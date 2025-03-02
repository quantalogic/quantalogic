"""Module for defining tool arguments and base tool classes.

This module provides base classes and data models for creating configurable tools
with type-validated arguments and execution methods.
"""

import ast
import asyncio  # Added for asynchronous support
import inspect
from typing import Any, Callable, Literal, TypeVar

from docstring_parser import parse as parse_docstring
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Type variable for create_tool to preserve function signature
F = TypeVar('F', bound=Callable[..., Any])

class ToolArgument(BaseModel):
    """Represents an argument for a tool with validation and description.

    Attributes:
        name: The name of the argument.
        arg_type: The type of the argument (integer, float, boolean).
        description: Optional description of the argument.
        required: Indicates if the argument is mandatory.
        default: Optional default value for the argument.
        example: Optional example value to illustrate the argument's usage.
    """

    name: str = Field(..., description="The name of the argument.")
    arg_type: Literal["string", "int", "float", "boolean"] = Field(
        ..., description="The type of the argument. Must be one of: string, integer, float, boolean."
    )
    description: str | None = Field(default=None, description="A brief description of the argument.")
    required: bool = Field(default=False, description="Indicates if the argument is required.")
    default: str | None = Field(
        default=None, description="The default value for the argument. This parameter is required."
    )
    example: str | None = Field(default=None, description="An example value to illustrate the argument's usage.")


class ToolDefinition(BaseModel):
    """Base class for defining tool configurations without execution logic.

    Attributes:
        name: Unique name of the tool.
        description: Brief description of the tool's functionality.
        arguments: List of arguments the tool accepts.
        need_validation: Flag to indicate if tool requires validation.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    name: str = Field(..., description="The unique name of the tool.")
    description: str = Field(..., description="A brief description of what the tool does.")
    arguments: list[ToolArgument] = Field(default_factory=list, description="A list of arguments the tool accepts.")
    need_validation: bool = Field(
        default=False,
        description="When True, requires user confirmation before execution. Useful for tools that perform potentially destructive operations.",
    )
    need_variables: bool = Field(
        default=False,
        description="When True, provides access to the agent's variable store. Required for tools that need to interpolate variables (e.g., Jinja templates).",
    )
    need_caller_context_memory: bool = Field(
        default=False,
        description="When True, provides access to the agent's conversation history. Useful for tools that need context from previous interactions.",
    )

    def get_properties(self, exclude: list[str] | None = None) -> dict[str, Any]:
        """Return a dictionary of all non-None properties, excluding Tool class fields and specified fields.

        Args:
            exclude: Optional list of field names to exclude from the result

        Returns:
            Dictionary of property names and values, excluding Tool class fields and specified fields.
        """
        exclude = exclude or []
        tool_fields = {
            "name",
            "description",
            "arguments",
            "need_validation",
            "need_variables",
            "need_caller_context_memory",
        }
        properties = {}

        for name, value in self.__dict__.items():
            if name not in tool_fields and name not in exclude and value is not None and not name.startswith("_"):
                properties[name] = value

        return properties

    def to_json(self) -> str:
        """Convert the tool to a JSON string representation.

        Returns:
            A JSON string of the tool's configuration.
        """
        return self.model_dump_json()

    def to_markdown(self) -> str:
        """Create a comprehensive Markdown representation of the tool.

        Returns:
            A detailed Markdown string representing the tool's configuration and usage.
        """
        # Tool name and description
        markdown = f"`{self.name}`:\n"
        markdown += f"- **Description**: {self.description}\n\n"

        properties_injectable = self.get_injectable_properties_in_execution()

        # Parameters section
        if self.arguments:
            markdown += "- **Parameters**:\n"
            parameters = ""
            for arg in self.arguments:
                # Skip if parameter name matches an object property with non-None value
                # This enables automatic property injection during execution:
                # When an object has a property matching an argument name,
                # the agent will inject the property value at runtime,
                # reducing manual input and improving flexibility
                if properties_injectable.get(arg.name) is not None:
                    continue

                required_status = "required" if arg.required else "optional"
                # Prioritize example, then default, then create a generic description
                value_info = ""
                if arg.example is not None:
                    value_info = f" (example: `{arg.example}`)"
                elif arg.default is not None:
                    value_info = f" (default: `{arg.default}`)"

                parameters += (
                    f"  - `{arg.name}`: " f"({required_status}{value_info})\n" f"    {arg.description or ''}\n"
                )
            if len(parameters) > 0:
                markdown += parameters + "\n\n"
            else:
                markdown += "None\n\n"

        # Usage section with XML-style example
        markdown += "**Usage**:\n"
        markdown += "```xml\n"
        markdown += f"<{self.name}>\n"

        # Generate example parameters
        for arg in self.arguments:
            if properties_injectable.get(arg.name) is not None:
                continue
            # Prioritize example, then default, then create a generic example
            example_value = arg.example or arg.default or f"Your {arg.name} here"
            markdown += f"  <{arg.name}>{example_value}</{arg.name}>\n"

        markdown += f"</{self.name}>\n"
        markdown += "```\n"

        return markdown

    def get_non_injectable_arguments(self) -> list[ToolArgument]:
        """Get arguments that cannot be injected from properties.

        Returns:
            List of ToolArgument instances that cannot be injected by the agent.
        """
        properties_injectable = self.get_injectable_properties_in_execution()

        return [arg for arg in self.arguments if properties_injectable.get(arg.name) is None]

    def get_injectable_properties_in_execution(self) -> dict[str, Any]:
        """Get injectable properties excluding tool arguments.

        Returns:
            A dictionary of property names and values, excluding tool arguments and None values.
        """
        # This method is defined here in ToolDefinition and overridden in Tool
        # For ToolDefinition, it returns an empty dict since it has no execution context yet
        return {}


class Tool(ToolDefinition):
    """Extended class for tools with execution capabilities.

    Inherits from ToolDefinition and adds execution functionality.
    """

    @field_validator("arguments", mode="before")
    @classmethod
    def validate_arguments(cls, v: Any) -> list[ToolArgument]:
        """Validate and convert arguments to ToolArgument instances.

        Args:
            v: Input arguments to validate.

        Returns:
            A list of validated ToolArgument instances.
        """
        if isinstance(v, list):
            return [
                ToolArgument(**arg)
                if isinstance(arg, dict)
                else arg
                if isinstance(arg, ToolArgument)
                else ToolArgument(name=str(arg), type=type(arg).__name__)
                for arg in v
            ]
        return []

    def execute(self, **kwargs: Any) -> str:
        """Execute the tool with provided arguments.

        If not implemented by a subclass, falls back to the asynchronous execute_async method.

        Args:
            **kwargs: Keyword arguments for tool execution.

        Returns:
            A string representing the result of tool execution.
        """
        # Check if execute is implemented in the subclass
        if self.__class__.execute is Tool.execute:
            # If not implemented, run the async version synchronously
            return asyncio.run(self.async_execute(**kwargs))
        raise NotImplementedError("This method should be implemented by subclasses.")

    async def async_execute(self, **kwargs: Any) -> str:
        """Asynchronous version of execute.

        By default, runs the synchronous execute method in a separate thread using asyncio.to_thread.
        Subclasses can override this method to provide a native asynchronous implementation for
        operations that benefit from async I/O (e.g., network requests).

        Args:
            **kwargs: Keyword arguments for tool execution.

        Returns:
            A string representing the result of tool execution.
        """
        # Check if execute_async is implemented in the subclass
        if self.__class__.async_execute is Tool.async_execute:
            return await asyncio.to_thread(self.execute, **kwargs)
        raise NotImplementedError("This method should be implemented by subclasses.")

    def get_injectable_properties_in_execution(self) -> dict[str, Any]:
        """Get injectable properties excluding tool arguments.

        Returns:
            A dictionary of property names and values, excluding tool arguments and None values.
        """
        # Get argument names from tool definition
        argument_names = {arg.name for arg in self.arguments}

        # Get properties excluding arguments and filter out None values
        properties = self.get_properties(exclude=["arguments"])
        return {name: value for name, value in properties.items() if value is not None and name in argument_names}


def create_tool(func: F) -> Tool:
    """Create a Tool instance from a Python function using AST analysis.

    Analyzes the function's source code to extract its name, docstring, and arguments,
    then constructs a Tool subclass with appropriate execution logic.

    Args:
        func: The Python function (sync or async) to convert into a Tool.

    Returns:
        A Tool subclass instance configured based on the function.

    Raises:
        ValueError: If the input is not a valid function or lacks a function definition.
    """
    if not callable(func):
        raise ValueError("Input must be a callable function")

    # Get source code and parse with AST
    try:
        source = inspect.getsource(func).strip()
        tree = ast.parse(source)
    except (OSError, TypeError, SyntaxError) as e:
        raise ValueError(f"Failed to parse function source: {e}")

    # Ensure root node is a function definition
    if not tree.body or not isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ValueError("Source must define a single function")
    func_def = tree.body[0]

    # Extract metadata
    name = func_def.name
    docstring = ast.get_docstring(func_def) or ""
    parsed_doc = parse_docstring(docstring)
    description = parsed_doc.short_description or f"Tool generated from {name}"
    param_docs = {p.arg_name: p.description for p in parsed_doc.params}
    is_async = isinstance(func_def, ast.AsyncFunctionDef)

    # Get type hints using typing module
    from typing import get_type_hints
    type_hints = get_type_hints(func)
    type_map = {int: "int", str: "string", float: "float", bool: "boolean"}

    # Process arguments
    args = func_def.args
    defaults = [None] * (len(args.args) - len(args.defaults)) + [
        ast.unparse(d) if isinstance(d, ast.AST) else str(d) for d in args.defaults
    ]
    arguments: list[ToolArgument] = []

    for i, arg in enumerate(args.args):
        arg_name = arg.arg
        default = defaults[i]
        required = default is None

        # Determine argument type
        hint = type_hints.get(arg_name, str)  # Default to str if no hint
        arg_type = type_map.get(hint, "string")  # Fallback to string for unmapped types

        # Use docstring or default description
        description = param_docs.get(arg_name, f"Argument {arg_name}")

        # Create ToolArgument
        arguments.append(ToolArgument(
            name=arg_name,
            arg_type=arg_type,
            description=description,
            required=required,
            default=default,
            example=default if default else None
        ))

    # Define Tool subclass
    class GeneratedTool(Tool):
        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(*args, name=name, description=description, arguments=arguments, **kwargs)
            self._func = func

        if is_async:
            async def async_execute(self, **kwargs: Any) -> str:
                result = await self._func(**kwargs)
                return str(result)
        else:
            def execute(self, **kwargs: Any) -> str:
                result = self._func(**kwargs)
                return str(result)

    return GeneratedTool()


if __name__ == "__main__":
    tool = Tool(name="my_tool", description="A simple tool", arguments=[ToolArgument(name="arg1", arg_type="string")])
    print(tool.to_markdown())

    class MyTool(Tool):
        field1: str | None = Field(default=None, description="Field 1 description")

    tool_with_fields = MyTool(
        name="my_tool1", description="A simple tool", arguments=[ToolArgument(name="field1", arg_type="string")]
    )
    print(tool_with_fields.to_markdown())
    print(tool_with_fields.get_injectable_properties_in_execution())

    tool_with_fields_defined = MyTool(
        name="my_tool2",
        description="A simple tool2",
        field1="field1_value",
        arguments=[ToolArgument(name="field1", arg_type="string")],
    )
    print(tool_with_fields_defined.to_markdown())
    print(tool_with_fields_defined.get_injectable_properties_in_execution())

    # Test create_tool with synchronous function
    def add(a: int, b: int = 0) -> int:
        """Add two numbers.
        
        Args:
            a: First number.
            b: Second number (optional).
        """
        return a + b

    # Test create_tool with asynchronous function
    async def greet(name: str) -> str:
        """Greet a person.
        
        Args:
            name: Name of the person.
        """
        await asyncio.sleep(0.1)  # Simulate async work
        return f"Hello, {name}"

    # Create and test tools
    sync_tool = create_tool(add)
    print("\nSynchronous Tool:")
    print(sync_tool.to_markdown())
    print("Execution result:", sync_tool.execute(a=5, b=3))

    async_tool = create_tool(greet)
    print("\nAsynchronous Tool:")
    print(async_tool.to_markdown())
    print("Execution result:", asyncio.run(async_tool.async_execute(name="Alice")))