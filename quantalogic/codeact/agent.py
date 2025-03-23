import asyncio
import time
from functools import partial
from typing import Callable, Dict, List, Optional, Tuple

import litellm
from jinja2 import Environment, FileSystemLoader
from lxml import etree

from quantalogic.python_interpreter import execute_async
from quantalogic.tools import Tool

from .constants import MAX_TOKENS, TEMPLATE_DIR
from .events import (
    ActionExecutedEvent,
    ActionGeneratedEvent,
    ErrorOccurredEvent,
    StepCompletedEvent,
    TaskCompletedEvent,
    TaskStartedEvent,
    ThoughtGeneratedEvent,
    StepStartedEvent,
)
from .tools_manager import get_default_tools
from .utils import XMLResultHandler, validate_code, validate_xml

jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), trim_blocks=True, lstrip_blocks=True)

async def generate_program(task_description: str, tools: List[Tool], model: str, max_tokens: int) -> str:
    """Generate a Python program using the specified model."""
    tool_docstrings = "\n\n".join(tool.to_docstring() for tool in tools)
    prompt = jinja_env.get_template("generate_program.j2").render(
        task_description=task_description,
        tool_docstrings=tool_docstrings
    )

    for attempt in range(3):
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a Python code generator."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )
            code = response.choices[0].message.content.strip()
            return code[9:-3].strip() if code.startswith("```python") and code.endswith("```") else code
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
            else:
                raise Exception(f"Code generation failed with {model}: {e}")

class Reasoner:
    """Handles action generation using the language model."""
    def __init__(self, model: str, tools: List[Tool]):
        self.model = model
        self.tools = tools

    async def generate_action(self, task: str, history_str: str, step: int, max_iterations: int, system_prompt: Optional[str] = None) -> str:
        """Generate an action based on task and history."""
        try:
            task_prompt = jinja_env.get_template("generate_action.j2").render(
                task=task if not system_prompt else f"{system_prompt}\nTask: {task}",
                history_str=history_str,
                current_step=step,
                max_iterations=max_iterations
            )
            program = await generate_program(task_prompt, self.tools, self.model, MAX_TOKENS)
            response = jinja_env.get_template("response_format.j2").render(
                task=task,
                history_str=history_str,
                program=program,
                current_step=step,
                max_iterations=max_iterations
            )
            if not validate_xml(response):
                raise ValueError("Invalid XML generated")
            return response
        except Exception as e:
            return jinja_env.get_template("error_format.j2").render(error=str(e))

class Executor:
    """Manages action execution and context updates."""
    def __init__(self, tools: List[Tool]):
        self.tools = tools
        self.tool_namespace = self._build_tool_namespace()

    def _build_tool_namespace(self) -> Dict:
        """Build the namespace for tool execution."""
        return {
            "asyncio": asyncio,
            "context_vars": {},  # Updated dynamically
            **{tool.name: partial(tool.async_execute) for tool in self.tools}
        }

    async def execute_action(self, code: str, context_vars: Dict, timeout: int = 300) -> str:
        """Execute the generated code and return the result."""
        if not validate_code(code):
            return etree.tostring(
                etree.Element("ExecutionResult", status="Error", message="Code lacks async main()"),
                encoding="unicode"
            )
        
        self.tool_namespace["context_vars"] = context_vars
        try:
            result = await execute_async(
                code=code, timeout=timeout, entry_point="main",
                allowed_modules=["asyncio"], namespace=self.tool_namespace
            )
            if result.local_variables:
                context_vars.update({
                    k: v for k, v in result.local_variables.items()
                    if not k.startswith('__') and not callable(v)
                })
            return XMLResultHandler.format_execution_result(result)
        except Exception as e:
            return etree.tostring(
                etree.Element("ExecutionResult", status="Error", message=f"Execution error: {e}"),
                encoding="unicode"
            )

class ReActAgent:
    """Core agent implementing the ReAct framework with modular components."""
    def __init__(self, model: str, tools: List[Tool], max_iterations: int = 5):
        self.reasoner = Reasoner(model, tools)
        self.executor = Executor(tools)
        self.max_iterations = max_iterations
        self.context_vars: Dict = {}
        self._observers: List[Tuple[Callable, List[str]]] = []

    def add_observer(self, observer: Callable, event_types: List[str]) -> 'ReActAgent':
        """Add an observer for specific event types."""
        self._observers.append((observer, event_types))
        return self

    async def _notify_observers(self, event):
        """Notify all subscribed observers of an event."""
        await asyncio.gather(
            *(observer(event) for observer, types in self._observers if event.event_type in types),
            return_exceptions=True
        )

    async def generate_action(self, task: str, history: List[Dict], step: int, max_iterations: int, system_prompt: Optional[str] = None) -> str:
        """Generate an action using the Reasoner."""
        history_str = self._format_history(history, max_iterations)
        start = time.perf_counter()
        response = await self.reasoner.generate_action(task, history_str, step, max_iterations, system_prompt)
        thought, code = XMLResultHandler.parse_response(response)
        gen_time = time.perf_counter() - start
        await self._notify_observers(ThoughtGeneratedEvent(
            event_type="ThoughtGenerated", step_number=step, thought=thought, generation_time=gen_time
        ))
        await self._notify_observers(ActionGeneratedEvent(
            event_type="ActionGenerated", step_number=step, action_code=code, generation_time=gen_time
        ))
        return response

    async def execute_action(self, code: str, step: int, timeout: int = 300) -> str:
        """Execute an action using the Executor."""
        start = time.perf_counter()
        result_xml = await self.executor.execute_action(code, self.context_vars, timeout)
        execution_time = time.perf_counter() - start
        await self._notify_observers(ActionExecutedEvent(
            event_type="ActionExecuted", step_number=step, result_xml=result_xml, execution_time=execution_time
        ))
        return result_xml

    def _format_history(self, history: List[Dict], max_iterations: int) -> str:
        """Format the history for use in prompts."""
        return "\n".join(
            f"===== Step {i + 1} of {max_iterations} max =====\n"
            f"Thought:\n{h['thought']}\n\nAction:\n{h['action']}\n\nResult:\n{XMLResultHandler.format_result_summary(h['result'])}"
            for i, h in enumerate(history)
        ) or "No previous steps"

    async def is_task_complete(self, task: str, history: List[Dict], result: str, success_criteria: Optional[str]) -> Tuple[bool, str]:
        """Check if the task is complete based on the result."""
        try:
            root = etree.fromstring(result)
            if root.findtext("Completed") == "true":
                final_answer = root.findtext("FinalAnswer") or ""
                verification = await litellm.acompletion(
                    model=self.reasoner.model,
                    messages=[{
                        "role": "user",
                        "content": f"Does '{final_answer}' solve '{task}' given history:\n{self._format_history(history, self.max_iterations)}?"
                    }],
                    temperature=0.1,
                    max_tokens=100
                )
                if "yes" in verification.choices[0].message.content.lower():
                    return True, final_answer
                return True, final_answer
        except etree.XMLSyntaxError:
            pass

        if success_criteria and (result_value := XMLResultHandler.extract_result_value(result)) and success_criteria in result_value:
            return True, result_value
        return False, ""

    async def solve(self, task: str, success_criteria: Optional[str] = None, system_prompt: Optional[str] = None, max_iterations: Optional[int] = None) -> List[Dict]:
        """Solve a task using the ReAct framework."""
        max_iters = max_iterations if max_iterations is not None else self.max_iterations
        history = []
        await self._notify_observers(TaskStartedEvent(event_type="TaskStarted", task_description=task))

        for step in range(1, max_iters + 1):
            await self._notify_observers(StepStartedEvent(event_type="StepStarted", step_number=step))
            try:
                response = await self.generate_action(task, history, step, max_iters, system_prompt)
                thought, code = XMLResultHandler.parse_response(response)
                result = await self.execute_action(code, step)
                history.append({"thought": thought, "action": code, "result": result})

                is_complete, final_answer = await self.is_task_complete(task, history, result, success_criteria)
                if is_complete:
                    history[-1]["result"] += f"\n<FinalAnswer><![CDATA[\n{final_answer}\n]]></FinalAnswer>"

                await self._notify_observers(StepCompletedEvent(
                    event_type="StepCompleted", step_number=step, thought=thought, 
                    action=code, result=history[-1]["result"], is_complete=is_complete,
                    final_answer=final_answer if is_complete else None
                ))

                if is_complete:
                    await self._notify_observers(TaskCompletedEvent(
                        event_type="TaskCompleted", final_answer=final_answer, reason="success"
                    ))
                    break
            except Exception as e:
                await self._notify_observers(ErrorOccurredEvent(
                    event_type="ErrorOccurred", error_message=str(e), step_number=step
                ))
                break

        if not any("<FinalAnswer>" in step["result"] for step in history):
            await self._notify_observers(TaskCompletedEvent(
                event_type="TaskCompleted", final_answer=None,
                reason="max_iterations_reached" if len(history) == max_iters else "error"
            ))
        return history

class Agent:
    """High-level interface for the Quantalogic Agent, providing chat and solve functionalities."""
    def __init__(
        self,
        model: str = "gemini/gemini-2.0-flash",
        tools: Optional[List[Tool]] = None,
        max_iterations: int = 5,
        personality: Optional[str] = None,
        backstory: Optional[str] = None,
        sop: Optional[str] = None
    ):
        self.model = model
        self.default_tools = tools if tools is not None else get_default_tools(model)
        self.max_iterations = max_iterations
        self.personality = personality
        self.backstory = backstory
        self.sop = sop
        self._observers: List[Tuple[Callable, List[str]]] = []

    def _build_system_prompt(self) -> str:
        """Builds a system prompt based on personality, backstory, and SOP."""
        prompt = "You are an AI assistant."
        if self.personality:
            prompt += f" You have a {self.personality} personality."
        if self.backstory:
            prompt += f" Your backstory is: {self.backstory}"
        if self.sop:
            prompt += f" Follow this standard operating procedure: {self.sop}"
        return prompt

    async def chat(self, message: str, use_tools: bool = False, tools: Optional[List[Tool]] = None, timeout: int = 30) -> str:
        """Single-step interaction with optional custom tools."""
        system_prompt = self._build_system_prompt()
        if use_tools:
            # Use provided tools or fall back to default tools
            chat_tools = tools if tools is not None else self.default_tools
            chat_agent = ReActAgent(model=self.model, tools=chat_tools, max_iterations=1)
            for observer, event_types in self._observers:
                chat_agent.add_observer(observer, event_types)
            history = await chat_agent.solve(message, system_prompt=system_prompt)
            return self._extract_response(history)
        else:
            response = await litellm.acompletion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            return response.choices[0].message.content.strip()

    def sync_chat(self, message: str, timeout: int = 30) -> str:
        """Synchronous wrapper for chat."""
        return asyncio.run(self.chat(message, timeout=timeout))

    async def solve(self, task: str, success_criteria: Optional[str] = None, max_iterations: Optional[int] = None, tools: Optional[List[Tool]] = None, timeout: int = 300) -> List[Dict]:
        """Multi-step task solving with optional custom tools and max_iterations."""
        system_prompt = self._build_system_prompt()
        # Use provided tools or fall back to default tools
        solve_tools = tools if tools is not None else self.default_tools
        solve_agent = ReActAgent(
            model=self.model,
            tools=solve_tools,
            max_iterations=max_iterations if max_iterations is not None else self.max_iterations
        )
        for observer, event_types in self._observers:
            solve_agent.add_observer(observer, event_types)
        return await solve_agent.solve(task, success_criteria, system_prompt=system_prompt, max_iterations=max_iterations)

    def sync_solve(self, task: str, success_criteria: Optional[str] = None, timeout: int = 300) -> List[Dict]:
        """Synchronous wrapper for solve."""
        return asyncio.run(self.solve(task, success_criteria, timeout=timeout))

    def add_observer(self, observer: Callable, event_types: List[str]) -> 'Agent':
        """Add an observer to be applied to agents created in chat and solve."""
        self._observers.append((observer, event_types))
        return self

    def list_tools(self) -> List[str]:
        """Return a list of available tool names."""
        return [tool.name for tool in self.default_tools]

    def get_context_vars(self) -> Dict:
        """Return the current context variables."""
        # Since context_vars are now per-agent instance, this method is less useful unless stored elsewhere.
        return {}

    def _extract_response(self, history: List[Dict]) -> str:
        """Extract a clean response from the history."""
        if not history:
            return "No response generated."
        last_result = history[-1]["result"]
        try:
            root = etree.fromstring(last_result)
            if root.findtext("Status") == "Success":
                value = root.findtext("Value") or ""
                final_answer = root.findtext("FinalAnswer")
                return final_answer.strip() if final_answer else value.strip()
            else:
                return f"Error: {root.findtext('Value') or 'Unknown error'}"
        except etree.XMLSyntaxError:
            return last_result