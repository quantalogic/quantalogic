import asyncio
import time
import types
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from loguru import logger
from quantalogic_pythonbox import AsyncExecutionResult as PythonboxExecutionResult
from quantalogic_pythonbox import execute_async

from quantalogic.tools import Tool

from .conversation_manager import ConversationManager
from .events import (
    ExecutionResult,
    ToolConfirmationRequestEvent,
    ToolExecutionCompletedEvent,
    ToolExecutionErrorEvent,
    ToolExecutionStartedEvent,
)
from .tools_manager import ToolRegistry
from .utils import validate_code

# Global registry to track active executor instances
_active_executor_registry = {}

# Define at module level for simpler imports
class ToolConfirmationDeclinedError(Exception):
    """Error raised when a user declines to execute a tool that requires confirmation."""
    pass

class TaskAbortedError(Exception):
    """Error raised when an entire task should be aborted, not just the current tool.
    This is a more serious error that should terminate the entire solve process.
    """
    pass

ALLOWED_MODULES = ["asyncio", "math", "random", "time","typing","datetime","dataclasses"]

class BaseExecutor(ABC):
    """Abstract base class for execution components."""

    @property
    @abstractmethod
    def allowed_modules(self) -> List[str]:
        """Allowed modules for code execution."""
        pass

    @abstractmethod
    async def execute_action(self, code: str, context_vars: Dict, step: int, timeout: int) -> ExecutionResult:
        pass

    @abstractmethod
    def register_tool(self, tool: Tool) -> None:
        pass


class Executor(BaseExecutor):
    """Manages action execution and context updates with dynamic tool registration."""

    def __init__(self, tools: List[Tool], notify_event: Callable, conversation_manager: ConversationManager,
                 agent_id: str, agent_name: str, config: Optional[Dict[str, Any]] = None, verbose: bool = True,
                 allowed_modules: Optional[List[str]] = ALLOWED_MODULES):
        # Register self in global registry for easier access from shell and other components
        import uuid
        self.executor_id = str(uuid.uuid4())
        self.agent_id = agent_id  # New: Store agent ID
        self.agent_name = agent_name  # New: Store agent name
        self.registry = ToolRegistry()
        for tool in tools:
            self.registry.register(tool)
        self.tools: Dict[tuple[str, str], Tool] = self.registry.tools
        self.notify_event = notify_event
        self.conversation_manager = conversation_manager
        self.config = config or {}
        self.verbose = verbose
        self.tool_namespace = self._build_tool_namespace()
        self._allowed_modules = allowed_modules

    def _build_tool_namespace(self) -> Dict:
        """Build the namespace with tools grouped by toolbox using SimpleNamespace."""
        def wrap_tool_with_confirmation(tool):
            """Wrap a tool with confirmation logic, ensuring it's applied consistently."""
            async def wrapped_tool_with_confirm(**kwargs):
                # Get current step from namespace (for event tracking)
                current_step = self.tool_namespace.get("current_step", None)
                
                # Check for requires_confirmation, similar to _wrap_tool method
                requires_confirmation = False
                
                # Check tool instance first
                if hasattr(tool, 'requires_confirmation'):
                    requires_confirmation = bool(tool.requires_confirmation)
                    logger.debug(f"Tool {tool.name} requires_confirmation={requires_confirmation}")
                    
                # If necessary, also check the underlying function
                if not requires_confirmation and hasattr(tool, '_func'):
                    if hasattr(tool._func, 'requires_confirmation'):
                        requires_confirmation = bool(tool._func.requires_confirmation)
                        tool.requires_confirmation = requires_confirmation
                        logger.debug(f"Propagated requires_confirmation={requires_confirmation} from function to tool {tool.name}")
                
                # If confirmation is required, handle it first
                if requires_confirmation:
                    # Get confirmation message - check in multiple places
                    confirmation_message = ""
                    
                    # 1. Try tool's get_confirmation_message method
                    if hasattr(tool, 'get_confirmation_message') and callable(tool.get_confirmation_message):
                        confirmation_message = tool.get_confirmation_message()
                        logger.debug(f"Got confirmation message via tool.get_confirmation_message() for {tool.name}")
                        
                    # 2. Try tool's confirmation_message attribute
                    elif hasattr(tool, 'confirmation_message'):
                        if callable(tool.confirmation_message):
                            confirmation_message = tool.confirmation_message()
                            logger.debug(f"Got confirmation message via callable tool.confirmation_message for {tool.name}")
                        else:
                            confirmation_message = tool.confirmation_message
                            logger.debug(f"Got confirmation message via static tool.confirmation_message for {tool.name}")
                            
                    # 3. Try the underlying function
                    elif hasattr(tool, '_func') and hasattr(tool._func, 'confirmation_message'):
                        if callable(tool._func.confirmation_message):
                            confirmation_message = tool._func.confirmation_message()
                            logger.debug(f"Got confirmation message via callable _func.confirmation_message for {tool.name}")
                        else:
                            confirmation_message = tool._func.confirmation_message
                            logger.debug(f"Got confirmation message via static _func.confirmation_message for {tool.name}")
                    
                    # Use default if no message is available
                    if not confirmation_message:
                        confirmation_message = f"Confirm execution of '{tool.name}' tool? (yes/no)"
                        logger.debug(f"Using default confirmation message for {tool.name}")
                    
                    # Request confirmation via the established pattern
                    confirm_result = await self.request_confirmation(
                        step_number=current_step,
                        tool_name=f"{tool.toolbox_name or 'default'}.{tool.name}",
                        confirmation_message=confirmation_message,
                        tool_parameters=kwargs
                    )
                    
                    if not confirm_result:
                        # user declined; suppress log and abort task
                        raise TaskAbortedError(f"User declined to execute tool {tool.name} - aborting entire task")
                
                # Now handle event notification if in verbose mode
                if self.verbose:
                    parameters_summary = {
                        k: str(v)[:100] + "..." if len(str(v)) > 100 else str(v) for k, v in kwargs.items()
                    }
                    await self.notify_event(
                        ToolExecutionStartedEvent(
                            event_type="ToolExecutionStarted",
                            agent_id=self.agent_id,  # New
                            agent_name=self.agent_name,  # New
                            step_number=current_step,
                            tool_name=f"{tool.toolbox_name or 'default'}.{tool.name}",
                            parameters_summary=parameters_summary,
                        )
                    )
                
                # Execute the tool
                try:
                    result = await tool.async_execute(**kwargs)
                    
                    # Handle completion notification if in verbose mode
                    if self.verbose:
                        result_summary = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                        await self.notify_event(
                            ToolExecutionCompletedEvent(
                                event_type="ToolExecutionCompleted",
                                agent_id=self.agent_id,  # New
                                agent_name=self.agent_name,  # New
                                step_number=current_step,
                                tool_name=f"{tool.toolbox_name or 'default'}.{tool.name}",
                                result_summary=result_summary,
                            )
                        )
                    return result
                except Exception as e:
                    # Handle error notification if in verbose mode
                    if self.verbose:
                        await self.notify_event(
                            ToolExecutionErrorEvent(
                                event_type="ToolExecutionError",
                                agent_id=self.agent_id,  # New
                                agent_name=self.agent_name,  # New
                                step_number=current_step,
                                tool_name=f"{tool.toolbox_name or 'default'}.{tool.name}",
                                error=str(e)
                            )
                        )
                    raise

            return wrapped_tool_with_confirm

        # Build toolboxes with wrapped tools (with confirmation logic)
        toolboxes = {}
        for (toolbox_name, tool_name), tool in self.tools.items():
            if toolbox_name not in toolboxes:
                toolboxes[toolbox_name] = types.SimpleNamespace()
            
            # Always use the wrapper with confirmation checks
            setattr(toolboxes[toolbox_name], tool_name, wrap_tool_with_confirmation(tool))

        return {
            "asyncio": asyncio,
            "context_vars": {},
            **toolboxes,
        }

    @property
    def allowed_modules(self) -> List[str]:
        return self._allowed_modules

    def register_tool(self, tool: Tool) -> None:
        """Register a new tool dynamically at runtime."""
        self.registry.register(tool)
        key = (tool.toolbox_name or "default", tool.name)
        self.tools[key] = tool
        toolbox_name = tool.toolbox_name or "default"
        if toolbox_name not in self.tool_namespace:
            self.tool_namespace[toolbox_name] = types.SimpleNamespace()
        setattr(self.tool_namespace[toolbox_name], tool.name, 
                self._wrap_tool(tool) if self.verbose else tool.async_execute)

    def _wrap_tool(self, tool: Tool):
        """Wrap a tool function to handle execution events and confirmation (internal use)."""
        async def wrapped_tool(**kwargs):
            current_step = self.tool_namespace.get("current_step", None)
            parameters_summary = {
                k: str(v)[:100] + "..." if len(str(v)) > 100 else str(v) for k, v in kwargs.items()
            }
            
            # Log all tool attributes for debugging
            tool_dir = dir(tool)
            logger.debug(f"Tool attributes for {tool.name}: {tool_dir}")
            
            # Force-check the original function for requires_confirmation
            # This handles cases where the attribute might not have been properly transferred during tool creation
            requires_confirmation = False
            
            # Check tool instance first
            if hasattr(tool, 'requires_confirmation'):
                requires_confirmation = bool(tool.requires_confirmation)
                logger.debug(f"Tool {tool.name} requires_confirmation={requires_confirmation}")
                
            # If necessary, also check the underlying function for the attribute
            if not requires_confirmation and hasattr(tool, '_func'):
                if hasattr(tool._func, 'requires_confirmation'):
                    requires_confirmation = bool(tool._func.requires_confirmation)
                    # Propagate the attribute to the tool for future use
                    tool.requires_confirmation = requires_confirmation
                    logger.debug(f"Propagated requires_confirmation={requires_confirmation} from function to tool {tool.name}")
            
            # Check if confirmation is required
            if requires_confirmation:
                # Get confirmation message - check in multiple places to ensure we get it
                confirmation_message = ""
                
                # 1. Try tool's get_confirmation_message method
                if hasattr(tool, 'get_confirmation_message') and callable(tool.get_confirmation_message):
                    confirmation_message = tool.get_confirmation_message()
                    logger.debug(f"Got confirmation message via tool.get_confirmation_message() for {tool.name}")
                    
                # 2. Try tool's confirmation_message attribute
                elif hasattr(tool, 'confirmation_message'):
                    if callable(tool.confirmation_message):
                        confirmation_message = tool.confirmation_message()
                        logger.debug(f"Got confirmation message via callable tool.confirmation_message for {tool.name}")
                    else:
                        confirmation_message = tool.confirmation_message
                        logger.debug(f"Got confirmation message via static tool.confirmation_message for {tool.name}")
                        
                # 3. Try the underlying function if tool has _func attribute
                elif hasattr(tool, '_func') and hasattr(tool._func, 'confirmation_message'):
                    if callable(tool._func.confirmation_message):
                        confirmation_message = tool._func.confirmation_message()
                        # Propagate to tool for future use
                        tool.confirmation_message = tool._func.confirmation_message
                        logger.debug(f"Got confirmation message via callable _func.confirmation_message for {tool.name}")
                    else:
                        confirmation_message = tool._func.confirmation_message
                        # Propagate to tool for future use
                        tool.confirmation_message = tool._func.confirmation_message
                        logger.debug(f"Got confirmation message via static _func.confirmation_message for {tool.name}")
                
                # Use default if no message is available
                if not confirmation_message:
                    confirmation_message = f"Confirm execution of '{tool.name}' tool? (yes/no)"
                    logger.debug(f"Using default confirmation message for {tool.name}")
                
                # Create a confirmation event and wait for response
                confirm_result = await self.request_confirmation(
                    step_number=current_step,
                    tool_name=f"{tool.toolbox_name or 'default'}.{tool.name}",
                    confirmation_message=confirmation_message,
                    tool_parameters=kwargs
                )
                
                # If not confirmed, cancel execution
                if not confirm_result:
                    await self.notify_event(
                        ToolExecutionErrorEvent(
                            event_type="ToolExecutionError",
                            agent_id=self.agent_id,  # New
                            agent_name=self.agent_name,  # New
                            step_number=current_step,
                            tool_name=f"{tool.toolbox_name or 'default'}.{tool.name}",
                            error="Operation cancelled by user"
                        )
                    )
                    return "Operation cancelled by user"
            
            # Proceed with normal tool execution
            await self.notify_event(
                ToolExecutionStartedEvent(
                    event_type="ToolExecutionStarted",
                    agent_id=self.agent_id,  # New
                    agent_name=self.agent_name,  # New
                    step_number=current_step,
                    tool_name=f"{tool.toolbox_name or 'default'}.{tool.name}",
                    parameters_summary=parameters_summary,
                )
            )
            try:
                result = await tool.async_execute(**kwargs)
                result_summary = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                await self.notify_event(
                    ToolExecutionCompletedEvent(
                        event_type="ToolExecutionCompleted",
                        agent_id=self.agent_id,  # New
                        agent_name=self.agent_name,  # New
                        step_number=current_step,
                        tool_name=f"{tool.toolbox_name or 'default'}.{tool.name}",
                        result_summary=result_summary,
                    )
                )
                return result
            except Exception as e:
                await self.notify_event(
                    ToolExecutionErrorEvent(
                        event_type="ToolExecutionError",
                        agent_id=self.agent_id,  # New
                        agent_name=self.agent_name,  # New
                        step_number=current_step,
                        tool_name=f"{tool.toolbox_name or 'default'}.{tool.name}",
                        error=str(e)
                    )
                )
                raise

        return wrapped_tool

    async def request_confirmation(self, step_number: int, tool_name: str, confirmation_message: str, tool_parameters: Dict[str, Any]) -> bool:
        """Request user confirmation for a tool execution.
        
        Args:
            step_number: The current step number
            tool_name: Name of the tool requiring confirmation
            confirmation_message: The confirmation message to display
            tool_parameters: Tool parameters (for display)
            
        Returns:
            bool: True if confirmed, False if declined
        """
        logger.debug("===== CONFIRMATION REQUEST START =====")
        logger.debug(f"Requesting confirmation for tool: {tool_name}")
        logger.debug(f"Step number: {step_number}")
        logger.debug(f"Confirmation message: {confirmation_message}")
        logger.debug(f"Parameters: {tool_parameters}")
        
        # Create a future for the confirmation response
        confirmation_future = asyncio.Future()
        
        # Create and emit a confirmation request event
        event = ToolConfirmationRequestEvent(
            event_type="ToolConfirmationRequest",
            agent_id=self.agent_id,  # New
            agent_name=self.agent_name,  # New
            step_number=step_number,
            tool_name=tool_name,
            confirmation_message=confirmation_message,
            parameters_summary=tool_parameters,
            confirmation_future=confirmation_future
        )
        
        # Emit the event and start waiting for a response
        logger.debug("Emitting ToolConfirmationRequestEvent")
        await self.notify_event(event)
        logger.debug("Event emitted, awaiting future for response")
        
        # Wait for user response
        try:
            logger.debug("Waiting for confirmation response...")
            start_time = time.time()
            
            # Log the current event loop and pending tasks for debugging
            loop = asyncio.get_event_loop()
            logger.debug(f"Current event loop: {loop}, running={loop.is_running()}")
            
            # Log pending tasks for debugging deadlocks
            pending_tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
            logger.debug(f"Number of pending tasks before waiting: {len(pending_tasks)}")
            
            # Set a reasonable timeout to prevent indefinite hangs
            logger.debug("About to await future with timeout...")
            confirmation_timeout = 60  # 1 minute timeout
            result = await asyncio.wait_for(confirmation_future, timeout=confirmation_timeout)
            
            # Log state immediately after receiving result
            elapsed = time.time() - start_time
            logger.debug(f"Received confirmation response after {elapsed:.2f}s: {result}")
            logger.debug(f"Future state after result: done={confirmation_future.done()}")
            
            logger.debug("===== CONFIRMATION REQUEST END =====")
            return result
        except TimeoutError:
            logger.warning(f"Confirmation timed out for tool {tool_name} at step {step_number}")
            # Set the future to False to indicate timeout
            if not confirmation_future.done():
                confirmation_future.set_result(False)
            logger.debug("===== CONFIRMATION REQUEST END (TIMEOUT) =====")
            return False
        except Exception as e:
            logger.error(f"Unexpected error while waiting for confirmation: {e}")
            # Set the future to False to indicate error
            if not confirmation_future.done():
                confirmation_future.set_result(False)
            logger.debug("===== CONFIRMATION REQUEST END (ERROR) =====")
            return False

    async def execute_tool(self, tool_name, step_number=None, **kwargs):
        """Execute a tool with the given parameters."""
        logger.debug(f"Executing tool: {tool_name} with parameters: {kwargs}")

        tool = self.tools_registry.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool {tool_name} not found")
            
        # Execute the tool and handle any errors
        try:
            result = await tool.async_execute(**kwargs)
            return result
        except Exception:
            raise

    class ToolExecutionResult:
        """Tool execution result."""
        def __init__(self, tool_name: str, parameters: Dict, result: Any, success: bool, error: str = None):
            self.tool_name = tool_name
            self.parameters = parameters
            self.result = result
            self.success = success
            self.error = error

    async def execute_action(self, code: str, context_vars: Dict, step: int, timeout: int = 300) -> ExecutionResult:
        """Execute the generated code and return the result with local variables, setting the step number."""
        self.tool_namespace["context_vars"] = context_vars
        self.tool_namespace["current_step"] = step
        timeout = self.config.get("timeout", timeout)  # Use config timeout if provided
        if not validate_code(code):
            logger.error(f"Invalid code at step {step}: lacks async main()")
            return ExecutionResult(
                execution_status="error",
                error="Code lacks async main()",
                execution_time=0.0
            )

        try:
            result: PythonboxExecutionResult = await execute_async(
                code=code,
                timeout=timeout,
                entry_point="main",
                allowed_modules=self.allowed_modules,
                namespace=self.tool_namespace,
                ignore_typing=True
            )
            if result.error:
                err_str = str(result.error)
                # suppress logging for user-declined aborts
                if 'User declined to execute tool' not in err_str:
                    logger.error(f"Execution error at step {step}: {result.error}")
                return ExecutionResult(
                    execution_status="error",
                    error=err_str,
                    execution_time=result.execution_time or 0.0
                )
            task_result = result.result
            if not isinstance(task_result, dict) or 'status' not in task_result or 'result' not in task_result:
                logger.error(f"Invalid return format at step {step}: expected dict with 'status' and 'result'")
                return ExecutionResult(
                    execution_status="error",
                    error="main() did not return a valid dictionary with 'status' and 'result'",
                    execution_time=result.execution_time or 0.0
                )
            logger.info(f"Execution successful at step {step}, task status: {task_result['status']}")
            return ExecutionResult(
                execution_status="success",
                task_status=task_result['status'],
                result=str(task_result['result']),
                next_step=task_result.get('next_step'),
                execution_time=result.execution_time or 0.0,
                local_variables={
                    k: v for k, v in result.local_variables.items()
                    if not k.startswith("__") and not callable(v)
                }
            )
        except Exception as e:
            logger.error(f"Unexpected execution error at step {step}: {e}")
            return ExecutionResult(
                execution_status="error",
                error=f"Execution error: {str(e)}",
                execution_time=0.0
            )