import asyncio
from functools import partial
from typing import Callable, Dict, List, Optional, Tuple
import time
from .utils import format_result_summary, format_execution_result

import litellm
from jinja2 import Environment, FileSystemLoader
from loguru import logger
from lxml import etree

from quantalogic.python_interpreter import execute_async
from quantalogic.tools import Tool

from .constants import MAX_TOKENS, TEMPLATE_DIR
from .events import (
    ActionExecutedEvent, ActionGeneratedEvent, ErrorOccurredEvent, 
    StepCompletedEvent, TaskCompletedEvent, TaskStartedEvent, 
    ThoughtGeneratedEvent
)
from .utils import validate_code, validate_xml

jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), trim_blocks=True, lstrip_blocks=True)

async def generate_program(task_description: str, tools: List[Tool], model: str, max_tokens: int) -> str:
    """Generate a Python program using the specified model."""
    tool_docstrings = "\n\n".join(tool.to_docstring() for tool in tools)
    prompt = jinja_env.get_template("action_code/generate_program.j2").render(
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

class ReActAgent:
    def __init__(self, model: str, tools: List[Tool], max_iterations: int = 5):
        self.model = model
        self.tools = tools
        self.max_iterations = max_iterations
        self.context_vars: Dict = {}
        self.tool_namespace = self._build_tool_namespace()
        self._observers: List[Tuple[Callable, List[str]]] = []

    def _build_tool_namespace(self) -> Dict:
        return {
            "asyncio": asyncio,
            "context_vars": self.context_vars,
            **{tool.name: partial(tool.async_execute) for tool in self.tools}
        }

    def add_observer(self, observer: Callable, event_types: List[str]) -> 'ReActAgent':
        self._observers.append((observer, event_types))
        return self

    async def _notify_observers(self, event):
        await asyncio.gather(
            *(observer(event) for observer, types in self._observers if event.event_type in types),
            return_exceptions=True
        )

    async def generate_action(self, task: str, history: List[Dict], step: int) -> str:
        history_str = self._format_history(history)
        try:
            start = time.perf_counter()
            task_prompt = jinja_env.get_template("action_code/generate_action.j2").render(
                task=task, history_str=history_str, current_step=step, max_iterations=self.max_iterations
            )
            program = await generate_program(task_prompt, self.tools, self.model, MAX_TOKENS)
            response = jinja_env.get_template("action_code/response_format.j2").render(
                task=task, history_str=history_str, program=program, 
                current_step=step, max_iterations=self.max_iterations
            )
            if not validate_xml(response):
                raise ValueError("Invalid XML generated")
            
            thought, code = self._parse_response(response)
            gen_time = time.perf_counter() - start
            await self._notify_observers(ThoughtGeneratedEvent(
                event_type="ThoughtGenerated", step_number=step, thought=thought, generation_time=gen_time
            ))
            await self._notify_observers(ActionGeneratedEvent(
                event_type="ActionGenerated", step_number=step, action_code=code, generation_time=gen_time
            ))
            return response
        except Exception as e:
            await self._notify_observers(ErrorOccurredEvent(
                event_type="ErrorOccurred", error_message=str(e), step_number=step
            ))
            return jinja_env.get_template("action_code/error_format.j2").render(error=str(e))

    async def execute_action(self, code: str, timeout: int = 300) -> str:
        if not validate_code(code):
            return etree.tostring(
                etree.Element("ExecutionResult", status="Error", 
                            message="Code lacks async main()"),
                encoding="unicode"
            )
        
        start = time.perf_counter()
        try:
            result = await execute_async(
                code=code, timeout=timeout, entry_point="main",
                allowed_modules=["asyncio"], namespace=self.tool_namespace
            )
            if result.local_variables:
                self.context_vars.update({
                    k: v for k, v in result.local_variables.items()
                    if not k.startswith('__') and not callable(v)
                })
            result_xml = format_execution_result(result)
            await self._notify_observers(ActionExecutedEvent(
                event_type="ActionExecuted", step_number=len(self.context_vars) + 1,
                result_xml=result_xml, execution_time=time.perf_counter() - start
            ))
            return result_xml
        except Exception as e:
            return etree.tostring(
                etree.Element("ExecutionResult", status="Error", message=f"Execution error: {e}"),
                encoding="unicode"
            )

    def _format_history(self, history: List[Dict]) -> str:
        return "\n".join(
            f"===== Step {i + 1} of {self.max_iterations} max =====\n"
            f"Thought:\n{h['thought']}\n\nAction:\n{h['action']}\n\nResult:\n{format_result_summary(h['result'])}"
            for i, h in enumerate(history)
        ) or "No previous steps"

    async def is_task_complete(self, task: str, history: List[Dict], result: str, 
                             success_criteria: Optional[str]) -> Tuple[bool, str]:
        try:
            result_xml = etree.fromstring(result)
            if result_xml.findtext("Completed") == "true":
                final_answer = result_xml.findtext("FinalAnswer") or ""
                verification = await litellm.acompletion(
                    model=self.model,
                    messages=[{
                        "role": "user",
                        "content": f"Does '{final_answer}' solve '{task}' given history:\n{self._format_history(history)}?"
                    }],
                    temperature=0.1,
                    max_tokens=100
                )
                if "yes" in verification.choices[0].message.content.lower():
                    return True, final_answer
                return True, final_answer
        except etree.XMLSyntaxError:
            pass

        if success_criteria and (result_value := self._extract_result(result)) and success_criteria in result_value:
            return True, result_value
        return False, ""

    def _extract_result(self, result: str) -> str:
        try:
            return etree.fromstring(result).findtext("Value") or ""
        except etree.XMLSyntaxError:
            return ""

    def _parse_response(self, response: str) -> Tuple[str, str]:
        try:
            root = etree.fromstring(response)
            return root.findtext("Thought") or "", root.findtext("Code") or ""
        except etree.XMLSyntaxError as e:
            raise ValueError(f"Failed to parse XML: {e}")

    async def solve(self, task: str, success_criteria: Optional[str] = None) -> List[Dict]:
        history = []
        await self._notify_observers(TaskStartedEvent(event_type="TaskStarted", task_description=task))

        for step in range(1, self.max_iterations + 1):
            try:
                response = await self.generate_action(task, history, step)
                thought, code = self._parse_response(response)
                result = await self.execute_action(code)
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
                reason="max_iterations_reached" if len(history) == self.max_iterations else "error"
            ))
        return history