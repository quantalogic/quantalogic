import asyncio
from abc import ABC, abstractmethod
from typing import Callable, Dict, List

from lxml import etree
from quantalogic_pythonbox import AsyncExecutionResult, execute_async  # Updated import for clarity

from quantalogic.tools import Tool

from .events import ToolExecutionCompletedEvent, ToolExecutionErrorEvent, ToolExecutionStartedEvent
from .tools_manager import ToolRegistry
from .utils import XMLResultHandler, validate_code


class BaseExecutor(ABC):
    """Abstract base class for execution components."""

    @abstractmethod
    async def execute_action(self, code: str, context_vars: Dict, step: int, timeout: int) -> str:
        pass

    @abstractmethod
    def register_tool(self, tool: Tool) -> None:
        pass


class Executor(BaseExecutor):
    """Manages action execution and context updates with dynamic tool registration."""

    def __init__(self, tools: List[Tool], notify_event: Callable, verbose: bool = True):
        self.registry = ToolRegistry()
        for tool in tools:
            self.registry.register(tool)
        self.tools: Dict[str, Tool] = self.registry.tools
        self.notify_event = notify_event
        self.verbose = verbose
        self.tool_namespace = self._build_tool_namespace()

    def _build_tool_namespace(self) -> Dict:
        """Build the namespace with wrapped tool functions that trigger events if verbose."""
        if not self.verbose:
            return {
                "asyncio": asyncio,
                "context_vars": {},
                **{tool.name: tool.async_execute for tool in self.tools.values()},
            }

        def wrap_tool(tool):
            async def wrapped_tool(**kwargs):
                current_step = self.tool_namespace.get("current_step", None)
                parameters_summary = {
                    k: str(v)[:100] + "..." if len(str(v)) > 100 else str(v) for k, v in kwargs.items()
                }
                await self.notify_event(
                    ToolExecutionStartedEvent(
                        event_type="ToolExecutionStarted",
                        step_number=current_step,
                        tool_name=tool.name,
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
                            tool_name=tool.name,
                            result_summary=result_summary,
                        )
                    )
                    return result
                except Exception as e:
                    await self.notify_event(
                        ToolExecutionErrorEvent(
                            event_type="ToolExecutionError", step_number=current_step, tool_name=tool.name, error=str(e)
                        )
                    )
                    raise

            return wrapped_tool

        return {"asyncio": asyncio, "context_vars": {}, **{tool.name: wrap_tool(tool) for tool in self.tools.values()}}

    def register_tool(self, tool: Tool) -> None:
        """Register a new tool dynamically at runtime."""
        self.registry.register(tool)
        self.tools[tool.name] = tool
        self.tool_namespace[tool.name] = self._wrap_tool(tool) if self.verbose else tool.async_execute

    def _wrap_tool(self, tool: Tool) -> Callable:
        """Wrap a tool function to handle execution events (internal use)."""

        async def wrapped_tool(**kwargs):
            current_step = self.tool_namespace.get("current_step", None)
            parameters_summary = {k: str(v)[:100] + "..." if len(str(v)) > 100 else str(v) for k, v in kwargs.items()}
            await self.notify_event(
                ToolExecutionStartedEvent(
                    event_type="ToolExecutionStarted",
                    step_number=current_step,
                    tool_name=tool.name,
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
                        tool_name=tool.name,
                        result_summary=result_summary,
                    )
                )
                return result
            except Exception as e:
                await self.notify_event(
                    ToolExecutionErrorEvent(
                        event_type="ToolExecutionError", step_number=current_step, tool_name=tool.name, error=str(e)
                    )
                )
                raise

        return wrapped_tool

    async def execute_action(self, code: str, context_vars: Dict, step: int, timeout: int = 300) -> str:
        """Execute the generated code and return the result with local variables, setting the step number."""
        self.tool_namespace["context_vars"] = context_vars
        self.tool_namespace["current_step"] = step
        if not validate_code(code):
            return etree.tostring(
                etree.Element("ExecutionResult", status="Error", message="Code lacks async main()"), encoding="unicode"
            )

        try:
            # Execute the code using the updated quantalogic_pythonbox execute_async
            result: AsyncExecutionResult = await execute_async(
                code=code,
                timeout=timeout,
                entry_point="main",
                allowed_modules=["asyncio", "math", "random", "time"],
                namespace=self.tool_namespace,
            )
            # Update context_vars with all local variables from the execution
            if result.local_variables:
                context_vars.update(
                    {k: v for k, v in result.local_variables.items() if not k.startswith("__") and not callable(v)}
                )
            return XMLResultHandler.format_execution_result(result)
        except Exception as e:
            # Format error result without local variables if execution fails
            root = etree.Element("ExecutionResult")
            root.append(etree.Element("Status", text="Error"))
            root.append(etree.Element("Value", text=f"Execution error: {str(e)}"))
            root.append(etree.Element("ExecutionTime", text="0.00 seconds"))
            root.append(etree.Element("Completed", text="false"))
            return etree.tostring(root, pretty_print=True, encoding="unicode")