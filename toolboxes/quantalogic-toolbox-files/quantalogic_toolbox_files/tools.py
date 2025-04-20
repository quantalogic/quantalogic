from dataclasses import dataclass
from typing import List


@dataclass
class FileInfo:
    name: str
    path: str
    is_dir: bool
    size: int


async def list_files_tool(path: str) -> List[FileInfo]:
    """List files in a directory and return FileInfo dataclasses."""
    import os
    files: List[FileInfo] = []
    for name in os.listdir(path):
        full_path = os.path.join(path, name)
        is_dir = os.path.isdir(full_path)
        size = os.path.getsize(full_path) if not is_dir else 0
        files.append(FileInfo(name=name, path=full_path, is_dir=is_dir, size=size))
    return files


async def create_directory_tool(path: str) -> str:
    """Create a directory at the given path."""
    import os
    os.makedirs(path, exist_ok=True)
    return f"Directory created at {path}"


async def write_file_tool(path: str, content: str) -> str:
    """Write content to a new file at path. Raises if file exists. Creates directories if needed."""
    import os
    if os.path.exists(path):
        raise FileExistsError(f"Cannot create file: {path} already exists")
    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"File written at {path}"


async def read_file_tool(path: str) -> str:
    """Read content from a file at the given path."""
    import os
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    if os.path.isdir(path):
        raise IsADirectoryError(f"Expected file but found directory: {path}")
    with open(path, encoding="utf-8") as f:
        return f.read()


async def read_file_block_tool(path: str, start_line: int, end_line: int) -> str:
    """Read lines [start_line, end_line] from file, report total lines and indicate if EOF is reached."""
    import os
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    if os.path.isdir(path):
        raise IsADirectoryError(f"Expected file but found directory: {path}")
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    total = len(lines)
    # clamp bounds
    start = max(1, start_line)
    end = min(end_line, total)
    block = lines[start-1:end]
    eof = end >= total
    content = "".join(block)
    return f"```text\n{content}```\nTotal lines: {total}\nEnd of file reached: {eof}"


async def list_files_markdown_table(path: str) -> str:
    """List files in directory and return markdown table."""
    files = await list_files_tool(path)
    lines = ["| Name | Path | Is Dir | Size |", "|---|---|---|---|"]
    for f in files:
        lines.append(f"| {f.name} | {f.path} | {f.is_dir} | {f.size} |")
    return "\n".join(lines)


def get_tools() -> list:
    """Return a list of tool functions defined in this module."""
    return [create_directory_tool, write_file_tool, read_file_tool, read_file_block_tool, list_files_markdown_table]