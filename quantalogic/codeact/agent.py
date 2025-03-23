import asyncio  # noqa: I001
from functools import partial
from typing import Callable, Dict, List, Optional, Tuple, Awaitable, Union

import litellm
from jinja2 import Environment, FileSystemLoader
from loguru import logger
from lxml import etree
from pydantic import BaseModel, Field
from datetime import datetime
import time

from quantalogic.python_interpreter import execute_async
from quantalogic.tools import Tool

from .constants import MAX_TOKENS, TEMPLATE_DIR
from .utils import format_execution_result, format_result_xml, validate_code, validate_xml

jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), trim_blocks=True, lstrip_blocks=True)

# Base Event Class using Pydantic V2
class Event(BaseModel):
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.now)

# Specific Event Types using Pydantic V2
class TaskStartedEvent(Event):
    task_description: str

class ThoughtGeneratedEvent(Event):
    step_number: int
    thought: str
    generation_time: float

class ActionGeneratedEvent(Event):
    step_number: int
    action_code: str
    generation_time: float

class ActionExecutedEvent(Event):
    step_number: int
    result_xml: str
    execution_time: float

class StepCompletedEvent(Event):
    step_number: int
    thought: str
    action: str
    result: str
    is_complete: bool
    final_answer: Optional[str] = None

class ErrorOccurredEvent(Event):
    error_message: str
    step_number: Optional[int] = None

class TaskCompletedEvent(Event):
    final_answer: Optional[str]
    reason: str

async def generate_program(task_description: str, tools: List[Tool], model: str, max_tokens: int) -> str:
    logger.debug(f"Generating program for task: {task_description}")
    tool_docstrings = "\n\n".join([tool.to_docstring() for tool in tools])

    template = jinja_env.get_template("action_code/generate_program.j2")
    prompt = template.render(
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
            generated_code = response.choices[0].message.content.strip()
            
            if generated_code.startswith("```python") and generated_code.endswith("```"):
                generated_code = generated_code[9:-3].strip()
            return generated_code
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
            else:
                raise Exception(f"Failed to generate code with model '{model}': {str(e)}")

class ReActAgent:
    def __init__(self, model: str, tools: List[Tool], max_iterations: int = 5):
        self.model = model
        self.tools = tools
        self.max_iterations = max_iterations
        self.context_vars = {}
        self.tool_namespace: Dict[str, Callable] = self._build_tool_namespace()
        # List of tuples: (observer function, list of event types to subscribe to)
        self._observers: List[Tuple[Callable[[Event], Awaitable[None]], List[str]]] = []

    def _build_tool_namespace(self) -> Dict[str, Callable]:
        namespace = {
            "asyncio": asyncio,
            "context_vars": self.context_vars
        }
        for tool in self.tools:
            namespace[tool.name] = partial(tool.async_execute)
        return namespace

    def add_observer(self, observer: Callable[[Event], Awaitable[None]], event_types: List[str]) -> 'ReActAgent':
        """Add an observer to monitor specific events in the agent's lifecycle.

        Args:
            observer: An async function that takes an Event and returns None.
            event_types: List of event type strings the observer subscribes to.

        Returns:
            Self, for method chaining.
        """
        self._observers.append((observer, event_types))
        return self

    async def _notify_observers(self, event: Event) -> None:
        """Notify all registered observers concurrently with the current event.

        Args:
            event: The Event instance to send to observers.
        """
        tasks = []
        for observer, event_types in self._observers:
            if event.event_type in event_types:
                tasks.append(self._run_observer(observer, event))
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Observer failed with error: {result}")

    async def _run_observer(self, observer: Callable[[Event], Awaitable[None]], event: Event):
        """Run a single observer with error handling."""
        try:
            await observer(event)
        except Exception as e:
            raise e

    async def generate_action(self, task: str, history: List[Dict[str, str]], current_step: int, max_iterations: int) -> str:
        history_str = self._format_history(history, max_iterations)

        try:
            task_prompt = jinja_env.get_template("action_code/generate_action.j2").render(
                task=task,
                history_str=history_str,
                current_step=current_step,
                max_iterations=max_iterations
            )
            start_time = time.perf_counter()
            program = await generate_program(
                task_description=task_prompt,
                tools=self.tools,
                model=self.model,
                max_tokens=MAX_TOKENS,
            )
            generation_time = time.perf_counter() - start_time
            response = jinja_env.get_template("action_code/response_format.j2").render(
                task=task,
                history_str=history_str,
                program=program,
                current_step=current_step,
                max_iterations=max_iterations
            )
            if not validate_xml(response):
                raise ValueError("Generated XML is invalid")
            
            # Notify observers of thought and action generation
            thought, code = self._parse_response(response)
            await self._notify_observers(ThoughtGeneratedEvent(
                event_type="ThoughtGenerated",
                step_number=current_step,
                thought=thought,
                generation_time=generation_time
            ))
            await self._notify_observers(ActionGeneratedEvent(
                event_type="ActionGenerated",
                step_number=current_step,
                action_code=code,
                generation_time=generation_time
            ))
            return response
        except Exception as e:
            await self._notify_observers(ErrorOccurredEvent(
                event_type="ErrorOccurred",
                error_message=str(e),
                step_number=current_step
            ))
            return jinja_env.get_template("action_code/error_format.j2").render(error=str(e))

    async def execute_action(self, code: str, timeout: int = 300) -> str:
        if not validate_code(code):
            error_xml = etree.tostring(
                etree.Element("ExecutionResult", status="Error", 
                            message="Generated code lacks an async main() function"),
                encoding="unicode"
            )
            return error_xml

        try:
            start_time = time.perf_counter()
            result = await execute_async(
                code=code,
                timeout=timeout,
                entry_point="main",
                allowed_modules=["asyncio"],
                namespace=self.tool_namespace,
            )
            execution_time = time.perf_counter() - start_time
            if result.local_variables:
                self.context_vars.update({
                    k: v for k, v in result.local_variables.items()
                    if not k.startswith('__') and not callable(v)
                })
            result_xml = format_execution_result(result)
            return result_xml
        except Exception as e:
            error_xml = etree.tostring(
                etree.Element("ExecutionResult", status="Error", message=f"Execution error: {e}"),
                encoding="unicode"
            )
            return error_xml

    def _format_history(self, history: List[Dict[str, str]], max_iterations: int) -> str:
        formatted_steps = []
        for i, h in enumerate(history):
            step_str = (
                f"===== Step {i + 1} of {max_iterations} max =====\n"
                f"Thought:\n{h['thought']}\n\n"
                f"Action:\n{h['action']}\n\n"
                f"Result:\n{format_result_xml(h['result'])}"
            )
            formatted_steps.append(step_str)
        return "\n".join(formatted_steps) if formatted_steps else "No previous steps"

    async def is_task_complete(self, task: str, history: List[Dict[str, str]], result: str, 
                             success_criteria: Optional[str] = None) -> Tuple[bool, str]:
        try:
            result_xml = etree.fromstring(result)
            if result_xml.findtext("Completed") == "true":
                final_answer = result_xml.findtext("FinalAnswer") or ""
                verification_prompt = f"Does '{final_answer}' solve '{task}' given history:\n{self._format_history(history, self.max_iterations)}?"
                verification = await litellm.acompletion(
                    model=self.model,
                    messages=[{"role": "user", "content": verification_prompt}],
                    temperature=0.1,
                    max_tokens=100
                )
                response = verification.choices[0].message.content.lower()
                if "yes" in response or "true" in response:
                    return True, final_answer
                return True, final_answer
        
        except etree.XMLSyntaxError:
            pass
        
        if success_criteria:
            result_value = self._extract_result(result)
            if result_value and success_criteria in result_value:
                return True, result_value
        
        return False, ""

    def _extract_final_answer(self, result: str) -> str:
        try:
            return etree.fromstring(result).findtext("FinalAnswer") or ""
        except etree.XMLSyntaxError:
            return ""

    def _extract_result(self, result: str) -> str:
        try:
            return etree.fromstring(result).findtext("Value") or ""
        except etree.XMLSyntaxError:
            return ""

    async def solve(self, task: str, success_criteria: Optional[str] = None) -> List[Dict[str, str]]:
        history = []
        await self._notify_observers(TaskStartedEvent(
            event_type="TaskStarted",
            task_description=task
        ))
        
        for iteration in range(self.max_iterations):
            current_step = iteration + 1
            try:
                response = await self.generate_action(task, history, current_step, self.max_iterations)
                thought, code = self._parse_response(response)
                
                start_time = time.perf_counter()
                result = await self.execute_action(code)
                execution_time = time.perf_counter() - start_time
                
                history.append({"thought": thought, "action": code, "result": result})
                
                # Notify ActionExecutedEvent
                await self._notify_observers(ActionExecutedEvent(
                    event_type="ActionExecuted",
                    step_number=current_step,
                    result_xml=result,
                    execution_time=execution_time
                ))
                
                # Check if the task is complete
                is_complete, final_answer = await self.is_task_complete(task, history, result, success_criteria)
                if is_complete:
                    history[-1]["result"] += f"\n<FinalAnswer><![CDATA[\n{final_answer}\n]]></FinalAnswer>"
                
                # Notify StepCompletedEvent
                await self._notify_observers(StepCompletedEvent(
                    event_type="StepCompleted",
                    step_number=current_step,
                    thought=thought,
                    action=code,
                    result=history[-1]["result"],
                    is_complete=is_complete,
                    final_answer=final_answer if is_complete else None
                ))
                
                if is_complete:
                    await self._notify_observers(TaskCompletedEvent(
                        event_type="TaskCompleted",
                        final_answer=final_answer,
                        reason="success"
                    ))
                    break
            except (ValueError, etree.XMLSyntaxError) as e:
                await self._notify_observers(ErrorOccurredEvent(
                    event_type="ErrorOccurred",
                    error_message=str(e),
                    step_number=current_step
                ))
                break
        
        if not history or not any("<FinalAnswer>" in step["result"] for step in history):
            await self._notify_observers(TaskCompletedEvent(
                event_type="TaskCompleted",
                final_answer=None,
                reason="max_iterations_reached" if len(history) == self.max_iterations else "error"
            ))
        
        return history

    def _parse_response(self, response: str) -> Tuple[str, str]:
        try:
            root = etree.fromstring(response)
            return root.findtext("Thought") or "", root.findtext("Code") or ""
        except etree.XMLSyntaxError as e:
            raise ValueError(f"Failed to parse XML response: {e}")