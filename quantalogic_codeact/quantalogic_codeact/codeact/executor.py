import asyncio
import time
import types
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from loguru import logger
from nanoid import generate
from quantalogic_pythonbox import AsyncExecutionResult as PythonboxExecutionResult
from quantalogic_pythonbox import execute_async

from quantalogic.tools import Tool

from .conversation_manager import ConversationManager
from .events import (
    ExecutionResult,
    ToolConfirmationRequestEvent,
    ToolConfirmationResponseEvent,
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

    def __init__(self, tools: List[Tool], notify_event: Callable, conversation_manager: ConversationManager, config: Optional[Dict[str, Any]] = None, verbose: bool = True, allowed_modules: Optional[List[str]] = ALLOWED_MODULES):
        # Register self in global registry for easier access from shell and other components
        import uuid
        self.executor_id = str(uuid.uuid4())
        _active_executor_registry[self.executor_id] = self
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
        self._confirmation_future = None
        self._pending_confirmations = {}

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
                            tool.confirmation_message = tool._func.confirmation_message
                            logger.debug(f"Got confirmation message via callable _func.confirmation_message for {tool.name}")
                        else:
                            confirmation_message = tool._func.confirmation_message
                            tool.confirmation_message = tool._func.confirmation_message
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
                        logger.info(f"User declined to execute tool {tool.name}")
                        # Raise TaskAbortedError instead to signal complete task termination
                        # This will ensure the entire task workflow is stopped, not just this tool
                        raise TaskAbortedError(f"User declined to execute tool {tool.name} - aborting entire task")
                
                # Now handle event notification if in verbose mode
                if self.verbose:
                    parameters_summary = {
                        k: str(v)[:100] + "..." if len(str(v)) > 100 else str(v) for k, v in kwargs.items()
                    }
                    await self.notify_event(
                        ToolExecutionStartedEvent(
                            event_type="ToolExecutionStarted",
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
        # Generate a unique confirmation ID
        confirmation_id = generate(size=12)  # Using nanoid for a short, unique ID
        
        logger.debug("===== CONFIRMATION REQUEST START =====")
        logger.debug(f"Confirmation ID: {confirmation_id}")
        logger.debug(f"Requesting confirmation for tool: {tool_name}")
        logger.debug(f"Step number: {step_number}")
        logger.debug(f"Confirmation message: {confirmation_message}")
        logger.debug(f"Parameters: {tool_parameters}")
        
        # Store the confirmation with its ID
        self._pending_confirmations[confirmation_id] = asyncio.Future()
        
        # Create and emit a confirmation request event
        event = ToolConfirmationRequestEvent(
            event_type="ToolConfirmationRequest",
            step_number=step_number,
            tool_name=tool_name,
            confirmation_message=confirmation_message,
            parameters_summary=tool_parameters,
            confirmation_id=confirmation_id
        )
        
        # Emit the event and start waiting for a response
        logger.debug("Emitting ToolConfirmationRequestEvent")
        await self.notify_event(event)
        logger.debug("Event emitted, setting up future for response")
        
        # Store the step and tool for confirmation response correlation
        self._pending_confirmations[(step_number, tool_name)] = asyncio.Future()
        
        # Wait for user response
        try:
            logger.debug("Waiting for confirmation response...")
            start_time = time.time()
            # Check if confirmation_id exists before waiting
            if confirmation_id not in self._pending_confirmations:
                logger.error(f"Confirmation ID {confirmation_id} not found in _pending_confirmations before waiting")
                return False
            
            # Get the future we'll wait on
            future = self._pending_confirmations[confirmation_id]
            logger.debug(f"Future to wait on: {future}, done={future.done()}")
            
            # Log the current event loop and pending tasks for debugging
            loop = asyncio.get_event_loop()
            logger.debug(f"Current event loop: {loop}, running={loop.is_running()}")
            
            # Log pending tasks for debugging deadlocks
            pending_tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
            logger.debug(f"Number of pending tasks before waiting: {len(pending_tasks)}")
            
            # Set a reasonable timeout to prevent indefinite hangs
            logger.debug("About to await future with timeout...")
            # Using a shorter timeout value for better responsiveness
            confirmation_timeout = 60  # 1 minute is more reasonable than 5 minutes
            result = await asyncio.wait_for(future, timeout=confirmation_timeout)
            
            # Log state immediately after receiving result
            elapsed = time.time() - start_time
            logger.debug(f"Received confirmation response after {elapsed:.2f}s: {result}")
            logger.debug(f"Future state after result: done={future.done()}")
            
            logger.debug("===== CONFIRMATION REQUEST END =====")
            return result
        except TimeoutError:
            logger.warning(f"Confirmation timed out for ID {confirmation_id} ({tool_name} at step {step_number})")
            # Clean up the pending confirmation
            if confirmation_id in self._pending_confirmations:
                logger.debug(f"Cleaning up timed-out confirmation with ID {confirmation_id}")
                del self._pending_confirmations[confirmation_id]
            # Emit an event indicating the timeout for UI feedback
            logger.debug("Emitting timeout response event")
            try:
                await self.notify_event(
                    ToolConfirmationResponseEvent(
                        event_type="ToolConfirmationResponse",
                        step_number=step_number,
                        tool_name=tool_name,
                        confirmed=False,  # Timeout is treated as decline
                        confirmation_id=confirmation_id
                    )
                )
            except Exception as e:
                logger.error(f"Error emitting timeout response event: {e}")
            logger.debug("===== CONFIRMATION REQUEST END (TIMEOUT) =====")
            return False
        except KeyError as e:
            logger.error(f"KeyError accessing pending confirmation: {e}")
            logger.debug("===== CONFIRMATION REQUEST END (ERROR) =====")
            return False
        except Exception as e:
            logger.error(f"Unexpected error while waiting for confirmation: {e}")
            logger.debug("===== CONFIRMATION REQUEST END (ERROR) =====")
            return False
    
    async def handle_confirmation_response(self, confirmed: bool, step_number: int, tool_name: str, confirmation_id: str = None):
        """Handle a confirmation response from a user.
        
        Args:
            confirmed: Whether the user confirmed the action
            step_number: The step number the confirmation belongs to
            tool_name: The name of the tool being confirmed
            confirmation_id: The unique ID for this confirmation request (preferred method)
        """
        logger.debug("===== CONFIRMATION RESPONSE START =====")
        logger.debug(f"Handling confirmation response for: {tool_name}")
        logger.debug(f"Step number: {step_number}")
        logger.debug(f"Confirmation ID: {confirmation_id}")
        logger.debug(f"Confirmed: {confirmed}")
        logger.debug(f"Current pending confirmations: {list(self._pending_confirmations.keys())}")
        
        # If we have a confirmation_id (preferred method), use it directly
        if confirmation_id and confirmation_id in self._pending_confirmations:
            logger.debug(f"Found pending confirmation with ID: {confirmation_id}, resolving future")
            # Get the future
            future = self._pending_confirmations[confirmation_id]
            logger.debug(f"Got future object: {future}, done={future.done()}")
            
            # Resolve the future with the confirmation result
            logger.debug(f"Setting result to {confirmed}")
            future.set_result(confirmed)
            logger.debug(f"Future state after set_result: done={future.done()}")
            
            # Remove the pending confirmation
            del self._pending_confirmations[confirmation_id]
            logger.debug(f"Removed confirmation from pending confirmations. Remaining keys: {list(self._pending_confirmations.keys())}")
            
            success = True
        else:
            # For backward compatibility, attempt to find by step number and tool name
            logger.debug("No confirmation_id provided or not found, falling back to legacy method")
            all_keys = list(self._pending_confirmations.keys())
            logger.debug(f"All pending confirmation keys: {all_keys}")
            
            # For legacy implementation, we need to find a key that may be composite (step_number, tool_name)
            # or may be a string ID in our new implementation
            found_key = None
            
            for key in all_keys:
                # Skip confirmation_id keys (strings) in this legacy path
                if isinstance(key, str):
                    continue
                    
                if isinstance(key, tuple) and len(key) == 2:
                    key_step, key_tool = key
                    if key_step == step_number and key_tool == tool_name:
                        found_key = key
                        break
            
            if found_key:
                logger.debug(f"Found pending confirmation with legacy key: {found_key}, resolving future")
                # Resolve the future with the confirmation result
                self._pending_confirmations[found_key].set_result(confirmed)
                
                # Remove the pending confirmation
                del self._pending_confirmations[found_key]
                logger.debug("Removed legacy confirmation from pending confirmations")
                
                success = True
            else:
                logger.warning(f"No pending confirmation found for {tool_name} at step {step_number}")
                success = False
                
        # Emit confirmation response event - always emit even if we didn't find a matching confirmation
        # so other components know about the response
        logger.debug("Emitting ToolConfirmationResponseEvent")
        response_event = ToolConfirmationResponseEvent(
            event_type="ToolConfirmationResponse",
            step_number=step_number,
            tool_name=tool_name,
            confirmed=confirmed,
            confirmation_id=confirmation_id or ""
        )
        logger.debug(f"Created response event: {response_event}")
        
        try:
            await self.notify_event(response_event)
            logger.debug("Successfully emitted ToolConfirmationResponseEvent")
        except Exception as e:
            logger.error(f"Error emitting confirmation response event: {e}")
        
        logger.debug("===== CONFIRMATION RESPONSE END =====")
        return success

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
                logger.error(f"Execution error at step {step}: {result.error}")
                return ExecutionResult(
                    execution_status="error",
                    error=str(result.error),
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