"""Tool for listing the contents of a directory."""

import os

from quantalogic.tools.tool import Tool, ToolArgument
from quantalogic.utils.git_ls import git_ls


class ListDirectoryTool(Tool):
    """Lists directory contents with pagination and .gitignore support."""

    name: str = "list_directory_tool"
    description: str = "Lists directory contents with pagination and .gitignore filtering"
    arguments: list[ToolArgument] = [
        ToolArgument(
            name="directory_path",
            arg_type="string",
            description="Absolute or relative path to target directory",
            required=True,
            example="~/documents/projects",
        ),
        ToolArgument(
            name="recursive",
            arg_type="string",
            description="Enable recursive traversal (true/false)",
            required=False,
            default="false",
            example="true",
        ),
        ToolArgument(
            name="max_depth",
            arg_type="int",
            description="Maximum directory traversal depth",
            required=False,
            default="1",
            example="1",
        ),
        ToolArgument(
            name="start_line",
            arg_type="int",
            description="First line to return in paginated results",
            required=False,
            default="1",
            example="1",
        ),
        ToolArgument(
            name="end_line",
            arg_type="int",
            description="Last line to return in paginated results",
            required=False,
            default="200",
            example="200",
        ),
    ]

    def execute(
        self,
        directory_path: str,
        recursive: str = "false",
        max_depth: str = "1",
        start_line: str = "1",
        end_line: str = "200",
    ) -> str:
        """
        List directory contents with pagination and .gitignore support.

        Args:
            directory_path: Absolute or relative path to target directory
            recursive: Enable recursive traversal (true/false)
            max_depth: Maximum directory traversal depth
            start_line: First line to return in paginated results
            end_line: Last line to return in paginated results

        Returns:
            str: Paginated directory listing with metadata

        Raises:
            ValueError: For invalid directory paths or pagination parameters
        """
        # Expand user home directory to full path
        # This ensures compatibility with '~' shorthand for home directory
        if directory_path.startswith("~"):
            directory_path = os.path.expanduser(directory_path)

        # Validate directory existence and type
        # Fail early with clear error messages if path is invalid
        if not os.path.exists(directory_path):
            raise ValueError(f"The directory '{directory_path}' does not exist.")
        if not os.path.isdir(directory_path):
            raise ValueError(f"The path '{directory_path}' is not a directory.")

        # Safely convert inputs with default values
        start = int(start_line or "1")
        end = int(end_line or "200")
        max_depth_int = int(max_depth or "1")
        is_recursive = (recursive or "false").lower() == "true"

        # Validate pagination parameters
        if start > end:
            raise ValueError("start_line must be less than or equal to end_line.")

        try:
            # Use git_ls for directory listing with .gitignore support
            all_lines = git_ls(
                directory_path=directory_path,
                recursive=is_recursive,
                max_depth=max_depth_int,
                start_line=start,
                end_line=end,
            )
            return all_lines
        except Exception as e:
            import traceback

            traceback.print_exc()
            return f"Error: {str(e)} occurred during directory listing. See logs for details."


if __name__ == "__main__":
    tool = ListDirectoryTool()
    current_directory = os.getcwd()
    tool.execute(directory_path=current_directory, recursive="true")
    print(tool.to_markdown())
