"""Tool for listing the contents of a directory."""

import os
from pathlib import Path
from typing import List, Dict
from loguru import logger

from quantalogic.tools.tool import Tool, ToolArgument


class ListDirectoryTool(Tool):
    """Lists directory contents with pagination and .gitignore support."""

    name: str = "list_directory_tool"
    description: str = "Lists directory contents with pagination and .gitignore filtering"
    arguments: list[ToolArgument] = [
        ToolArgument(
            name="directory_path",
            arg_type="string",
            description="Absolute or relative path to target directory",
            required=True,
            example="~/documents/projects",
        ),
        ToolArgument(
            name="recursive",
            arg_type="string",
            description="Enable recursive traversal (true/false)",
            required=False,
            default="false",
            example="true",
        ),
        ToolArgument(
            name="max_depth",
            arg_type="int",
            description="Maximum directory traversal depth",
            required=False,
            default="10",
            example="10",
        ),
        ToolArgument(
            name="start_line",
            arg_type="int",
            description="First line to return in paginated results",
            required=False,
            default="1",
            example="1",
        ),
        ToolArgument(
            name="end_line",
            arg_type="int",
            description="Last line to return in paginated results",
            required=False,
            default="200",
            example="200",
        ),
    ]

    def _list_directory(self, path: Path, max_depth: int, current_depth: int = 0) -> List[Dict]:
        """List directory contents recursively.
        
        Args:
            path: Directory path to list
            max_depth: Maximum recursion depth
            current_depth: Current recursion depth
            
        Returns:
            List of dictionaries containing file/directory information
        """
        if current_depth > max_depth:
            return []

        results = []
        try:
            for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if item.name == ".git":
                    continue
                    
                try:
                    if item.is_file():
                        size = item.stat().st_size
                        results.append({
                            "type": "file",
                            "name": item.name,
                            "size": f"{size} bytes",
                            "path": str(item.relative_to(path.parent))
                        })
                    elif item.is_dir():
                        children = self._list_directory(item, max_depth, current_depth + 1)
                        results.append({
                            "type": "directory",
                            "name": item.name,
                            "children": children,
                            "path": str(item.relative_to(path.parent))
                        })
                except PermissionError:
                    results.append({
                        "type": "error",
                        "name": item.name,
                        "error": "Permission denied"
                    })
                except Exception as e:
                    logger.error(f"Error processing {item}: {str(e)}")
                    
        except PermissionError:
            return [{"type": "error", "name": path.name, "error": "Permission denied"}]
        except Exception as e:
            logger.error(f"Error listing directory {path}: {str(e)}")
            return [{"type": "error", "name": path.name, "error": str(e)}]
            
        return results

    def _format_tree(self, items: List[Dict], depth: int = 0) -> List[str]:
        """Format directory tree into lines of text.
        
        Args:
            items: List of file/directory items
            depth: Current indentation depth
            
        Returns:
            List of formatted lines
        """
        lines = []
        indent = "  " * depth
        
        for item in items:
            if item["type"] == "file":
                lines.append(f"{indent} {item['path']} ({item['size']})")
            elif item["type"] == "directory":
                lines.append(f"{indent} {item['path']}/")
                if "children" in item:
                    lines.extend(self._format_tree(item["children"], depth + 1))
            elif item["type"] == "error":
                lines.append(f"{indent} {item['name']} ({item['error']})")
                
        return lines

    def execute(
        self,
        directory_path: str,
        recursive: str = "false",
        max_depth: str = "10",
        start_line: str = "1",
        end_line: str = "200",
    ) -> str:
        """
        List directory contents with pagination.

        Args:
            directory_path: Absolute or relative path to target directory
            recursive: Enable recursive traversal (true/false)
            max_depth: Maximum directory traversal depth
            start_line: First line to return in paginated results
            end_line: Last line to return in paginated results

        Returns:
            str: Paginated directory listing with metadata

        Raises:
            ValueError: For invalid directory paths or pagination parameters
        """
        try:
            # Expand user home directory
            if directory_path.startswith("~"):
                directory_path = os.path.expanduser(directory_path)

            path = Path(directory_path)
            
            # Validate directory
            if not path.exists():
                raise ValueError(f"The directory '{directory_path}' does not exist.")
            if not path.is_dir():
                raise ValueError(f"The path '{directory_path}' is not a directory.")

            # Parse parameters
            start = int(start_line)
            end = int(end_line)
            max_depth_int = int(max_depth)
            is_recursive = recursive.lower() == "true"

            if start > end:
                raise ValueError("start_line must be less than or equal to end_line.")

            # List directory contents
            items = self._list_directory(
                path=path,
                max_depth=max_depth_int if is_recursive else 0
            )
            
            # Format output
            lines = self._format_tree(items)
            
            if not lines:
                return "==== No files to display ===="
                
            # Paginate results
            total_lines = len(lines)
            paginated_lines = lines[start - 1:end]
            
            header = f"==== Lines {start}-{min(end, total_lines)} of {total_lines} ===="
            if end >= total_lines:
                header += " [LAST BLOCK]"
                
            return f"{header}\n" + "\n".join(paginated_lines) + "\n==== End of Block ===="
            
        except Exception as e:
            logger.error(f"Error listing directory: {str(e)}")
            return f"Error: {str(e)}"


if __name__ == "__main__":
    tool = ListDirectoryTool()
    print(tool.execute(directory_path=".", recursive="true"))
