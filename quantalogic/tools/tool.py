"""Module for defining tool arguments and base tool classes.

This module provides base classes and data models for creating configurable tools
with type-validated arguments and execution methods.
"""

import ast
import asyncio
import inspect
from typing import Any, Callable, TypeVar, get_args, get_origin

from docstring_parser import parse as parse_docstring
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Type variable for create_tool to preserve function signature
F = TypeVar('F', bound=Callable[..., Any])


def type_hint_to_str(type_hint):
    """Convert a type hint to a string representation.

    Args:
        type_hint: The type hint to convert.

    Returns:
        A string representation of the type hint, e.g., 'list[int]', 'dict[str, float]'.
    """
    origin = get_origin(type_hint)
    if origin is not None:
        origin_name = origin.__name__
        args = get_args(type_hint)
        args_str = ", ".join(type_hint_to_str(arg) for arg in args)
        return f"{origin_name}[{args_str}]"
    elif hasattr(type_hint, "__name__"):
        return type_hint.__name__
    else:
        return str(type_hint)


def get_type_description(type_hint):
    """Generate a detailed description of the type hint.

    Args:
        type_hint: The type hint to describe.

    Returns:
        A string describing the type hint in detail, e.g., 'a list of int', or a structured class description.
    """
    origin = get_origin(type_hint)
    if origin is not None:
        if origin is list:
            item_type = get_args(type_hint)[0]
            return f"a list of {get_type_description(item_type)}"
        elif origin is dict:
            key_type, value_type = get_args(type_hint)
            return f"a dictionary with {get_type_description(key_type)} keys and {get_type_description(value_type)} values"
        else:
            return type_hint_to_str(type_hint)
    elif inspect.isclass(type_hint) and hasattr(type_hint, "__annotations__"):
        annotations = getattr(type_hint, "__annotations__", {})
        if annotations:
            field_desc = "\n".join([f"        - {name}: {type_hint_to_str(typ)}" for name, typ in annotations.items()])
            return f"an instance of {type_hint.__name__} with attributes:\n{field_desc}"
        return type_hint.__name__
    else:
        return f"<class '{str(type_hint)}'>"


class ToolArgument(BaseModel):
    """Represents an argument for a tool with validation and description.

    Attributes:
        name: The name of the argument.
        arg_type: The type of the argument, e.g., 'string', 'int', 'list[int]', 'dict[str, float]'.
        description: Optional description of the argument.
        required: Indicates if the argument is mandatory.
        default: Optional default value for the argument.
        example: Optional example value to illustrate the argument's usage.
        type_details: Detailed description of the argument's type.
    """

    name: str = Field(..., description="The name of the argument.")
    arg_type: str = Field(
        ..., description="The type of the argument, e.g., 'string', 'int', 'list[int]', 'dict[str, float]', etc."
    )
    description: str | None = Field(default=None, description="A brief description of the argument.")
    required: bool = Field(default=False, description="Indicates if the argument is required.")
    default: str | None = Field(
        default=None, description="The default value for the argument. This parameter is required."
    )
    example: str | None = Field(default=None, description="An example value to illustrate the argument's usage.")
    type_details: str | None = Field(default=None, description="Detailed description of the argument's type.")


class ToolDefinition(BaseModel):
    """Base class for defining tool configurations without execution logic.

    Attributes:
        name: Unique name of the tool.
        description: Brief description of the tool's functionality.
        arguments: List of arguments the tool accepts.
        return_type: The return type of the tool's execution method. Defaults to "str".
        return_description: Optional description of the return value.
        return_type_details: Detailed description of the return type.
        need_validation: Flag to indicate if tool requires validation.
        is_async: Flag to indicate if the tool is asynchronous (for documentation purposes).
        toolbox_name: Optional name of the toolbox this tool belongs to.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    name: str = Field(..., description="The unique name of the tool.")
    description: str = Field(..., description="A brief description of what the tool does.")
    arguments: list[ToolArgument] = Field(default_factory=list, description="A list of arguments the tool accepts.")
    return_type: str = Field(default="str", description="The return type of the tool's execution method.")
    return_description: str | None = Field(default=None, description="Description of the return value.")
    return_type_details: str | None = Field(default=None, description="Detailed description of the return type.")
    need_validation: bool = Field(
        default=False,
        description="When True, requires user confirmation before execution. Useful for tools that perform potentially destructive operations.",
    )
    need_post_process: bool = Field(
        default=True,
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
    is_async: bool = Field(
        default=False,
        description="Indicates if the tool is asynchronous (used for documentation).",
    )
    toolbox_name: str | None = Field(
        default=None,
        description="The name of the toolbox this tool belongs to, set during registration if applicable."
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
            "return_type",
            "return_description",
            "need_validation",
            "need_variables",
            "need_caller_context_memory",
            "return_type_details",
            "is_async",
            "toolbox_name",  # Added to standard fields
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
        markdown = f"`{self.name}`:\n"
        markdown += f"- **Description**: {self.description}\n\n"

        properties_injectable = self.get_injectable_properties_in_execution()
        if any(properties_injectable.get(arg.name) is not None for arg in self.arguments):
            markdown += "- **Note**: Some arguments are injected from the tool's configuration and may not need to be provided explicitly.\n\n"

        if self.arguments:
            markdown += "- **Parameters**:\n"
            parameters = ""
            for arg in self.arguments:
                if properties_injectable.get(arg.name) is not None:
                    continue
                type_info = f"{arg.arg_type}"
                if arg.type_details and arg.type_details != arg.arg_type:
                    type_info += f" ({arg.type_details})"
                required_status = "required" if arg.required else "optional"
                value_info = ""
                if arg.default is not None:
                    value_info += f", default: `{arg.default}`"
                if arg.example is not None:
                    value_info += f", example: `{arg.example}`"
                parameters += (
                    f"  - `{arg.name}`: ({type_info}, {required_status}{value_info})\n"
                    f"    {arg.description or ''}\n"
                )
            if parameters:
                markdown += parameters + "\n"
            else:
                markdown += "  None\n\n"

        standard_fields = {
            "name", "description", "arguments", "return_type", "return_description", "return_type_details",
            "need_validation", "need_post_process", "need_variables", "need_caller_context_memory", "is_async",
            "toolbox_name"  # Added to standard fields
        }
        additional_fields = [f for f in self.model_fields if f not in standard_fields]
        if additional_fields:
            markdown += "- **Configuration**:\n"
            for field in additional_fields:
                field_info = self.model_fields[field]
                field_type = type_hint_to_str(field_info.annotation)
                field_desc = field_info.description or "No description provided."
                if field in properties_injectable:
                    field_desc += f" Injects into '{field}' argument."
                markdown += f"  - `{field}`: ({field_type}) - {field_desc}\n"
            markdown += "\n"

        markdown += "- **Usage**: This tool can be invoked using the following XML-like syntax:\n"
        markdown += "```xml\n"
        markdown += f"<{self.name}>\n"

        for arg in self.arguments:
            if properties_injectable.get(arg.name) is not None:
                continue
            example_value = arg.example or arg.default or f"Your {arg.name} here"
            markdown += f"  <{arg.name}>{example_value}</{arg.name}>\n"

        markdown += f"</{self.name}>\n"
        markdown += "```\n\n"

        markdown += f"- **Returns**: `{self.return_type}` - {self.return_description or 'The result of the tool execution.'}\n"

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
        return {}

    def to_docstring(self) -> str:
        """Convert the tool definition into a Google-style docstring with function signature.

        Returns:
            A string formatted as a valid Python docstring representing the tool's configuration,
            including the function signature, detailed argument types, and return type with descriptions.
        """
        signature_parts = []
        for arg in self.arguments:
            arg_str = f"{arg.name}: {arg.arg_type}"
            if arg.default is not None:
                arg_str += f" = {arg.default}"
            signature_parts.append(arg_str)
        signature = f"{'async ' if self.is_async else ''}def {self.name}({', '.join(signature_parts)}) -> {self.return_type}:"

        docstring = f'"""\n{signature}\n\n{self.description}\n'
        properties_injectable = self.get_injectable_properties_in_execution()
        if properties_injectable:
            docstring += "\n    Note: Some arguments may be injected from the tool's configuration.\n"

        if self.arguments:
            docstring += "\nArgs:\n"
            for arg in self.arguments:
                arg_line = f"    {arg.name} ({arg.arg_type})"
                details = []
                if not arg.required:
                    details.append("optional")
                if arg.default is not None:
                    details.append(f"defaults to {arg.default}")
                if arg.example is not None:
                    details.append(f"e.g., {arg.example}")
                if details:
                    arg_line += f" [{', '.join(details)}]"
                if arg.description:
                    arg_line += f": {arg.description}"
                if arg.type_details and arg.type_details != arg.arg_type:
                    arg_line += f"\n        {arg.type_details}"
                docstring += f"{arg_line}\n"

        return_desc = self.return_description or "The result of the tool execution."
        docstring += f"\nReturns:\n    {self.return_type}: {return_desc}"
        if self.return_type_details and self.return_type_details != self.return_type:
            docstring += f"\n        {self.return_type_details}"
        docstring += "\n"

        docstring += "\nExamples:\n"
        args_str = ", ".join([f"{arg.name}=..." for arg in self.arguments if arg.required])
        prefix = "        result = " if not self.is_async else "        result = await "
        docstring += f"{prefix}{self.name}({args_str})\n"

        standard_fields = {
            "name", "description", "arguments", "return_type", "return_description", "return_type_details",
            "need_validation", "need_post_process", "need_variables", "need_caller_context_memory", "is_async",
            "toolbox_name"  # Added to standard fields
        }
        additional_fields = [f for f in self.model_fields if f not in standard_fields]
        if additional_fields:
            docstring += "\nConfiguration:\n"
            for field in additional_fields:
                field_info = self.model_fields[field]
                field_type = type_hint_to_str(field_info.annotation)
                field_desc = field_info.description or "No description provided."
                docstring += f"    {field} ({field_type}): {field_desc}\n"

        docstring += '\n"""'
        return docstring


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
                else ToolArgument(name=str(arg), arg_type=type(arg).__name__)
                for arg in v
            ]
        return []

    def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with provided arguments.

        If not implemented by a subclass, falls back to the asynchronous execute_async method.

        Args:
            **kwargs: Keyword arguments for tool execution.

        Returns:
            The result of tool execution, preserving the original type returned by the tool's logic.
        """
        if self.__class__.execute is Tool.execute:
            return asyncio.run(self.async_execute(**kwargs))
        raise NotImplementedError("This method should be implemented by subclasses.")

    async def async_execute(self, **kwargs: Any) -> Any:
        """Asynchronous version of execute.

        By default, runs the synchronous execute method in a separate thread using asyncio.to_thread.
        Subclasses can override this method to provide a native asynchronous implementation for
        operations that benefit from async I/O (e.g., network requests).

        Args:
            **kwargs: Keyword arguments for tool execution.

        Returns:
            The result of tool execution, preserving the original type returned by the tool's logic.
        """
        if self.__class__.async_execute is Tool.async_execute:
            return await asyncio.to_thread(self.execute, **kwargs)
        raise NotImplementedError("This method should be implemented by subclasses.")

    def get_injectable_properties_in_execution(self) -> dict[str, Any]:
        """Get injectable properties excluding tool arguments.

        Returns:
            A dictionary of property names and values, excluding tool arguments and None values.
        """
        argument_names = {arg.name for arg in self.arguments}
        properties = self.get_properties(exclude=["arguments"])
        return {name: value for name, value in properties.items() if value is not None and name in argument_names}


def create_tool(func: F) -> Tool:
    """Create a Tool instance from a Python function using AST analysis.

    Analyzes the function's source code to extract its name, docstring, and arguments,
    then constructs a Tool subclass with appropriate execution logic for both
    synchronous and asynchronous functions.

    Args:
        func: The Python function (sync or async) to convert into a Tool.

    Returns:
        A Tool subclass instance configured based on the function.

    Raises:
        ValueError: If the input is not a valid function or lacks a function definition.
    """
    if not callable(func):
        raise ValueError("Input must be a callable function")

    try:
        source = inspect.getsource(func).strip()
        tree = ast.parse(source)
    except (OSError, TypeError, SyntaxError) as e:
        raise ValueError(f"Failed to parse function source: {e}")

    if not tree.body or not isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ValueError("Source must define a single function")
    func_def = tree.body[0]

    name = func_def.name
    docstring = ast.get_docstring(func_def) or ""
    parsed_doc = parse_docstring(docstring)
    description = parsed_doc.short_description or f"Tool generated from {name}"
    param_docs = {p.arg_name: p.description for p in parsed_doc.params}
    return_description = parsed_doc.returns.description if parsed_doc.returns else None
    is_async = isinstance(func_def, ast.AsyncFunctionDef)

    from typing import get_type_hints
    type_hints = get_type_hints(func)

    args = func_def.args
    defaults = [None] * (len(args.args) - len(args.defaults)) + [
        ast.unparse(d) if isinstance(d, ast.AST) else str(d) for d in args.defaults
    ]
    arguments: list[ToolArgument] = []

    for i, arg in enumerate(args.args):
        arg_name = arg.arg
        default = defaults[i]
        required = default is None
        hint = type_hints.get(arg_name, str)
        arg_type = type_hint_to_str(hint)
        description = param_docs.get(arg_name, f"Argument {arg_name}")
        arguments.append(ToolArgument(
            name=arg_name,
            arg_type=arg_type,
            description=description,
            required=required,
            default=default,
            example=default if default else None,
            type_details=get_type_description(hint)
        ))

    return_type_str = type_hint_to_str(type_hints.get("return", str))
    return_type_details = get_type_description(type_hints.get("return", str))

    class GeneratedTool(Tool):
        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(
                *args,
                name=name,
                description=description,
                arguments=arguments,
                return_type=return_type_str,
                return_description=return_description,
                return_type_details=return_type_details,
                is_async=is_async,
                toolbox_name=None,  # Explicitly set to None initially
                **kwargs
            )
            self._func = func

        def execute(self, **kwargs: Any) -> Any:
            """Execute the tool synchronously, handling both sync and async functions.

            Args:
                **kwargs: Keyword arguments for tool execution.

            Returns:
                The result of the function execution, preserving its original type.
            """
            injectable = self.get_injectable_properties_in_execution()
            full_kwargs = {**injectable, **kwargs}
            if self.is_async:
                return asyncio.run(self.async_execute(**full_kwargs))
            else:
                return self._func(**full_kwargs)

        async def async_execute(self, **kwargs: Any) -> Any:
            """Execute the tool asynchronously, handling both sync and async functions.

            Args:
                **kwargs: Keyword arguments for tool execution.

            Returns:
                The result of the function execution, preserving its original type.
            """
            injectable = self.get_injectable_properties_in_execution()
            full_kwargs = {**injectable, **kwargs}
            if self.is_async:
                return await self._func(**full_kwargs)
            else:
                return self._func(**full_kwargs)

    return GeneratedTool()


if __name__ == "__main__":
    # Basic tool with argument
    tool = Tool(
        name="my_tool",
        description="A simple tool",
        arguments=[ToolArgument(name="arg1", arg_type="string")]
    )
    print("Basic Tool Markdown:")
    print(tool.to_markdown())
    print("Basic Tool Docstring:")
    print(tool.to_docstring())
    print()

    # Tool with injectable field (undefined)
    class MyTool(Tool):
        field1: str | None = Field(default=None, description="Field 1 description")

    tool_with_fields = MyTool(
        name="my_tool1",
        description="A simple tool with a field",
        arguments=[ToolArgument(name="field1", arg_type="string")]
    )
    print("Tool with Undefined Field Markdown:")
    print(tool_with_fields.to_markdown())
    print("Injectable Properties (should be empty):", tool_with_fields.get_injectable_properties_in_execution())
    print("Tool with Undefined Field Docstring:")
    print(tool_with_fields.to_docstring())
    print()

    # Tool with defined injectable field
    tool_with_fields_defined = MyTool(
        name="my_tool2",
        description="A simple tool with a defined field",
        field1="field1_value",
        arguments=[ToolArgument(name="field1", arg_type="string")]
    )
    print("Tool with Defined Field Markdown:")
    print(tool_with_fields_defined.to_markdown())
    print("Injectable Properties (should include field1):", tool_with_fields_defined.get_injectable_properties_in_execution())
    print("Tool with Defined Field Docstring:")
    print(tool_with_fields_defined.to_docstring())
    print()

    # Test create_tool with synchronous function
    def add(a: int, b: int = 0) -> int:
        """Add two numbers.
        
        Args:
            a: First number.
            b: Second number (optional).
        
        Returns:
            The sum of a and b.
        """
        return a + b

    sync_tool = create_tool(add)
    print("Synchronous Tool Markdown:")
    print(sync_tool.to_markdown())
    print("Synchronous Tool Docstring:")
    print(sync_tool.to_docstring())
    print("Execution result (sync):", sync_tool.execute(a=5, b=3))
    print("Execution result (async):", asyncio.run(sync_tool.async_execute(a=5, b=3)))
    print()

    # Test create_tool with asynchronous function
    async def greet(name: str) -> str:
        """Greet a person.
        
        Args:
            name: Name of the person.
        
        Returns:
            A greeting message.
        """
        await asyncio.sleep(0.1)
        return f"Hello, {name}"

    async_tool = create_tool(greet)
    print("Asynchronous Tool Markdown:")
    print(async_tool.to_markdown())
    print("Asynchronous Tool Docstring:")
    print(async_tool.to_docstring())
    print("Execution result (sync):", async_tool.execute(name="Alice"))
    print("Execution result (async):", asyncio.run(async_tool.async_execute(name="Alice")))
    print()

    # Comprehensive tool with complex types
    from typing import Dict, List

    def process_data(data: List[int], options: Dict[str, bool] = {}) -> Dict[str, int]:
        """Process a list of integers with options.

        Args:
            data: List of integers to process.
            options: Dictionary of options.

        Returns:
            A dictionary with results.
        """
        return {str(i): i for i in data}

    complex_tool = create_tool(process_data)
    print("Complex Tool Markdown:")
    print(complex_tool.to_markdown())
    print("Complex Tool Docstring:")
    print(complex_tool.to_docstring())
    print("Execution result (sync):", complex_tool.execute(data=[1, 2, 3]))
    print()

    # Comprehensive tool for to_docstring demonstration with custom return type
    docstring_tool = Tool(
        name="sample_tool",
        description="A sample tool for testing docstring generation.",
        arguments=[
            ToolArgument(name="x", arg_type="int", description="The first number", required=True),
            ToolArgument(name="y", arg_type="float", description="The second number", default="0.0", example="1.5"),
            ToolArgument(name="verbose", arg_type="boolean", description="Print extra info", default="False")
        ],
        return_type="int",
        return_description="The computed result of the operation."
    )
    print("Comprehensive Tool Markdown:")
    print(docstring_tool.to_markdown())
    print("Comprehensive Tool Docstring with Custom Return Type:")
    print(docstring_tool.to_docstring())

    from dataclasses import dataclass

    @dataclass
    class Point:
        x: int
        y: int

    async def distance(point1: Point, point2: Point) -> float:
        """
        Calculate the Euclidean distance between two points.

        Args:
            point1: First point with x and y coordinates.
            point2: Second point with x and y coordinates.

        Returns:
            The Euclidean distance between two points.
        """
        return ((point1.x - point2.x) ** 2 + (point1.y - point2.y) ** 2) ** 0.5

    distance_tool = create_tool(distance)
    print("Distance Tool Markdown:")
    print(distance_tool.to_markdown())
    print("Distance Tool Docstring:")
    print(distance_tool.to_docstring())
    print("Execution result (sync):", distance_tool.execute(point1=Point(x=1, y=2), point2=Point(x=4, y=6)))
    print()