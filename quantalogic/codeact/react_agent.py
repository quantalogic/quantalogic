import asyncio
import time
from typing import Callable, Dict, List, Optional, Tuple

from loguru import logger
from lxml import etree

from quantalogic.tools import Tool

from .events import (
    ActionExecutedEvent,
    ActionGeneratedEvent,
    ErrorOccurredEvent,
    StepCompletedEvent,
    StepStartedEvent,
    TaskCompletedEvent,
    TaskStartedEvent,
    ThoughtGeneratedEvent,
)
from .executor import Executor
from .llm_util import litellm_completion
from .reasoner import Reasoner
from .utils import XMLResultHandler


class ReActAgent:
    """Core agent implementing the ReAct framework with modular components."""
    def __init__(self, model: str, tools: List[Tool], max_iterations: int = 5, max_history_tokens: int = 2000):
        self.reasoner = Reasoner(model, tools)
        self.executor = Executor(tools, notify_event=self._notify_observers)
        self.max_iterations = max_iterations
        self.max_history_tokens = max_history_tokens
        self.context_vars: Dict = {}
        self._observers: List[Tuple[Callable, List[str]]] = []
        self.history_store: List[Dict] = []

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

    async def generate_action(
        self,
        task: str,
        history: List[Dict],
        step: int,
        max_iterations: int,
        system_prompt: Optional[str] = None,
        streaming: bool = False
    ) -> str:
        """Generate an action using the Reasoner."""
        history_str = self._format_history(history, max_iterations)
        start = time.perf_counter()
        response = await self.reasoner.generate_action(task, history_str, step, max_iterations, system_prompt, self._notify_observers, streaming=streaming)
        thought, code = XMLResultHandler.parse_response(response)
        gen_time = time.perf_counter() - start
        await self._notify_observers(ThoughtGeneratedEvent(
            event_type="ThoughtGenerated", step_number=step, thought=thought, generation_time=gen_time
        ))
        await self._notify_observers(ActionGeneratedEvent(
            event_type="ActionGenerated", step_number=step, action_code=code, generation_time=gen_time
        ))
        if not response.endswith("</Code>"):
            logger.warning(f"Response might be truncated at step {step}")
        return response

    async def execute_action(self, code: str, step: int, timeout: int = 300) -> str:
        """Execute an action using the Executor, passing the step number."""
        start = time.perf_counter()
        result_xml = await self.executor.execute_action(code, self.context_vars, step, timeout)
        execution_time = time.perf_counter() - start
        await self._notify_observers(ActionExecutedEvent(
            event_type="ActionExecuted", step_number=step, result_xml=result_xml, execution_time=execution_time
        ))
        return result_xml

    def _format_history(self, history: List[Dict], max_iterations: int) -> str:
        """Format the history with available variables, truncating to fit within max_history_tokens."""
        included_steps = []
        total_tokens = 0
        for step in reversed(history):
            try:
                root = etree.fromstring(step['result'])
                vars_elem = root.find("Variables")
                available_vars = (
                    [var.get('name') for var in vars_elem.findall("Variable")]
                    if vars_elem is not None else []
                )
            except etree.XMLSyntaxError:
                available_vars = []

            step_str = (
                f"===== Step {step['step_number']} of {max_iterations} max =====\n"
                f"Thought:\n{step['thought']}\n\n"
                f"Action:\n{step['action']}\n\n"
                f"Result:\n{XMLResultHandler.format_result_summary(step['result'])}\n"
                f"Available variables: {', '.join(available_vars) or 'None'}"
            )
            step_tokens = len(step_str.split())
            if total_tokens + step_tokens > self.max_history_tokens:
                break
            included_steps.append(step_str)
            total_tokens += step_tokens
        return "\n".join(reversed(included_steps)) or "No previous steps"

    async def is_task_complete(self, task: str, history: List[Dict], result: str, success_criteria: Optional[str]) -> Tuple[bool, str]:
        """Check if the task is complete based on the result."""
        try:
            root = etree.fromstring(result)
            if root.findtext("Completed") == "true":
                final_answer = root.findtext("FinalAnswer") or ""
                verification = await litellm_completion(
                    model=self.reasoner.model,
                    messages=[{
                        "role": "user",
                        "content": f"Does '{final_answer}' solve '{task}' given history:\n{self._format_history(history, self.max_iterations)}?"
                    }],
                    max_tokens=100,
                    temperature=0.1,
                    stream=False
                )
                if "yes" in verification.lower():
                    return True, final_answer
                return True, final_answer
        except etree.XMLSyntaxError:
            pass

        if success_criteria and (result_value := XMLResultHandler.extract_result_value(result)) and success_criteria in result_value:
            return True, result_value
        return False, ""

    async def solve(
        self,
        task: str,
        success_criteria: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_iterations: Optional[int] = None,
        streaming: bool = False
    ) -> List[Dict]:
        """Solve a task using the ReAct framework."""
        max_iters = max_iterations if max_iterations is not None else self.max_iterations
        history = []
        self.history_store = []
        await self._notify_observers(TaskStartedEvent(event_type="TaskStarted", task_description=task))

        for step in range(1, max_iters + 1):
            await self._notify_observers(StepStartedEvent(event_type="StepStarted", step_number=step))
            try:
                response = await self.generate_action(task, history, step, max_iters, system_prompt, streaming=streaming)
                thought, code = XMLResultHandler.parse_response(response)
                result = await self.execute_action(code, step)
                step_data = {"step_number": step, "thought": thought, "action": code, "result": result}
                history.append(step_data)
                self.history_store.append(step_data)

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