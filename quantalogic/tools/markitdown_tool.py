"""Tool for converting various file formats to Markdown using the MarkItDown library."""

import os
import tempfile
from typing import Optional

from quantalogic.tools.tool import Tool, ToolArgument
from quantalogic.utils.download_http_file import download_http_file

MAX_LINES = 2000  # Maximum number of lines to return when no output file is specified


class MarkitdownTool(Tool):
    """Tool for converting various file formats to Markdown using the MarkItDown library."""

    name: str = "markitdown_tool"
    description: str = (
        "Converts various file formats to Markdown using the MarkItDown library. "
        "Supports both local file paths and URLs (http://, https://). "
        "Supported formats include: PDF, PowerPoint, Word, Excel, HTML"
        "Don't use the output_file_path argument if you want to return the result in markdown directly"
    )
    arguments: list = [
        ToolArgument(
            name="file_path",
            arg_type="string",
            description="The path to the file to convert. Can be a local path or URL (http://, https://).",
            required=True,
            example="/path/to/file.txt or https://example.com/file.pdf",
        ),
        ToolArgument(
            name="output_file_path",
            arg_type="string",
            description="Path to write the Markdown output to. You can use a temp file.",
            required=False,
            example="/path/to/output.md",
        ),
    ]

    def execute(self, file_path: str, output_file_path: Optional[str] = None) -> str:
        """Converts a file to Markdown and returns or writes the content.

        Args:
            file_path (str): The path to the file to convert. Can be a local path or URL.
            output_file_path (str, optional): Optional path to write the Markdown output to.

        Returns:
            str: The Markdown content or a success message.
        """
        try:
            # Handle URL paths first
            if file_path.startswith(("http://", "https://")):
                try:
                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        temp_path = temp_file.name
                        download_http_file(file_path, temp_path)
                        file_path = temp_path
                        is_temp_file = True
                except Exception as e:
                    return f"Error downloading file from URL: {str(e)}"
            else:
                is_temp_file = False
                # Handle local paths
                if file_path.startswith("~"):
                    file_path = os.path.expanduser(file_path)
                if not os.path.isabs(file_path):
                    file_path = os.path.abspath(file_path)

                # Verify file exists
                if not os.path.exists(file_path):
                    return f"Error: File not found at path: {file_path}"

            from markitdown import MarkItDown

            md = MarkItDown()

            # Detect file type if possible
            file_extension = os.path.splitext(file_path)[1].lower()
            supported_extensions = [".pdf", ".pptx", ".docx", ".xlsx", ".html", ".htm"]

            if not file_extension or file_extension not in supported_extensions:
                return f"Error: Unsupported file format. Supported formats are: {', '.join(supported_extensions)}"

            try:
                result = md.convert(file_path)
            except Exception as e:
                return f"Error converting file to Markdown: {str(e)}"

            if output_file_path:
                # Ensure output directory exists
                output_dir = os.path.dirname(output_file_path)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir)

                with open(output_file_path, "w", encoding="utf-8") as f:
                    f.write(result.text_content)
                return f"Markdown content successfully written to {output_file_path}"

            # Handle content truncation
            lines = result.text_content.splitlines()
            if len(lines) > MAX_LINES:
                truncated_content = "\n".join(lines[:MAX_LINES])
                return f"Markdown content truncated to {MAX_LINES} lines:\n{truncated_content}"
            return result.text_content

        except Exception as e:
            return f"Error processing file: {str(e)}"
        finally:
            if is_temp_file and os.path.exists(file_path):
                os.remove(file_path)


if __name__ == "__main__":
    tool = MarkitdownTool()
    print(tool.to_markdown())

    # Example usage:
    print(tool.execute(file_path="./examples/2412.18601v1.pdf"))

    print(tool.execute(file_path="https://arxiv.org/pdf/2412.18601"))
