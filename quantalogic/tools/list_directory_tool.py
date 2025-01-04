"""Tool for listing the contents of a directory."""

import os

from quantalogic.tools.tool import Tool, ToolArgument
from quantalogic.tools.utils.git_ls import git_ls


class ListDirectoryTool(Tool):
    """Tool to list the contents of a directory."""

    name: str = "list_directory_tool"
    description: str = "Lists the contents of a specified directory."
    arguments: list[ToolArgument] = [
        ToolArgument(
            name="directory_path",
            type="string",
            description="The path to the directory to list.",
            required=True,
            example="~/documents/projects",
        ),
        ToolArgument(
            name="recursive",
            type="string",
            description="Whether to list directories recursively (true/false).",
            required=False,
            default="false",
            example="true",
        ),
        ToolArgument(
            name="max_depth",
            type="int",
            description="Maximum depth for recursive directory listing.",
            required=False,
            default="1",
            example="1",
        ),
        ToolArgument(
            name="start_line",
            type="int",
            description="Starting line number for paginated results (1-based).",
            required=False,
            default="1",
            example="1",
        ),
        ToolArgument(
            name="end_line",
            type="int",
            description="Ending line number for paginated results (1-based).",
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
        List directory contents with flexible and robust pagination.

        This method provides a comprehensive directory listing with several key features:
        - Supports both recursive and non-recursive directory traversal
        - Handles pagination to manage large directory listings
        - Provides human-readable file sizes
        - Robust against invalid input parameters

        The method is designed to be flexible and handle various edge cases:
        - Expands user home directory paths (e.g., '~')
        - Safely converts string inputs to integers
        - Provides meaningful default values
        - Generates a structured output for easy consumption

        Args:
            directory_path (str): Absolute or relative path to the directory.
            recursive (str): Flag to enable recursive directory listing.
                             Accepts "true" or "false" (case-insensitive).
            max_depth (str): Limit the depth of recursive traversal.
                             Prevents overwhelming output for deep directory structures.
            start_line (str): Starting line for paginated results.
                              Useful for handling large directory listings.
            end_line (str): Ending line for paginated results.
                            Prevents returning excessive amounts of data.

        Returns:
            str: A formatted directory listing string containing:
                - Header with directory path
                - Paginated list of directory contents
                - Footer with pagination information
                - Contextual information about the listing

        Raises:
            ValueError: If the directory path is invalid or cannot be accessed.
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
