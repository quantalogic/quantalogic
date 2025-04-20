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


async def list_files_markdown_table(path: str) -> str:
    """List files in directory and return markdown table."""
    files = await list_files_tool(path)
    lines = ["| Name | Path | Is Dir | Size |", "|---|---|---|---|"]
    for f in files:
        lines.append(f"| {f.name} | {f.path} | {f.is_dir} | {f.size} |")
    return "\n".join(lines)


def get_tools() -> list:
    """Return a list of tool functions defined in this module."""
    return [create_directory_tool, write_file_tool, list_files_markdown_table]