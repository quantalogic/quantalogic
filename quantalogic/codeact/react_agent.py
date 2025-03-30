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
from .llm_util import litellm_completion
from .reasoner import BaseReasoner, Reasoner
from .utils import XMLResultHandler


class ReActAgent:
    """Implements the ReAct framework for reasoning and acting.

    This class coordinates the generation and execution of actions to solve tasks,
    using a reasoner and executor. It supports event notifications for monitoring progress.

    Attributes:
        reasoner (BaseReasoner): Component for generating actions.
        executor (BaseExecutor): Component for executing actions.
        max_iterations (int): Maximum number of steps to attempt.
        max_history_tokens (int): Token limit for history formatting.
        context_vars (Dict): Stores variables across steps.
        _observers (List[Tuple[Callable, List[str]]]): Registered event observers.
        history_store (List[Dict]): Records steps for retrieval.
    """
    def __init__(
        self,
        model: str,
        tools: List[Tool],
        max_iterations: int = 5,
        max_history_tokens: int = 2000,
        reasoner: Optional[BaseReasoner] = None,
        executor: Optional[BaseExecutor] = None
    ) -> None:
        self.reasoner: BaseReasoner = reasoner or Reasoner(model, tools)
        self.executor: BaseExecutor = executor or Executor(tools, notify_event=self._notify_observers)
        self.max_iterations: int = max_iterations
        self.max_history_tokens: int = max_history_tokens
        self.context_vars: Dict = {}
        self._observers: List[Tuple[Callable, List[str]]] = []
        self.history_store: List[Dict] = []

    def add_observer(self, observer: Callable, event_types: List[str]) -> 'ReActAgent':
        """Add an observer for specific event types.

        Args:
            observer (Callable): Function to call when events occur.
            event_types (List[str]): List of event type names to subscribe to.

        Returns:
            ReActAgent: Self, for method chaining.
        """
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
        """Generate an action using the Reasoner.

        Args:
            task (str): The task to solve.
            history (List[Dict]): Previous steps' data.
            step (int): Current step number.
            max_iterations (int): Maximum allowed steps.
            system_prompt (Optional[str]): Optional system prompt.
            streaming (bool): Whether to stream the response.

        Returns:
            str: Generated action in XML format.
        """
        history_str: str = self._format_history(history, max_iterations)
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
        """Execute an action using the Executor, passing the step number.

        Args:
            code (str): Python code to execute.
            step (int): Current step number.
            timeout (int): Execution timeout in seconds.

        Returns:
            str: Execution result in XML format.
        """
        start: float = time.perf_counter()
        result_xml: str = await self.executor.execute_action(code, self.context_vars, step, timeout)
        execution_time: float = time.perf_counter() - start
        await self._notify_observers(ActionExecutedEvent(
            event_type="ActionExecuted", step_number=step, result_xml=result_xml, execution_time=execution_time
        ))
        return result_xml

    def _format_history(self, history: List[Dict], max_iterations: int) -> str:
        """Format the history with available variables, truncating to fit within max_history_tokens.

        Args:
            history (List[Dict]): Previous steps' data.
            max_iterations (int): Maximum allowed steps.

        Returns:
            str: Formatted history string.
        """
        included_steps: List[str] = []
        total_tokens: int = 0
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

            step_str: str = (
                f"===== Step {step['step_number']} of {max_iterations} max =====\n"
                f"Thought:\n{step['thought']}\n\n"
                f"Action:\n{step['action']}\n\n"
                f"Result:\n{XMLResultHandler.format_result_summary(step['result'])}\n"
                f"Available variables: {', '.join(available_vars) or 'None'}"
            )
            step_tokens: int = len(step_str.split())
            if total_tokens + step_tokens > self.max_history_tokens:
                break
            included_steps.append(step_str)
            total_tokens += step_tokens
        return "\n".join(reversed(included_steps)) or "No previous steps"

    async def is_task_complete(self, task: str, history: List[Dict], result: str, success_criteria: Optional[str]) -> Tuple[bool, str]:
        """Check if the task is complete based on the result.

        Args:
            task (str): The task to solve.
            history (List[Dict]): Previous steps' data.
            result (str): Result of the latest action.
            success_criteria (Optional[str]): Criteria to determine completion.

        Returns:
            Tuple[bool, str]: (is_complete, final_answer).
        """
        try:
            root = etree.fromstring(result)
            if root.findtext("Completed") == "true":
                final_answer: str = root.findtext("FinalAnswer") or ""
                verification: str = await litellm_completion(
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

    async def _run_step(self, task: str, history: List[Dict], step: int, max_iters: int, 
                       system_prompt: Optional[str], streaming: bool) -> Dict:
        """Execute a single step of the ReAct loop.

        Args:
            task (str): The task to solve.
            history (List[Dict]): Previous steps' data.
            step (int): Current step number.
            max_iters (int): Maximum allowed steps.
            system_prompt (Optional[str]): Optional system prompt.
            streaming (bool): Whether to stream the response.

        Returns:
            Dict: Step data including thought, action, and result.
        """
        await self._notify_observers(StepStartedEvent(event_type="StepStarted", step_number=step))
        response: str = await self.generate_action(task, history, step, max_iters, system_prompt, streaming)
        thought, code = XMLResultHandler.parse_action_response(response)
        result: str = await self.execute_action(code, step)
        return {"step_number": step, "thought": thought, "action": code, "result": result}

    async def _finalize_step(self, task: str, history: List[Dict], step_data: Dict, 
                            success_criteria: Optional[str]) -> Tuple[bool, Dict]:
        """Check completion and notify observers for a step.

        Args:
            task (str): The task to solve.
            history (List[Dict]): Previous steps' data.
            step_data (Dict): Data from the current step.
            success_criteria (Optional[str]): Criteria to determine completion.

        Returns:
            Tuple[bool, Dict]: (is_complete, updated_step_data).
        """
        is_complete, final_answer = await self.is_task_complete(task, history, step_data["result"], success_criteria)
        if is_complete:
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
        """Solve a task using the ReAct framework.

        Args:
            task (str): The task to solve.
            success_criteria (Optional[str]): Criteria to determine completion.
            system_prompt (Optional[str]): Optional system prompt.
            max_iterations (Optional[int]): Override for max steps.
            streaming (bool): Whether to stream responses.

        Returns:
            List[Dict]: History of steps taken.
        """
        max_iters: int = max_iterations if max_iterations is not None else self.max_iterations
        history: List[Dict] = []
        self.history_store = []
        await self._notify_observers(TaskStartedEvent(event_type="TaskStarted", task_description=task))

        for step in range(1, max_iters + 1):
            try:
                step_data: Dict = await self._run_step(task, history, step, max_iters, system_prompt, streaming)
                is_complete, step_data = await self._finalize_step(task, history, step_data, success_criteria)
                history.append(step_data)
                self.history_store.append(step_data)
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

        if not any("<FinalAnswer>" in step["result"] for step in history):
            await self._notify_observers(TaskCompletedEvent(
                event_type="TaskCompleted", final_answer=None,
                reason="max_iterations_reached" if len(history) == max_iters else "error"
            ))
        return history