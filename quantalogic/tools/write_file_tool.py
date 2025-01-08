"""Tool for writing a file and returning its content."""

import os

from quantalogic.tools.tool import Tool, ToolArgument


class WriteFileTool(Tool):
    """Tool for writing a text file."""

    name: str = "write_file_tool"
    description: str = "Writes a file with the given content. The tool will fail if the file already exists when not used in append mode."
    need_validation: bool = True
    arguments: list = [
        ToolArgument(
            name="file_path",
            arg_type="string",
            description="The path to the file to write. Using an absolute path is recommended.",
            required=True,
            example="/path/to/file.txt",
        ),
        ToolArgument(
            name="content",
            arg_type="string",
            description="""
            The content to write to the file. Use CDATA to escape special characters.
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
    ]

    def execute(self, file_path: str, content: str, append_mode: str = "False", overwrite: str = "False") -> str:
        """Writes a file with the given content.

        Args:
            file_path (str): The path to the file to write.
            content (str): The content to write to the file.
            append_mode (str, optional): If true, append content to existing file. Defaults to "False".
            overwrite (str, optional): If true, overwrite existing file. Defaults to "False".

        Returns:
            str: The content of the file.

        Raises:
            FileExistsError: If the file already exists and append_mode is False and overwrite is False.
        """
        # Convert mode strings to booleans
        append_mode_bool = append_mode.lower() in ["true", "1", "yes"]
        overwrite_bool = overwrite.lower() in ["true", "1", "yes"]

        ## Handle tilde expansion
        if file_path.startswith("~"):
            # Expand the tilde to the user's home directory
            file_path = os.path.expanduser(file_path)

        # Convert relative paths to absolute paths using current working directory
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(os.path.join(os.getcwd(), file_path))

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

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


if __name__ == "__main__":
    tool = WriteFileTool()
    print(tool.to_markdown())
