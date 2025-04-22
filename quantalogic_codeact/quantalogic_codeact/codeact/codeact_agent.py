"""Core implementation of the ReAct framework for reasoning and acting."""

import asyncio
import inspect
import time
from typing import Callable, Dict, List, Optional, Tuple

from loguru import logger

from quantalogic.tools import Tool

from .conversation_history_manager import ConversationHistoryManager
from .events import (
    ActionExecutedEvent,
    ActionGeneratedEvent,
    ErrorOccurredEvent,
    ExecutionResult,
    StepCompletedEvent,
    StepStartedEvent,
    TaskCompletedEvent,
    TaskStartedEvent,
    ThoughtGeneratedEvent,
)
from .executor import BaseExecutor, Executor
from .history_manager import HistoryManager
from .llm_util import LLMCompletionError, litellm_completion
from .reasoner import BaseReasoner, Reasoner
from .templates import jinja_env
from .tools_manager import ToolRegistry
from .xml_utils import XMLResultHandler

MAX_HISTORY_TOKENS = 64*1024
MAX_ITERATIONS = 5
MAX_TOKENS = 4000

class CodeActAgent:
    """Implements the ReAct framework for reasoning and acting with enhanced memory management."""
    
    def __init__(
        self,
        model: str,
        tools: List[Tool],
        max_iterations: int = MAX_ITERATIONS,
        max_history_tokens: int = MAX_HISTORY_TOKENS,
        system_prompt: str = "",
        task_description: str = "",
        reasoner: Optional[BaseReasoner] = None,
        executor: Optional[BaseExecutor] = None,
        tool_registry: Optional[ToolRegistry] = None,
        history_manager: Optional[HistoryManager] = None,
        conversation_history_manager: Optional[ConversationHistoryManager] = None,
        error_handler: Optional[Callable[[Exception, int], bool]] = None
    ) -> None:
        """
        Initialize the CodeActAgent with tools, reasoning, execution, and memory components.

        Args:
            model (str): Language model identifier.
            tools (List[Tool]): List of available tools.
            max_iterations (int): Maximum reasoning steps (default: 5).
            max_history_tokens (int): Max tokens for history (default: 65536).
            system_prompt (str): Persistent system instructions (default: "").
            task_description (str): Persistent task context (default: "").
            reasoner (Optional[BaseReasoner]): Custom reasoner instance.
            executor (Optional[BaseExecutor]): Custom executor instance.
            tool_registry (Optional[ToolRegistry]): Custom tool registry.
            history_manager (Optional[HistoryManager]): Custom task history manager.
            conversation_history_manager (Optional[ConversationHistoryManager]): Custom conversation history manager.
            error_handler (Optional[Callable[[Exception, int], bool]]): Error handler callback.
        """
        self.tool_registry = tool_registry or ToolRegistry()
        for tool in tools:
            self.tool_registry.register(tool)
        self.reasoner: BaseReasoner = reasoner or Reasoner(model, self.tool_registry.get_tools())
        self.executor: BaseExecutor = executor or Executor(self.tool_registry.get_tools(), notify_event=self._notify_observers)
        self.max_iterations: int = max_iterations
        self.max_history_tokens: int = max_history_tokens
        self.history_manager: HistoryManager = history_manager or HistoryManager(
            max_tokens=max_history_tokens,
            system_prompt=system_prompt,
            task_description=task_description
        )
        self.conversation_history_manager: ConversationHistoryManager = conversation_history_manager or ConversationHistoryManager(
            max_tokens=max_history_tokens
        )
        self.context_vars: Dict = {}
        self._observers: List[Tuple[Callable, List[str]]] = []
        self.error_handler = error_handler or (lambda e, step: False)  # Default: no retry

    def add_observer(self, observer: Callable, event_types: List[str]) -> 'CodeActAgent':
        """Add an observer for specific event types."""
        try:
            self._observers.append((observer, event_types))
            return self
        except Exception as e:
            logger.error(f"Failed to add observer: {e}")
            raise

    async def _notify_observers(self, event: object) -> None:
        """Notify all subscribed observers of an event."""
        try:
            coroutines = []
            for observer, types in self._observers:
                if event.event_type in types:
                    result = observer(event)
                    if inspect.isawaitable(result):
                        coroutines.append(result)
                    else:
                        # Wrap sync observer in coroutine
                        coroutines.append(asyncio.to_thread(lambda: result))
            
            await asyncio.gather(*coroutines, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error notifying observers: {e}")

    def construct_prompt(self, task: str, task_goal: str = None) -> str:
        """
        Construct the prompt with task goal, task history, and conversation summary.

        Args:
            task (str): The task to address.
            task_goal (str, optional): The explicit goal for the task.

        Returns:
            str: The constructed prompt.
        """
        try:
            goal = task_goal or task
            task_prompt = f"Goal: {goal}\nTask: {task}"
            task_history = self.history_manager.format_history(self.max_iterations)
            conv_summary = self.conversation_history_manager.summarize(task)
            return (
                f"{task_prompt}\n\n"
                f"Task Steps Taken:\n{task_history}\n\n"
                f"Conversation Background:\n{conv_summary}"
            )
        except Exception as e:
            logger.error(f"Error constructing prompt: {e}")
            return task

    async def generate_action(
        self,
        task: str,
        history: List[Dict],
        step: int,
        max_iterations: int,
        system_prompt: Optional[str] = None,
        streaming: bool = False
    ) -> str:
        """
        Generate an action using the Reasoner, passing available variables.

        Args:
            task (str): The task to address.
            history (List[Dict]): Stored step history.
            step (int): Current step number.
            max_iterations (int): Maximum allowed steps.
            system_prompt (Optional[str]): Override system prompt (optional).
            streaming (bool): Whether to stream the response.

        Returns:
            str: Generated action in XML format.
        """
        try:
            history_str: str = self.history_manager.format_history(max_iterations)
            available_vars: List[str] = list(self.context_vars.keys())
            start: float = time.perf_counter()
            response: str = await self.reasoner.generate_action(
                task, 
                history_str, 
                step, 
                max_iterations, 
                system_prompt or self.history_manager.system_prompt,
                self._notify_observers, 
                streaming=streaming, 
                available_vars=available_vars
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
        except Exception as e:
            logger.error(f"Error generating action: {e}")
            raise

    async def execute_action(self, code: str, step: int, timeout: int = 300) -> ExecutionResult:
        """
        Execute an action using the Executor.

        Args:
            code (str): Code to execute.
            step (int): Current step number.
            timeout (int): Execution timeout in seconds (default: 300).

        Returns:
            ExecutionResult: Execution result as a structured Pydantic model.
        """
        try:
            start: float = time.perf_counter()
            result: ExecutionResult = await self.executor.execute_action(code, self.context_vars, step, timeout)
            execution_time: float = time.perf_counter() - start
            result.execution_time = execution_time  # Ensure accurate timing
            await self._notify_observers(ActionExecutedEvent(
                event_type="ActionExecuted", step_number=step, result=result, execution_time=execution_time
            ))
            return result
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            raise

    async def is_task_complete(self, task: str, history: List[Dict], result: ExecutionResult, success_criteria: Optional[str]) -> Tuple[bool, str]:
        """
        Check if the task is complete based on the execution result.

        Args:
            task (str): The task being solved.
            history (List[Dict]): Stored step history.
            result (ExecutionResult): Result of the latest execution.
            success_criteria (Optional[str]): Optional success criteria.

        Returns:
            Tuple[bool, str]: (is_complete, final_answer).
        """
        try:
            if result.execution_status != "success":
                logger.info(f"Task not complete at step due to execution error: {result.error}")
                return False, ""

            task_status = result.task_status
            final_answer = result.result or ""

            # Use LLM to verify completion if task is marked as completed
            if task_status == "completed":
                template = jinja_env.get_template("is_task_complete.j2")
                verification_prompt = template.render(
                    task=task,
                    final_answer=final_answer,
                    task_status=task_status,
                    reason="Task marked as completed by execution result",
                    history=self.history_manager.format_history(self.max_iterations)
                )
                verification = await litellm_completion(
                    model=self.reasoner.model,
                    messages=[{"role": "user", "content": verification_prompt}],
                    max_tokens=20,
                    temperature=0.1,
                    stream=False
                )
                verification = verification.lower().strip()
                if verification == "yes":
                    logger.info(f"Task verified as complete: {final_answer}")
                    return True, final_answer
                elif verification == "not_solvable":
                    logger.info(f"Task deemed unsolvable: {final_answer}")
                    return True, f"Task is unsolvable: {final_answer}"
                elif verification == "no":
                    logger.info(f"LLM judge indicates task is not complete: '{verification}'")
                    return False, ""
                else:
                    logger.warning(f"Unexpected judge response: '{verification}', treating as 'no'")
                    return False, ""

            # Check success criteria if provided
            if success_criteria and final_answer and success_criteria in final_answer:
                logger.info(f"Task completed based on success criteria: {success_criteria}")
                return True, final_answer

            logger.info("Task not complete: in progress or no criteria met")
            return False, ""
        except Exception as e:
            logger.error(f"Error checking task completion: {e}")
            return False, ""

    async def _run_step(self, task: str, step: int, max_iters: int, 
                       system_prompt: Optional[str], streaming: bool) -> Dict:
        """
        Execute a single step of the ReAct loop with retry logic.

        Args:
            task (str): The task to address.
            step (int): Current step number.
            max_iters (int): Maximum allowed steps.
            system_prompt (Optional[str]): System prompt override.
            streaming (bool): Whether to stream responses.

        Returns:
            Dict: Step data (step_number, thought, action, result).
        """
        try:
            await self._notify_observers(StepStartedEvent(
                event_type="StepStarted",
                step_number=step,
                system_prompt=self.history_manager.system_prompt,
                task_description=self.history_manager.task_description
            ))
            for attempt in range(3):
                try:
                    response: str = await self.generate_action(task, self.history_manager.store, step, max_iters, system_prompt, streaming)
                    thought, code = XMLResultHandler.parse_action_response(response)
                    result: ExecutionResult = await self.execute_action(code, step)
                    # Update context variables
                    if result.execution_status == "success" and result.local_variables:
                        self.context_vars.update(
                            {k: v for k, v in result.local_variables.items() if not k.startswith("__") and not callable(v)}
                        )
                    step_data = {"step_number": step, "thought": thought, "action": code, "result": result.dict()}
                    self.history_manager.add(step_data)
                    return step_data
                except LLMCompletionError as e:
                    await self._notify_observers(ErrorOccurredEvent(
                        event_type="ErrorOccurred", error_message=str(e), step_number=step
                    ))
                    raise
                except Exception as e:
                    if not self.error_handler(e, step) or attempt == 2:
                        await self._notify_observers(ErrorOccurredEvent(
                            event_type="ErrorOccurred", error_message=str(e), step_number=step
                        ))
                        raise
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        except Exception as e:
            logger.error(f"Error running step {step}: {e}")
            raise

    async def _finalize_step(self, task: str, step_data: Dict, 
                            success_criteria: Optional[str]) -> Tuple[bool, Dict]:
        """
        Check completion and notify observers for a step.

        Args:
            task (str): The task being solved.
            step_data (Dict): Current step data.
            success_criteria (Optional[str]): Optional success criteria.

        Returns:
            Tuple[bool, Dict]: (is_complete, updated_step_data).
        """
        try:
            result = ExecutionResult(**step_data["result"])
            is_complete, final_answer = await self.is_task_complete(task, self.history_manager.store, result, success_criteria)
            if is_complete and final_answer:
                step_data["result"]["result"] = final_answer  # Update result with final answer
            await self._notify_observers(StepCompletedEvent(
                event_type="StepCompleted", 
                step_number=step_data["step_number"], 
                thought=step_data["thought"], 
                action=step_data["action"], 
                result=step_data["result"],
                is_complete=is_complete, 
                final_answer=final_answer if is_complete else None
            ))
            return is_complete, step_data
        except Exception as e:
            logger.error(f"Error finalizing step {step_data['step_number']}: {e}")
            raise

    async def solve(
        self,
        task: str,
        success_criteria: Optional[str] = None,
        task_goal: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_iterations: Optional[int] = None,
        streaming: bool = False
    ) -> List[Dict]:
        """
        Solve a task using the ReAct framework with persistent memory and explicit goal.

        Args:
            task (str): The task to solve.
            success_criteria (Optional[str]): Criteria for success.
            task_goal (Optional[str]): Explicit goal for the task.
            system_prompt (Optional[str]): System prompt override.
            max_iterations (Optional[int]): Override for max steps.
            streaming (bool): Whether to stream responses.

        Returns:
            List[Dict]: History of steps taken.
        """
        try:
            max_iters: int = max_iterations if max_iterations is not None else self.max_iterations
            self.history_manager.clear()  # Reset task history for new task
            if system_prompt is not None:
                self.history_manager.system_prompt = system_prompt
            self.history_manager.task_description = task
            # Add conversation history to context_vars
            self.context_vars["conversation_history"] = self.conversation_history_manager.get_messages()
            await self._notify_observers(TaskStartedEvent(
                event_type="TaskStarted",
                task_description=task,
                system_prompt=self.history_manager.system_prompt
            ))

            for step in range(1, max_iters + 1):
                try:
                    step_data: Dict = await self._run_step(task, step, max_iters, system_prompt, streaming)
                    is_complete, step_data = await self._finalize_step(task, step_data, success_criteria)
                    if is_complete:
                        await self._notify_observers(TaskCompletedEvent(
                            event_type="TaskCompleted", 
                            final_answer=step_data["result"].get("result"), 
                            reason="success"
                        ))
                        break
                except LLMCompletionError as e:
                    await self._notify_observers(ErrorOccurredEvent(
                        event_type="ErrorOccurred", error_message=str(e), step_number=step
                    ))
                    raise
                except Exception as e:
                    await self._notify_observers(ErrorOccurredEvent(
                        event_type="ErrorOccurred", error_message=str(e), step_number=step
                    ))
                    break

            if not any(step["result"].get("task_status") == "completed" for step in self.history_manager.store):
                await self._notify_observers(TaskCompletedEvent(
                    event_type="TaskCompleted", 
                    final_answer=None,
                    reason="max_iterations_reached" if len(self.history_manager.store) == max_iters else "error"
                ))
            return self.history_manager.store
        except Exception as e:
            logger.error(f"Error solving task: {e}")
            return [{"error": str(e)}]

    async def chat(
        self,
        message: str,
        max_tokens: int = MAX_TOKENS,
        temperature: float = 0.7,
        streaming: bool = True
    ) -> str:
        """
        Handle a single chat interaction using conversation history.

        Args:
            message (str): The user message.
            max_tokens (int): Maximum number of tokens to generate.
            temperature (float): Sampling temperature for LLM response.
            streaming (bool): Whether to stream the response.

        Returns:
            str: The assistant's response.
        """
        try:
            # Construct messages including conversation history
            messages = [
                {"role": "system", "content": self.history_manager.system_prompt or "You are a helpful AI assistant."}
            ]
            # Include only string role and content in conversation history
            for hist_msg in self.conversation_history_manager.get_messages():
                role = str(hist_msg.get("role", ""))
                content = str(hist_msg.get("content", ""))
                messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": str(message)})

            response: str = await litellm_completion(
                model=self.reasoner.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=streaming,
                notify_event=self._notify_observers if streaming else None
            )
            return response.strip()
        except LLMCompletionError as e:
            logger.error(f"Chat failed: {e}")
            await self._notify_observers(ErrorOccurredEvent(
                event_type="ErrorOccurred", error_message=str(e), step_number=1
            ))
            raise
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return f"Error: Unable to process chat request due to {str(e)}"