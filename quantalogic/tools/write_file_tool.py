"""Tool for writing a file and returning its content."""

import os
from pathlib import Path

from loguru import logger
from pydantic import Field

from quantalogic.tools.tool import Tool, ToolArgument


class WriteFileTool(Tool):
    """Tool for writing a text file in /tmp directory."""

    name: str = "write_file_tool"
    description: str = "Writes a file with the given content in /tmp directory. The tool will fail if the file already exists when not used in append mode."
    need_validation: bool = True

    disable_ensure_tmp_path: bool = Field(default=False)

    arguments: list = Field(
        default=[
            ToolArgument(
                name="file_path",
                arg_type="string",
                description="The path to the file to write. By default, paths will be forced to /tmp directory unless disable_ensure_tmp_path is enabled. Can include subdirectories.",
                required=True,
                example="/tmp/myfile.txt or myfile.txt",
            ),
            ToolArgument(
                name="content",
                arg_type="string",
                description="""The content to write to the file. Use CDATA to escape special characters.
                Don't add newlines at the beginning or end of the content.
                """,
                required=True,
                example="Hello, world!",
            ),
            ToolArgument(
                name="append_mode",
                arg_type="string",
                description="""Append mode. If true, the content will be appended to the end of the file.
                """,
                required=False,
                example="False",
            ),
            ToolArgument(
                name="overwrite",
                arg_type="string",
                description="Overwrite mode. If true, existing files can be overwritten. Defaults to False.",
                required=False,
                example="False",
                default="False",
            ),
        ],
    )

    def _ensure_tmp_path(self, file_path: str) -> str:
        """Ensures the file path is within /tmp directory.

        Args:
            file_path (str): The original file path

        Returns:
            str: Normalized path within /tmp

        Raises:
            ValueError: If the path attempts to escape /tmp
        """
        # Ensure /tmp exists and is writable
        tmp_dir = Path("/tmp")
        if not (tmp_dir.exists() and os.access(tmp_dir, os.W_OK)):
            raise ValueError("Error: /tmp directory is not accessible")

        # If path doesn't start with /tmp, prepend it
        if not file_path.startswith("/tmp/"):
            file_path = os.path.join("/tmp", file_path.lstrip("/"))

        # Resolve the absolute path and check if it's really in /tmp
        real_path = os.path.realpath(file_path)
        if not real_path.startswith("/tmp/"):
            raise ValueError("Error: Cannot write files outside of /tmp directory")

        return real_path

    def execute(self, file_path: str, content: str, append_mode: str = "False", overwrite: str = "False") -> str:
        """Writes a file with the given content in /tmp directory.

        Args:
            file_path (str): The path to the file to write (will be forced to /tmp).
            content (str): The content to write to the file.
            append_mode (str, optional): If true, append content to existing file. Defaults to "False".
            overwrite (str, optional): If true, overwrite existing file. Defaults to "False".

        Returns:
            str: Status message with file path and size.

        Raises:
            FileExistsError: If the file already exists and append_mode is False and overwrite is False.
            ValueError: If attempting to write outside /tmp or if /tmp is not accessible.
        """
        try:
            # Convert mode strings to booleans
            append_mode_bool = append_mode.lower() in ["true", "1", "yes"]
            overwrite_bool = overwrite.lower() in ["true", "1", "yes"]

            # Ensure path is in /tmp and normalize it
            if not self.disable_ensure_tmp_path:
                file_path = self._ensure_tmp_path(file_path)

            # Ensure parent directory exists (only within /tmp)
            parent_dir = os.path.dirname(file_path)
            if parent_dir.startswith("/tmp/"):
                os.makedirs(parent_dir, exist_ok=True)

            # Determine file write mode based on append_mode
            mode = "a" if append_mode_bool else "w"

            # Check if file already exists and not in append mode and not in overwrite mode
            if os.path.exists(file_path) and not append_mode_bool and not overwrite_bool:
                raise FileExistsError(
                    f"File {file_path} already exists. Set append_mode=True to append or overwrite=True to overwrite."
                )

            with open(file_path, mode, encoding="utf-8") as f:
                f.write(content)
            
            file_size = os.path.getsize(file_path)
            return f"File {file_path} {'appended to' if append_mode_bool else 'written'} successfully. Size: {file_size} bytes."

        except (ValueError, FileExistsError) as e:
            logger.error(f"Write file error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error writing file: {str(e)}")
            raise ValueError(f"Failed to write file: {str(e)}")


if __name__ == "__main__":
    tool = WriteFileTool()
    print(tool.to_markdown())
