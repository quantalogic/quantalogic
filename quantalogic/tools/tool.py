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
    default: str | None = Field(default=None, description="The default value for the argument. This parameter is required.")
    example: str | None = Field(default=None, description="An example value to illustrate the argument's usage.")
    need_validation: bool = Field(default=False, description="Indicates if the argument needs validation.")


class ToolDefinition(BaseModel):
    """Base class for defining tool configurations without execution logic.

    Attributes:
        name: Unique name of the tool.
        description: Brief description of the tool's functionality.
        arguments: List of arguments the tool accepts.
        need_validation: Flag to indicate if tool requires validation.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    name: str = Field(..., description="The unique name of the tool.")
    description: str = Field(..., description="A brief description of what the tool does.")
    arguments: list[ToolArgument] = Field(default_factory=list, description="A list of arguments the tool accepts.")
    need_validation: bool = Field(default=False, description="Indicates if the tool needs validation.")

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

        # Parameters section
        if self.arguments:
            markdown += "- **Parameters**:\n"
            for arg in self.arguments:
                required_status = "required" if arg.required else "optional"
                # Prioritize example, then default, then create a generic description
                value_info = ""
                if arg.example is not None:
                    value_info = f" (example: `{arg.example}`)"
                elif arg.default is not None:
                    value_info = f" (default: `{arg.default}`)"

                markdown += (
                    f"  - `{arg.name}`: "
                    f"({required_status}{value_info})\n"
                    f"    {arg.description or 'No description provided.'}\n"
                )
            markdown += "\n"

        # Usage section with XML-style example
        markdown += "**Usage**:\n"
        markdown += "```xml\n"
        markdown += f"<{self.name}>\n"

        # Generate example parameters
        for arg in self.arguments:
            # Prioritize example, then default, then create a generic example
            example_value = arg.example or arg.default or f"Your {arg.name} here"
            markdown += f"  <{arg.name}>{example_value}</{arg.name}>\n"

        markdown += f"</{self.name}>\n"
        markdown += "```\n"

        return markdown


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
