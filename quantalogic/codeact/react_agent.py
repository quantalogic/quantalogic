"""Core implementation of the ReAct framework for reasoning and acting."""

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
from .executor import BaseExecutor, Executor
from .history_manager import HistoryManager
from .llm_util import litellm_completion
from .reasoner import BaseReasoner, Reasoner
from .tools_manager import ToolRegistry
from .utils import XMLResultHandler


class ReActAgent:
    """Implements the ReAct framework for reasoning and acting."""
    def __init__(
        self,
        model: str,
        tools: List[Tool],
        max_iterations: int = 5,
        max_history_tokens: int = 2000,
        reasoner: Optional[BaseReasoner] = None,
        executor: Optional[BaseExecutor] = None,
        tool_registry: Optional[ToolRegistry] = None,
        history_manager: Optional[HistoryManager] = None,
        error_handler: Optional[Callable[[Exception, int], bool]] = None
    ) -> None:
        self.tool_registry = tool_registry or ToolRegistry()
        for tool in tools:
            self.tool_registry.register(tool)
        self.reasoner: BaseReasoner = reasoner or Reasoner(model, self.tool_registry.get_tools())
        self.executor: BaseExecutor = executor or Executor(self.tool_registry.get_tools(), notify_event=self._notify_observers)
        self.max_iterations: int = max_iterations
        self.max_history_tokens: int = max_history_tokens
        self.history_manager: HistoryManager = history_manager or HistoryManager(max_tokens=max_history_tokens)
        self.context_vars: Dict = {}
        self._observers: List[Tuple[Callable, List[str]]] = []
        self.error_handler = error_handler or (lambda e, step: False)  # Default: no retry

    def add_observer(self, observer: Callable, event_types: List[str]) -> 'ReActAgent':
        """Add an observer for specific event types."""
        self._observers.append((observer, event_types))
        return self

    async def _notify_observers(self, event: object) -> None:
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
        history_str: str = self.history_manager.format_history(max_iterations)
        start: float = time.perf_counter()
        response: str = await self.reasoner.generate_action(
            task, history_str, step, max_iterations, system_prompt, self._notify_observers, streaming=streaming
        )
        thought, code = XMLResultHandler.parse_action_response(response)
        gen_time: float = time.perf_counter() - start
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
        start: float = time.perf_counter()
        result_xml: str = await self.executor.execute_action(code, self.context_vars, step, timeout)
        execution_time: float = time.perf_counter() - start
        await self._notify_observers(ActionExecutedEvent(
            event_type="ActionExecuted", step_number=step, result_xml=result_xml, execution_time=execution_time
        ))
        return result_xml

    async def is_task_complete(self, task: str, history: List[Dict], result: str, success_criteria: Optional[str]) -> Tuple[bool, str]:
        """Check if the task is complete based on the result."""
        try:
            root = etree.fromstring(result)
            if root.findtext("Completed") == "true":
                final_answer: str = root.findtext("FinalAnswer") or ""
                verification: str = await litellm_completion(
                    model=self.reasoner.model,
                    messages=[{
                        "role": "user",
                        "content": f"Does '{final_answer}' solve '{task}' given history:\n{self.history_manager.format_history(self.max_iterations)}?"
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

    async def _run_step(self, task: str, step: int, max_iters: int, 
                       system_prompt: Optional[str], streaming: bool) -> Dict:
        """Execute a single step of the ReAct loop with retry logic."""
        await self._notify_observers(StepStartedEvent(event_type="StepStarted", step_number=step))
        for attempt in range(3):
            try:
                response: str = await self.generate_action(task, self.history_manager.store, step, max_iters, system_prompt, streaming)
                thought, code = XMLResultHandler.parse_action_response(response)
                result: str = await self.execute_action(code, step)
                step_data = {"step_number": step, "thought": thought, "action": code, "result": result}
                self.history_manager.add_step(step_data)
                return step_data
            except Exception as e:
                if not self.error_handler(e, step) or attempt == 2:
                    await self._notify_observers(ErrorOccurredEvent(
                        event_type="ErrorOccurred", error_message=str(e), step_number=step
                    ))
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

    async def _finalize_step(self, task: str, step_data: Dict, 
                            success_criteria: Optional[str]) -> Tuple[bool, Dict]:
        """Check completion and notify observers for a step."""
        is_complete, final_answer = await self.is_task_complete(task, self.history_manager.store, step_data["result"], success_criteria)
        if is_complete:
            try:
                root = etree.fromstring(step_data["result"])
                if root.find("FinalAnswer") is None:
                    final_answer_elem = etree.Element("FinalAnswer")
                    final_answer_elem.text = etree.CDATA(final_answer)
                    root.append(final_answer_elem)
                step_data["result"] = etree.tostring(root, pretty_print=True, encoding="unicode")
            except etree.XMLSyntaxError as e:
                logger.error(f"Failed to parse result XML for appending FinalAnswer: {e}")
                if "<FinalAnswer>" not in step_data["result"]:
                    step_data["result"] += f"\n<FinalAnswer><![CDATA[\n{final_answer}\n]]></FinalAnswer>"
        await self._notify_observers(StepCompletedEvent(
            event_type="StepCompleted", step_number=step_data["step_number"], 
            thought=step_data["thought"], action=step_data["action"], result=step_data["result"],
            is_complete=is_complete, final_answer=final_answer if is_complete else None
        ))
        return is_complete, step_data

    async def solve(
        self,
        task: str,
        success_criteria: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_iterations: Optional[int] = None,
        streaming: bool = False
    ) -> List[Dict]:
        """Solve a task using the ReAct framework."""
        max_iters: int = max_iterations if max_iterations is not None else self.max_iterations
        self.history_manager.store.clear()  # Reset history for new task
        await self._notify_observers(TaskStartedEvent(event_type="TaskStarted", task_description=task))

        for step in range(1, max_iters + 1):
            try:
                step_data: Dict = await self._run_step(task, step, max_iters, system_prompt, streaming)
                is_complete, step_data = await self._finalize_step(task, step_data, success_criteria)
                if is_complete:
                    await self._notify_observers(TaskCompletedEvent(
                        event_type="TaskCompleted", final_answer=step_data["result"], reason="success"
                    ))
                    break
            except Exception as e:
                await self._notify_observers(ErrorOccurredEvent(
                    event_type="ErrorOccurred", error_message=str(e), step_number=step
                ))
                break

        if not any("<FinalAnswer>" in step["result"] for step in self.history_manager.store):
            await self._notify_observers(TaskCompletedEvent(
                event_type="TaskCompleted", final_answer=None,
                reason="max_iterations_reached" if len(self.history_manager.store) == max_iters else "error"
            ))
        return self.history_manager.store