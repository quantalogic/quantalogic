"""Tool for tracking and returning paths of files created during a process."""

from typing import List
from pydantic import Field

from quantalogic.tools.tool import Tool, ToolArgument


class FileTrackerTool(Tool):
    """Tool for tracking and returning file paths created during a process.""" 
    name: str = "file_tracker_tool"
    description: str = "Tracks and returns file paths created during a process."
    need_validation: bool = False
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
    execute = lambda self, file_path: file_path