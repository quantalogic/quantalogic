"""Core implementation of the ReAct framework for reasoning and acting."""

import asyncio
import inspect
import time
from typing import Callable, Dict, List, Optional, Tuple

from loguru import logger
from nanoid import generate

from quantalogic.tools import Tool

from .completion_evaluator import DefaultCompletionEvaluator
from .conversation_manager import ConversationManager
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
from .executor import BaseExecutor, Executor, TaskAbortedError
from .llm_util import LLMCompletionError, litellm_completion
from .message import Message
from .reasoner import BaseReasoner, Reasoner
from .tools_manager import ToolRegistry
from .working_memory import WorkingMemory
from .xml_utils import XMLResultHandler

MAX_HISTORY_TOKENS = 64 * 1024
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
        working_memory: Optional[WorkingMemory] = None,
        conversation_manager: Optional[ConversationManager] = None,
        error_handler: Optional[Callable[[Exception, int], bool]] = None,
        temperature: float = 0.7,  # Added temperature parameter
        agent_id: str = None,  # New: Agent's unique ID
        agent_name: str = None  # New: Agent's name
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
            working_memory (Optional[WorkingMemory]): Custom working memory manager.
            conversation_manager (Optional[ConversationManager]): Custom conversation manager.
            error_handler (Optional[Callable[[Exception, int], bool]]): Error handler callback.
            temperature (float): Temperature for language model generation (default: 0.7).
            agent_id (str): Unique identifier for the agent.
            agent_name (str): Name of the agent.
        """
        # Ensure agent_id and agent_name are always valid strings
        self.agent_id = agent_id or generate()
        self.agent_name = agent_name or f"agent_{self.agent_id[:8]}"
        self.temperature = temperature  # Store temperature
        self.tool_registry = tool_registry or ToolRegistry()
        for tool in tools:
            self.tool_registry.register(tool)
        self.reasoner: BaseReasoner = reasoner or Reasoner(
            model,
            self.tool_registry.get_tools(),
            temperature=self.temperature,
            agent_id=self.agent_id,
            agent_name=self.agent_name
        )
        self.executor: BaseExecutor = executor or Executor(
            self.tool_registry.get_tools(), self._notify_observers, conversation_manager, agent_id=self.agent_id, agent_name=self.agent_name
        )
        self.max_iterations: int = max_iterations
        self.max_history_tokens: int = max_history_tokens
        self.working_memory: WorkingMemory = working_memory or WorkingMemory(
            max_tokens=max_history_tokens, system_prompt=system_prompt, task_description=task_description
        )
        self.conversation_history_manager: ConversationManager = (
            conversation_manager or ConversationManager(max_tokens=max_history_tokens)
        )
        self.context_vars: Dict = {}
        self._observers: List[Tuple[Callable, List[str]]] = []
        self.error_handler = error_handler or (lambda e, step: False)  # Default: no retry
        self.completion_evaluator = DefaultCompletionEvaluator()

    def add_observer(self, observer: Callable, event_types: List[str]) -> "CodeActAgent":
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

    async def generate_action(
        self, task: str, step: int, max_iterations: int, system_prompt: Optional[str] = None, streaming: bool = False
    ) -> str:
        """
        Generate an action using the Reasoner, passing available variables.

        Args:
            task (str): The task to address.
            step (int): Current step number.
            max_iterations (int): Maximum allowed steps.
            system_prompt (Optional[str]): Override system prompt (optional).
            streaming (bool): Whether to stream the response.

        Returns:
            str: Generated action in XML format.
        """
        try:
            step_history_str: str = self.working_memory.format_history(max_iterations)
            available_vars: List[str] = list(self.context_vars.keys())
            # Convert Message or dict objects to dicts for reasoning
            history_msgs = self.conversation_history_manager.get_history()
            conversation_history: List[Dict[str, str]] = []
            for msg in history_msgs:
                if isinstance(msg, Message):
                    conversation_history.append({"role": msg.role, "content": msg.content, "nanoid": msg.nanoid})
                elif isinstance(msg, dict):
                    conversation_history.append({"role": msg.get("role"), "content": msg.get("content"), "nanoid": msg.get("nanoid")})
                else:
                    raise ValueError(f"Invalid message type {type(msg)} in history")
            start: float = time.perf_counter()
            response: str = await self.reasoner.generate_action(
                task,
                step_history_str,
                step,
                max_iterations,
                system_prompt or self.working_memory.system_prompt,
                self._notify_observers,
                streaming=streaming,
                available_vars=available_vars,
                allowed_modules=self.executor.allowed_modules,
                conversation_history=conversation_history,
            )
            thought, code = XMLResultHandler.parse_action_response(response)
            gen_time: float = time.perf_counter() - start
            await self._notify_observers(
                ThoughtGeneratedEvent(
                    event_type="ThoughtGenerated",
                    agent_id=self.agent_id,  # New
                    agent_name=self.agent_name,  # New
                    step_number=step,
                    thought=thought,
                    generation_time=gen_time
                )
            )
            await self._notify_observers(
                ActionGeneratedEvent(
                    event_type="ActionGenerated",
                    agent_id=self.agent_id,  # New
                    agent_name=self.agent_name,  # New
                    step_number=step,
                    action_code=code,
                    generation_time=gen_time
                )
            )
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
            await self._notify_observers(
                ActionExecutedEvent(
                    event_type="ActionExecuted",
                    agent_id=self.agent_id,  # New
                    agent_name=self.agent_name,  # New
                    step_number=step,
                    result=result,
                    execution_time=execution_time
                )
            )
            return result
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            raise

    async def _run_step(
        self, task: str, step: int, max_iters: int, system_prompt: Optional[str] = None, streaming: bool = False,
        task_context: Optional[Dict] = None
    ) -> Dict:
        """
        Execute a single step of the ReAct loop with retry logic.

        Args:
            task: Description of the task to be performed.
            step: Number indicating the current step.
            max_iters: Maximum number of iterations.
            system_prompt: Optional system prompt override.
            streaming: Whether to stream the response.
            task_context: Optional dictionary to track task-specific state across steps.

        Returns:
            Dict: Step data (step_number, thought, action, result).
        """
        try:
            await self._notify_observers(
                StepStartedEvent(
                    event_type="StepStarted",
                    agent_id=self.agent_id,  # New
                    agent_name=self.agent_name,  # New
                    step_number=step,
                    system_prompt=self.working_memory.system_prompt,
                    task_description=self.working_memory.task_description,
                    task_id=task_context.get("task_id")
                )
            )
            for attempt in range(3):
                try:
                    response: str = await self.generate_action(task, step, max_iters, system_prompt, streaming)
                    thought, code = XMLResultHandler.parse_action_response(response)
                    result: ExecutionResult = await self.execute_action(code, step)
                    # Check for user-declined confirmation and raise TaskAbortedError
                    if result.execution_status == "error" and "User declined to execute tool" in result.error:
                        raise TaskAbortedError(result.error)
                    # Update context variables
                    if result.execution_status == "success" and result.local_variables:
                        new_vars = {
                            k: v
                            for k, v in result.local_variables.items()
                            if not k.startswith("__") and not callable(v)
                        }
                        self.context_vars.update(new_vars)
                        logger.debug(f"Step {step}: Updated context_vars with {new_vars}")
                    step_data = {"step_number": step, "thought": thought, "action": code, "result": result.dict()}
                    self.working_memory.add(step_data)
                    return step_data
                except LLMCompletionError as e:
                    await self._notify_observers(
                        ErrorOccurredEvent(
                            event_type="ErrorOccurred",
                            agent_id=self.agent_id,
                            agent_name=self.agent_name,
                            error_message=str(e),
                            step_number=step,
                            task_id=task_context.get("task_id")
                        )
                    )
                    raise
                except Exception as e:
                    err_str = str(e)
                    if 'TaskAbortedError' in err_str and 'User declined to execute tool' in err_str:
                        # Don't log as error for normal confirmation declines
                        logger.debug(f"User declined confirmation at step {step}")
                    elif 'TaskAbortedError' not in err_str:
                        logger.error(f"Error running step {step}: {e}")
                    raise
        except Exception as e:
            err_str = str(e)
            if 'TaskAbortedError' in err_str and 'User declined to execute tool' in err_str:
                # Don't log as error for normal confirmation declines
                logger.debug(f"User declined confirmation at step {step}")
            elif 'TaskAbortedError' not in err_str:
                logger.error(f"Error running step {step}: {e}")
            raise

    async def _finalize_step(self, task: str, step_data: Dict, success_criteria: Optional[str], task_id: Optional[str] = None) -> Tuple[bool, Dict]:
        """
        Check completion and notify observers for a step.

        Args:
            task (str): The task being solved.
            step_data (Dict): Current step data.
            success_criteria (Optional[str]): Optional success criteria.
            task_id (Optional[str]): Unique ID to group related events.

        Returns:
            Tuple[bool, Dict]: (is_complete, updated_step_data).
        """
        try:
            result = ExecutionResult(**step_data["result"])
            formatted_history = self.working_memory.format_history(self.max_iterations)
            is_complete, final_answer = await self.completion_evaluator.evaluate_completion(
                task=task,
                formatted_history=formatted_history,
                result=result,
                success_criteria=success_criteria,
                model=self.reasoner.model,
                temperature=self.temperature,
            )
            if is_complete and final_answer:
                step_data["result"]["result"] = final_answer  # Update result with final answer
            await self._notify_observers(
                StepCompletedEvent(
                    event_type="StepCompleted",
                    agent_id=self.agent_id,  # New
                    agent_name=self.agent_name,  # New
                    step_number=step_data["step_number"],
                    thought=step_data["thought"],
                    action=step_data["action"],
                    result=step_data["result"],
                    is_complete=is_complete,
                    final_answer=final_answer if is_complete else None,
                    task_id=task_id
                )
            )
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
        streaming: bool = False,
        task_id: Optional[str] = None,
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
            task_id (Optional[str]): Unique ID to group related events. If None, a default ID will be generated.

        Returns:
            List[Dict]: History of steps taken.
        """
        try:
            # Generate a default task_id if none is provided
            if task_id is None:
                task_id = generate(size=21)
                
            # Create a task-specific context dictionary to track this specific task's state
            # This avoids using instance variables that could interfere with other concurrent tasks
            task_context = {
                "aborted": False,
                "abort_message": "",
                "abort_step": None,
                "task_id": task_id  # Store the task_id in the context
            }
            
            max_iters: int = max_iterations if max_iterations is not None else self.max_iterations
            self.working_memory.clear()  # Reset working memory for a new task
            self.context_vars.clear()  # Clear previous context variables
            if system_prompt is not None:
                self.working_memory.system_prompt = system_prompt
            self.working_memory.task_description = task
            # Initialize context_vars with conversation history and previous task variables
            # Log conversation history
            logger.debug(f"Conversation history: {self.conversation_history_manager.get_history()}")
            self.context_vars["conversation_history"] = [
                {"role": message.role, "content": message.content, "nanoid": message.nanoid}
                for message in self.conversation_history_manager.get_history()
            ]
            # Retain non-private, non-callable variables from previous tasks
            previous_vars = {k: v for k, v in self.context_vars.items() if not k.startswith("__") and not callable(v)}
            logger.debug(f"Starting task with context_vars: {previous_vars}")
            await self._notify_observers(
                TaskStartedEvent(
                    event_type="TaskStarted",
                    agent_id=self.agent_id,  # New
                    agent_name=self.agent_name,  # New
                    task_description=task,
                    system_prompt=self.working_memory.system_prompt,
                    task_id=task_id
                )
            )

            # Main task execution loop
            for step in range(1, max_iters + 1):
                # Check if we should abort all further steps (task was aborted)
                if task_context["aborted"]:
                    logger.debug(f"Breaking out of the solve loop due to task abortion at step {task_context['abort_step']}")
                    break
                    
                try:
                    step_data: Dict = await self._run_step(task, step, max_iters, system_prompt, streaming, task_context)
                    is_complete, step_data = await self._finalize_step(task, step_data, success_criteria, task_id=task_id)
                    if is_complete:
                        await self._notify_observers(
                            TaskCompletedEvent(
                                event_type="TaskCompleted",
                                agent_id=self.agent_id,  # New
                                agent_name=self.agent_name,  # New
                                final_answer=step_data["result"].get("result"),
                                reason="success",
                                task_id=task_id
                            )
                        )
                        break
                except TaskAbortedError as e:
                    # Special handling for TaskAbortedError - complete immediate termination
                    logger.debug(f"Task execution aborted by user: {e}")
                    
                    # Set the task-specific context to mark this task as aborted
                    task_context["aborted"] = True
                    task_context["abort_message"] = f"Task aborted by user at step {step} - confirmation declined"
                    task_context["abort_step"] = step
                    logger.debug(f"Task context marked as aborted - {task_context['abort_message']}")
                    
                    # Break the loop immediately to prevent further steps
                    break
                except LLMCompletionError as e:
                    await self._notify_observers(
                        ErrorOccurredEvent(
                            event_type="ErrorOccurred",
                            agent_id=self.agent_id,  # New
                            agent_name=self.agent_name,  # New
                            error_message=str(e),
                            step_number=step,
                            task_id=task_id
                        )
                    )
                    raise
                except Exception as e:
                    await self._notify_observers(
                        ErrorOccurredEvent(
                            event_type="ErrorOccurred",
                            agent_id=self.agent_id,  # New
                            agent_name=self.agent_name,  # New
                            error_message=str(e),
                            step_number=step,
                            task_id=task_id
                        )
                    )
                    break

            # Handle final task status
            if task_context["aborted"]:
                # Return the history with an explicit abort message
                return [
                    {
                        "step_number": step.step_number,
                        "thought": step.thought,
                        "action": step.action,
                        "result": step.result.dict() if hasattr(step.result, 'dict') else {},
                        "aborted": True if task_context["abort_step"] and step.step_number == task_context["abort_step"] else False
                    }
                    for step in self.working_memory.store
                ] + [{"error": task_context["abort_message"], "aborted": True, "task_status": "aborted"}]
            elif not any(step.result.task_status == "completed" for step in self.working_memory.store):
                await self._notify_observers(
                    TaskCompletedEvent(
                        event_type="TaskCompleted",
                        agent_id=self.agent_id,  # New
                        agent_name=self.agent_name,  # New
                        final_answer=None,
                        reason="max_iterations_reached" if len(self.working_memory.store) == max_iters else "error",
                        task_id=task_id
                    )
                )
            return [
                {
                    "step_number": step.step_number,
                    "thought": step.thought,
                    "action": step.action,
                    "result": step.result.dict(),
                }
                for step in self.working_memory.store
            ]
        except TaskAbortedError as e:
            # Special handling for a confirmed task abortion
            logger.debug(f"Task execution aborted by user: {e}")
            return [{
                "error": "Task aborted by user - confirmation was declined",
                "status": "aborted",
                "reason": "user_confirmation_declined" 
            }]
        except Exception as e:
            logger.error(f"Error solving task: {e}")
            return [{"error": str(e)}]

    async def chat(
        self,
        message: str,
        max_tokens: int = MAX_TOKENS,
        temperature: Optional[float] = None,  # Allow override
        streaming: bool = True,
        task_id: Optional[str] = None,
    ) -> str:
        """
        Handle a single chat interaction using conversation history.

        Args:
            message (str): The user message.
            max_tokens (int): Maximum number of tokens to generate.
            temperature (Optional[float]): Sampling temperature for LLM response (defaults to instance temperature).
            streaming (bool): Whether to stream the response.
            task_id (Optional[str]): Unique ID to group related events. If None, a default ID will be generated.

        Returns:
            str: The assistant's response.
        """
        try:
            # Generate a default task_id if none is provided
            if task_id is None:
                task_id = generate(size=21)
                
            # Construct messages including conversation history
            messages = [
                {"role": "system", "content": self.working_memory.system_prompt or "You are a helpful AI assistant."}
            ]
            # Include only string role and content in conversation history
            for hist_msg in self.conversation_history_manager.get_history():
                role = str(hist_msg.role)
                content = str(hist_msg.content)
                messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": str(message)})

            response: str = await litellm_completion(
                model=self.reasoner.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature if temperature is not None else self.temperature,
                stream=streaming,
                notify_event=self._notify_observers if streaming else None,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                task_id=task_id
            )
            return response.strip()
        except LLMCompletionError as e:
            logger.error(f"Chat failed: {e}")
            await self._notify_observers(
                ErrorOccurredEvent(
                    event_type="ErrorOccurred",
                    agent_id=self.agent_id,  # New
                    agent_name=self.agent_name,  # New
                    error_message=str(e),
                    step_number=1,
                    task_id=task_id
                )
            )
            raise
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return f"Error: Unable to process chat request due to {str(e)}"

    def set_temperature(self, temperature: float) -> None:
        """Update the temperature for the agent and its reasoner."""
        self.temperature = temperature
        if hasattr(self.reasoner, "temperature"):
            self.reasoner.temperature = temperature