"""Module for defining tool arguments and base tool classes.

This module provides base classes and data models for creating configurable tools
with type-validated arguments and execution methods.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
                    f"  - `{arg.name}`: "
                    f"({required_status}{value_info})\n"
                    f"    {arg.description or ''}\n"
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

        return [
            arg for arg in self.arguments if properties_injectable.get(arg.name) is None
        ]


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

    def execute(self, **kwargs) -> str:
        """Execute the tool with provided arguments.

        Args:
            **kwargs: Keyword arguments for tool execution.

        Raises:
            NotImplementedError: If the method is not implemented by a subclass.

        Returns:
            A string representing the result of tool execution.
        """
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
        return {
            name: value 
            for name, value in properties.items() 
            if value is not None and name in argument_names
        }


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
