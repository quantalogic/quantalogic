
Your task is to implement a new Tool SearchDefinitionNames that uses tree sitter to search for definition names in a directory, an language name, and a file pattern.

The tool will return a string with the following format the list of definition names grouped by file name, with line numbers and context.

<search_definition_names>
    <!-- directory path to search in  -->
    <direrctory_path>./path/to</direrctory_path>
    <!-- tree sitter language name -->
    <language_name>python</language_name>
    <!-- Optional glob pattern to filter files (default: '*') -->
    <file_pattern>**/*.py</file_pattern>
</search_definition_names>

Implement the support for python first.

----


# Table of Contents
- quantalogic/tools/read_file_block_tool.py
- quantalogic/tools/tool.py

## File: quantalogic/tools/read_file_block_tool.py

- Extension: .py
- Language: python
- Size: 4997 bytes
- Created: 2024-12-29 08:05:45
- Modified: 2024-12-29 08:05:45

### Code

```python
"""Tool for reading a block of lines from a file."""
import os

from pydantic import field_validator

from quantalogic.tools.tool import Tool, ToolArgument

MAX_LINES = 200

class ReadFileBlockTool(Tool):
    """Tool for reading a block of lines from a file."""

    name: str = "read_file_block_tool"
    description: str = (
        "Reads a block of lines from a file and returns its content."
        f"Can return only a max of {MAX_LINES} lines at a time."
        "Use multiple read_file_block_tool to read larger files."
    )
    arguments: list = [
        ToolArgument(
            name="file_path",
            type="string",
            description="The path to the file to read.",
            required=True,
            example="/path/to/file.txt",
        ),
        ToolArgument(
            name="line_start",
            type="int",
            description="The starting line number (1-based index).",
            required=True,
            example="10",
        ),
        ToolArgument(
            name="line_end",
            type="int",
            description="The ending line number (1-based index).",
            required=True,
            example="200",
        ),
    ]

    @field_validator("line_start", "line_end", check_fields=False)
    @classmethod
    def validate_line_numbers(cls, v: int, info) -> int:
        """Validate that line_start and line_end are positive integers and line_start <= line_end."""
        if not isinstance(v, int):
            raise ValueError("Line numbers must be integers.")

        if v <= 0:
            raise ValueError("Line numbers must be positive integers.")

        # If both line_start and line_end are being validated
        if info.data and len(info.data) >= 2:
            line_start = info.data.get("line_start")
            line_end = info.data.get("line_end")

            if line_start is not None and line_end is not None and line_start > line_end:
                raise ValueError("line_start must be less than or equal to line_end.")

        return v

    def execute(self, file_path: str, line_start: int, line_end: int) -> str:
        """Reads a block of lines from a file and returns its content.

        Args:
            file_path (str): The path to the file to read.
            line_start (int): The starting line number (1-based index).
            line_end (int): The ending line number (1-based index).

        Returns:
            str: The content of the specified block of lines.

        Raises:
            ValueError: If line numbers are invalid or file cannot be read
            FileNotFoundError: If the file does not exist
            PermissionError: If there are permission issues reading the file
        """
        try:
            # Validate and convert line numbers
            line_start = int(line_start)
            line_end = int(line_end)
            
            if line_start <= 0 or line_end <= 0:
                raise ValueError("Line numbers must be positive integers")
            if line_start > line_end:
                raise ValueError("line_start must be less than or equal to line_end")

            # Handle path expansion and normalization
            file_path = os.path.expanduser(file_path)
            file_path = os.path.abspath(file_path)

            # Validate file exists and is readable
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            if not os.access(file_path, os.R_OK):
                raise PermissionError(f"Permission denied reading file: {file_path}")

            # Read file with explicit encoding and error handling
            with open(file_path, encoding='utf-8', errors='strict') as f:
                lines = f.readlines()

            # Validate line numbers against file length
            if line_start > len(lines):
                raise ValueError(f"line_start {line_start} exceeds file length {len(lines)}")

            # Calculate actual end line respecting MAX_LINES and file bounds
            actual_end = min(line_end, line_start + MAX_LINES - 1, len(lines))
            
            # Extract the block of lines
            block = lines[line_start - 1 : actual_end]

            # Format result with clear boundaries and metadata
            result = [
                f"==== File: {file_path} ====",
                f"==== Lines: {line_start}-{actual_end} of {len(lines)} ====",
                "==== Content ====",
                "".join(block).rstrip(),
                "==== End of Block ===="
            ]

            return "\n".join(result)

        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid line numbers: {e}")
        except UnicodeDecodeError:
            raise ValueError("File contains invalid UTF-8 characters")
        except Exception as e:
            raise RuntimeError(f"Error reading file: {e}")


if __name__ == "__main__":
    tool = ReadFileBlockTool()
    print(tool.to_markdown())

```

## File: quantalogic/tools/tool.py

- Extension: .py
- Language: python
- Size: 5495 bytes
- Created: 2024-12-23 08:40:25
- Modified: 2024-12-23 08:40:25

### Code

```python
"""Module for defining tool arguments and base tool classes.

This module provides base classes and data models for creating configurable tools
with type-validated arguments and execution methods.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ToolArgument(BaseModel):
    """Represents an argument for a tool with validation and description.

    Attributes:
        name: The name of the argument.
        type: The type of the argument (string or integer).
        description: Optional description of the argument.
        required: Indicates if the argument is mandatory.
        default: Optional default value for the argument.
        example: Optional example value to illustrate the argument's usage.
    """
    name: str = Field(..., description="The name of the argument.")
    type: str = Field(
        ..., 
        description="The type of the argument (e.g., string or integer).",
        pattern="^(string|int)$"
    )
    description: str | None = Field(
        None, description="A brief description of the argument."
    )
    required: bool = Field(
        default=False, description="Indicates if the argument is required."
    )
    default: str | None = Field(
        None, description="The default value for the argument."
    )
    example: str | None = Field(
        None, description="An example value to illustrate the argument's usage."
    )
    need_validation: bool = Field(
        default=False, description="Indicates if the argument needs validation."
    )


class Tool(BaseModel):
    """Base class for defining tools with configurable arguments and execution.

    Attributes:
        name: Unique name of the tool.
        description: Brief description of the tool's functionality.
        arguments: List of arguments the tool accepts.
        need_validation: Flag to indicate if tool requires validation.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    
    name: str = Field(..., description="The unique name of the tool.")
    description: str = Field(
        ..., description="A brief description of what the tool does."
    )
    arguments: list[ToolArgument] = Field(
        default_factory=list, description="A list of arguments the tool accepts."
    )
    need_validation: bool = Field(
        default=False, description="Indicates if the tool needs validation."
    )

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
                ToolArgument(**arg) if isinstance(arg, dict) else arg
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
            example_value = (
                arg.example or 
                arg.default or 
                f"Your {arg.name} here"
            )
            markdown += f"  <{arg.name}>{example_value}</{arg.name}>\n"
        
        markdown += f"</{self.name}>\n"
        markdown += "```\n"
        
        return markdown

```

Example of tree sitter:

/*
- class definitions
- function definitions
*/
export default `
(class_definition
  name: (identifier) @name.definition.class) @definition.class

(function_definition
  name: (identifier) @name.definition.function) @definition.function
`
