Write a Tool Search Replace Context Tool SearchReplaceTool that will search and replace text blocks to update a file.

Example of Tool:

# Table of Contents
- quantalogic/tools/write_file_tool.py

## File: quantalogic/tools/write_file_tool.py

- Extension: .py
- Language: python
- Size: 2070 bytes
- Created: 2024-12-25 16:41:41
- Modified: 2024-12-25 16:41:41

### Code

```python
"""Tool for writing a file and returning its content."""
import os

from quantalogic.tools.tool import Tool, ToolArgument


class WriteFileTool(Tool):
    """Tool for writing a text file."""

    name: str = "write_file"
    description: str = "Writes a file with the given content."
    need_validation: bool = True
    arguments: list = [
        ToolArgument(
            name="file_path",
            type="string",
            description="The path to the file to write. Using an absolute path is recommended.",
            required=True,
            example="/path/to/file.txt",
        ),
        ToolArgument(
            name="content",
            type="string",
            description="""
            The content to write to the file. Use CDATA to escape special characters.
            Don't add newlines at the beginning or end of the content.
            """,
            required=True,
            example="Hello, world!",
        ),
    ]

    def execute(self, file_path: str, content: str) -> str:
        """Writes a file with the given content.

        Args:
            file_path (str): The path to the file to write.
            content (str): The content to write to the file.

        Returns:
            str: The content of the file.
        """
        ## Handle tilde expansion
        if file_path.startswith("~"):
            # Expand the tilde to the user's home directory
            file_path = os.path.expanduser(file_path)

        # Convert relative paths to absolute paths using current working directory
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(os.path.join(os.getcwd(), file_path))

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        file_size = os.path.getsize(file_path)
        return f"File {file_path} written successfully. Size: {file_size} bytes."


if __name__ == "__main__":
    tool = WriteFileTool()
    print(tool.to_markdown())

```

Example of search and replace: Blocks

mathweb/flask/app.py
{fence[0]}python
<<<<<<< SEARCH
from flask import Flask
=======
import math
from flask import Flask
>>>>>>> REPLACE
{fence[1]}

mathweb/flask/app.py
{fence[0]}python
<<<<<<< SEARCH
def factorial(n):
    "compute factorial"

    if n == 0:
        return 1
    else:
        return n * factorial(n-1)

=======
>>>>>>> REPLACE
{fence[1]}

mathweb/flask/app.py
{fence[0]}python
<<<<<<< SEARCH
    return str(factorial(n))
=======
    return str(math.factorial(n))
>>>>>>> REPLACE
{fence[1]}
""",
        ),
        dict(
            role="user",
            content="Refactor hello() into its own file.",
        ),
        dict(
            role="assistant",
            content="""To make this change we need to modify `main.py` and make a new file `hello.py`:

1. Make a new hello.py file with hello() in it.
2. Remove hello() from main.py and replace it with an import.

Here are the *SEARCH/REPLACE* blocks:

hello.py
{fence[0]}python
<<<<<<< SEARCH
=======
def hello():
    "print a greeting"

    print("hello")
>>>>>>> REPLACE
{fence[1]}

main.py
{fence[0]}python
<<<<<<< SEARCH
def hello():
    "print a greeting"

    print("hello")
=======
from hello import hello
>>>>>>> REPLACE
{fence[1]}
""",
        ),
    ]

    system_reminder = """# *SEARCH/REPLACE block* Rules:
