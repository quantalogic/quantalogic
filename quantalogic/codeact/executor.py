import asyncio
from typing import Callable, Dict, List

from lxml import etree
from quantalogic_pythonbox import execute_async

from quantalogic.tools import Tool

from .events import ToolExecutionCompletedEvent, ToolExecutionErrorEvent, ToolExecutionStartedEvent
from .utils import XMLResultHandler, validate_code


class Executor:
    """Manages action execution and context updates with dynamic tool registration."""
    def __init__(self, tools: List[Tool], notify_event: Callable):
        # Changed from List to Dict for dynamic registration
        self.tools: Dict[str, Tool] = {tool.name: tool for tool in tools}
        self.notify_event = notify_event  # Callback to notify observers
        self.tool_namespace = self._build_tool_namespace()

    def _build_tool_namespace(self) -> Dict:
        """Build the namespace with wrapped tool functions that trigger events."""
        def wrap_tool(tool):
            async def wrapped_tool(**kwargs):
                current_step = self.tool_namespace.get('current_step', None)
                parameters_summary = {
                    k: str(v)[:100] + "..." if len(str(v)) > 100 else str(v)
                    for k, v in kwargs.items()
                }
                await self.notify_event(ToolExecutionStartedEvent(
                    event_type="ToolExecutionStarted",
                    step_number=current_step,
                    tool_name=tool.name,
                    parameters_summary=parameters_summary
                ))
                try:
                    result = await tool.async_execute(**kwargs)
                    result_summary = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                    await self.notify_event(ToolExecutionCompletedEvent(
                        event_type="ToolExecutionCompleted",
                        step_number=current_step,
                        tool_name=tool.name,
                        result_summary=result_summary
                    ))
                    return result
                except Exception as e:
                    await self.notify_event(ToolExecutionErrorEvent(
                        event_type="ToolExecutionError",
                        step_number=current_step,
                        tool_name=tool.name,
                        error=str(e)
                    ))
                    raise
            return wrapped_tool

        return {
            "asyncio": asyncio,
            "context_vars": {},
            **{tool.name: wrap_tool(tool) for tool in self.tools.values()}
        }

    def register_tool(self, tool: Tool) -> None:
        """Register a new tool dynamically at runtime."""
        if tool.name in self.tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self.tools[tool.name] = tool
        self.tool_namespace[tool.name] = self._wrap_tool(tool)

    def _wrap_tool(self, tool: Tool) -> Callable:
        """Wrap a tool function to handle execution events (internal use)."""
        async def wrapped_tool(**kwargs):
            current_step = self.tool_namespace.get('current_step', None)
            parameters_summary = {
                k: str(v)[:100] + "..." if len(str(v)) > 100 else str(v)
                for k, v in kwargs.items()
            }
            await self.notify_event(ToolExecutionStartedEvent(
                event_type="ToolExecutionStarted",
                step_number=current_step,
                tool_name=tool.name,
                parameters_summary=parameters_summary
            ))
            try:
                result = await tool.async_execute(**kwargs)
                result_summary = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                await self.notify_event(ToolExecutionCompletedEvent(
                    event_type="ToolExecutionCompleted",
                    step_number=current_step,
                    tool_name=tool.name,
                    result_summary=result_summary
                ))
                return result
            except Exception as e:
                await self.notify_event(ToolExecutionErrorEvent(
                    event_type="ToolExecutionError",
                    step_number=current_step,
                    tool_name=tool.name,
                    error=str(e)
                ))
                raise
        return wrapped_tool

    async def execute_action(self, code: str, context_vars: Dict, step: int, timeout: int = 300) -> str:
        """Execute the generated code and return the result, setting the step number."""
        self.tool_namespace["context_vars"] = context_vars
        self.tool_namespace['current_step'] = step
        if not validate_code(code):
            return etree.tostring(
                etree.Element("ExecutionResult", status="Error", message="Code lacks async main()"),
                encoding="unicode"
            )
        
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