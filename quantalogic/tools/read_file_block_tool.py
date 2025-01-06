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
        "Good to read specific portions of a file. But not adapted when the full file is needed."
        f"Can return only a max of {MAX_LINES} lines at a time."
        "Use multiple read_file_block_tool to read larger files."
    )
    arguments: list = [
        ToolArgument(
            name="file_path",
            arg_type="string",
            description="The path to the file to read.",
            required=True,
            example="/path/to/file.txt",
        ),
        ToolArgument(
            name="line_start",
            arg_type="int",
            description="The starting line number (1-based index).",
            required=True,
            example="10",
        ),
        ToolArgument(
            name="line_end",
            arg_type="int",
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
            with open(file_path, encoding="utf-8", errors="strict") as f:
                lines = f.readlines()

            # Validate line numbers against file length
            if line_start > len(lines):
                raise ValueError(f"line_start {line_start} exceeds file length {len(lines)}")

            # Calculate actual end line respecting MAX_LINES and file bounds
            actual_end = min(line_end, line_start + MAX_LINES - 1, len(lines))

            # Extract the block of lines
            block = lines[line_start - 1 : actual_end]

            # Determine if this is the last block of the file
            is_last_block = actual_end == len(lines)

            # Format result with clear boundaries and metadata
            result = [
                f"==== File: {file_path} ====",
                f"==== Lines: {line_start}-{actual_end} of {len(lines)} ====",
                "==== Content ====",
                "".join(block).rstrip(),
                "==== End of Block ====" + (" [LAST BLOCK SUCCESSFULLY READ]" if is_last_block else ""),
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
