"""Tool for reading a file or HTTP content and returning its content."""

from urllib.parse import urlparse

from quantalogic.tools.tool import Tool, ToolArgument
from quantalogic.utils.read_file import read_file
from quantalogic.utils.read_http_text_content import read_http_text_content

MAX_LINES = 3000


class ReadFileTool(Tool):
    """Tool for reading a file or HTTP content and returning its content."""

    name: str = "read_file_tool"
    description: str = (
        f"Reads a local file content and returns its content."
        f"Cut to {MAX_LINES} first lines.\n"
        "Don't use on HTML files and large files."
        "Prefer to use read file block tool to don't fill the memory."
    )
    arguments: list = [
        ToolArgument(
            name="file_path",
            arg_type="string",
            description="The path to the file to read.",
            required=True,
            example="/path/to/file.txt",
        ),
    ]

    def _is_url(self, path: str) -> bool:
        """Check if the given path is a valid URL."""
        try:
            result = urlparse(path)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False

    def _truncate_content(self, content: str) -> str:
        """Truncate the content to the first MAX_LINES lines."""
        lines = content.splitlines()
        truncated_lines = lines[:MAX_LINES]
        truncated_content = "\n".join(truncated_lines)
        if len(lines) > MAX_LINES:
            truncated_content += f"\n\n[The content is too long. Truncated at {MAX_LINES} lines.]"
        return truncated_content

    def execute(self, file_path: str) -> str:
        """Reads a file or HTTP content and returns its content.

        Args:
            file_path (str): The path to the file or URL to read.

        Returns:
            str: The content of the file or HTTP content.
        """
        if self._is_url(file_path):
            # Handle HTTP content
            content, error = read_http_text_content(file_path)
            if error:
                return f"Error reading URL {file_path}: {error}"
            truncated_content = self._truncate_content(content)
            result = f"{truncated_content}"
            return result
        else:
            # Handle local file
            try:
                content = read_file(file_path)
                truncated_content = self._truncate_content(content)
                result = f"{truncated_content}"
                return result
            except Exception as e:
                return f"Error reading file {file_path}: {str(e)}"


if __name__ == "__main__":
    tool = ReadFileTool()
    print(tool.to_markdown())
