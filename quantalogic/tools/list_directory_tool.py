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
            example="2",
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

    def execute(self, directory_path: str, recursive: str = "false", max_depth: str = "2") -> str:
        """Lists the contents of a directory.

        Args:
            directory_path (str): The path to the directory to list.
            recursive (str): Whether to list directories recursively ("true" or "false").
            max_depth (str): Maximum depth for recursive directory listing.

        Returns:
            str: A formatted string of directory contents.

        Raises:
            ValueError: If the directory does not exist or is not a directory.
        """
        # Handle tilde expansion
        if directory_path.startswith("~"):
            directory_path = os.path.expanduser(directory_path)

        # Validate the directory path
        if not os.path.exists(directory_path):
            raise ValueError(f"The directory '{directory_path}' does not exist.")
        if not os.path.isdir(directory_path):
            raise ValueError(f"The path '{directory_path}' is not a directory.")

        # Determine if recursive listing is needed
        is_recursive = recursive.lower() == "true"

        # Convert max_depth to integer, defaulting to 2 if empty or invalid
        try:
            max_depth_int = int(max_depth) if max_depth else 2
        except ValueError:
            max_depth_int = 2

        try:
            if is_recursive:
                # Use os.walk for recursive directory listing
                directories = []
                for root, dirs, files in os.walk(directory_path):
                    level = root.replace(directory_path, '').count(os.sep)
                    if level > max_depth_int:
                        continue
                    indent = '│   ' * (level - 1) + '├── ' if level > 0 else ''
                    directories.append(f"{indent}{os.path.basename(root)}/ <DIR>")
                    for d in dirs:
                        sub_indent = '│   ' * level + '├── '
                        directories.append(f"{sub_indent}{d}/ <DIR>")
                    for f in files:
                        sub_indent = '│   ' * level + '├── '
                        file_path = os.path.join(root, f)
                        file_size = os.path.getsize(file_path)
                        directories.append(f"{sub_indent}{f} ({self._format_size(file_size)})")
                content = "\n".join(directories) if directories else "The directory is empty."
            else:
                # Use os.listdir for non-recursive listing
                items = os.listdir(directory_path)
                if items:
                    content = []
                    for item in items:
                        item_path = os.path.join(directory_path, item)
                        if os.path.isdir(item_path):
                            content.append(f"├── {item}/ <DIR>")
                        else:
                            file_size = os.path.getsize(item_path)
                            content.append(f"├── {item} ({self._format_size(file_size)})")
                    content = "\n".join(content)
                else:
                    content = "The directory is empty."

            # Add header and footer for better context
            header = f"Contents of directory: {directory_path}\n"
            footer = "\nEnd of directory listing."
            return header + content + footer

        except Exception as e:
            raise ValueError(f"Error listing directory '{directory_path}': {str(e)}")


if __name__ == "__main__":
    tool = ListDirectoryTool()
    print(tool.to_markdown())