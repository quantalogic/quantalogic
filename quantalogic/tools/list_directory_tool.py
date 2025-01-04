"""Tool for listing the contents of a directory."""
import os

from quantalogic.tools.tool import Tool, ToolArgument


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
            type="string",
            description="Maximum depth for recursive directory listing.",
            required=False,
            default="1",
            example="1",
        ),
        ToolArgument(
            name="start_line",
            type="string",
            description="Starting line number for paginated results (1-based).",
            required=False,
            default="1",
            example="1",
        ),
        ToolArgument(
            name="end_line",
            type="string",
            description="Ending line number for paginated results (1-based).",
            required=False,
            default="200",
            example="200",
        ),
    ]

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Converts file size in bytes to a human-readable format.

        Args:
            size_bytes (int): Size of the file in bytes.

        Returns:
            str: Human-readable file size.
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def execute(self, directory_path: str, recursive: str = "false", max_depth: str = "2",
               start_line: str = "1", end_line: str = "200") -> str:
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

        # Determine recursive listing mode
        # Convert input to boolean, defaulting to non-recursive
        is_recursive = recursive.lower() == "true"

        # Safe integer conversion with default values
        # Handles various input scenarios: empty strings, non-numeric inputs, etc.
        def safe_int_convert(value: str, default: int) -> int:
            """
            Safely convert string to integer with a fallback default.
            
            This helper prevents errors from invalid or empty string inputs,
            ensuring the method can handle unexpected input gracefully.
            
            Args:
                value (str): String to convert to integer
                default (int): Value to return if conversion fails
            
            Returns:
                int: Converted integer or default value
            """
            try:
                return int(value) if value and value.strip() else default
            except ValueError:
                return default

        # Convert parameters safely with sensible defaults
        # Ensures consistent behavior even with unexpected inputs
        max_depth_int = safe_int_convert(max_depth, 2)
        start = max(0, safe_int_convert(start_line, 1) - 1)  # Convert to 0-based index
        end = safe_int_convert(end_line, 200)

        try:
            # Recursive directory listing
            # Uses os.walk to traverse directory tree with controlled depth
            if is_recursive:
                all_lines = []
                for root, dirs, files in os.walk(directory_path):
                    # Calculate directory nesting level
                    level = root.replace(directory_path, '').count(os.sep)
                    
                    # Respect max_depth to prevent overwhelming output
                    if level > max_depth_int:
                        continue
                    
                    # Create indented representation of directory structure
                    indent = '│   ' * (level - 1) + '├── ' if level > 0 else ''
                    all_lines.append(f"{indent}{os.path.basename(root)}/ <DIR>")
                    
                    # List subdirectories
                    for d in dirs:
                        sub_indent = '│   ' * level + '├── '
                        all_lines.append(f"{sub_indent}{d}/ <DIR>")
                    
                    # List files with human-readable sizes
                    for f in files:
                        sub_indent = '│   ' * level + '├── '
                        file_path = os.path.join(root, f)
                        file_size = os.path.getsize(file_path)
                        all_lines.append(f"{sub_indent}{f} ({self._format_size(file_size)})")
            else:
                # Non-recursive directory listing
                # Simple, flat listing of immediate directory contents
                all_lines = []
                items = os.listdir(directory_path)
                for item in items:
                    item_path = os.path.join(directory_path, item)
                    if os.path.isdir(item_path):
                        all_lines.append(f"├── {item}/ <DIR>")
                    else:
                        file_size = os.path.getsize(item_path)
                        all_lines.append(f"├── {item} ({self._format_size(file_size)})")

            # Handle empty directory scenario
            # Provide a clear, informative response
            if not all_lines:
                return "The directory is empty."

            # Pagination logic
            # Ensures we don't return more data than requested
            total_lines = len(all_lines)
            end = min(end, total_lines)
            is_last_block = end >= total_lines
            
            # Extract paginated content
            # Handles cases where requested range might exceed available items
            paginated_content = all_lines[start:end]
            content = "\n".join(paginated_content) if paginated_content else "No content in this range."

            # Create informative header and footer
            # Provides context about the listing
            header = f"Contents of directory: {directory_path}\n"
            footer = f"\nShowing lines {start + 1}-{end} of {total_lines}"
            if is_last_block:
                footer += " (last block)"
            footer += "\nEnd of directory listing."

            # Return formatted directory listing
            return header + content + footer

        except Exception as e:
            # Catch-all error handling
            # Ensures a meaningful error message is always returned
            raise ValueError(f"Error listing directory '{directory_path}': {str(e)}")


if __name__ == "__main__":
    tool = ListDirectoryTool()
    print(tool.to_markdown())