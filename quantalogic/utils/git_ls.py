import os
from pathlib import Path
from typing import Dict, List

from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern


def git_ls(
    directory_path: str, recursive: bool = False, max_depth: int = 10, start_line: int = 1, end_line: int = 500
) -> str:
    """List files respecting .gitignore rules with formatted output.

    Args:
        directory_path: Path to directory to list
        recursive: Whether to list recursively ("true"/"false")
        max_depth: Maximum recursion depth
        start_line: Start line for pagination
        end_line: End line for pagination

    Returns:
        Formatted tree structure with file info
    """
    # Convert inputs
    recursive = recursive if isinstance(recursive, bool) else recursive.lower() == "true"
    max_depth = int(max_depth)
    start_line = int(start_line)
    end_line = int(end_line)

    # Expand paths and get absolute path
    path = Path(os.path.expanduser(directory_path)).absolute()
    
    # Verify access to base directory
    if not os.access(path, os.R_OK):
        return f"==== Error: No read access to directory {path} ====\n==== End of Block ===="

    # Load .gitignore patterns
    ignore_spec = load_gitignore_spec(path)

    # Generate file tree
    tree = generate_file_tree(path, ignore_spec, recursive=recursive, max_depth=max_depth)

    # Format and paginate output
    return format_tree(tree, start_line, end_line)


def load_gitignore_spec(path: Path) -> PathSpec:
    """Load .gitignore patterns from directory and all parent directories."""
    ignore_patterns = []
    current = path

    # Traverse up the directory tree
    while current != current.parent:  # Stop at root
        gitignore_path = current / ".gitignore"
        if gitignore_path.exists():
            try:
                if os.access(gitignore_path, os.R_OK):
                    with open(gitignore_path) as f:
                        # Prepend parent patterns to maintain precedence
                        ignore_patterns = f.readlines() + ignore_patterns
            except (PermissionError, OSError):
                continue
        current = current.parent

    return PathSpec.from_lines(GitWildMatchPattern, ignore_patterns)


def generate_file_tree(
    path: Path, ignore_spec: PathSpec, recursive: bool = False, max_depth: int = 1, current_depth: int = 0
) -> Dict:
    """Generate file tree structure."""
    if current_depth > max_depth:
        return {}

    if ignore_spec.match_file(path) or path.name == ".git":
        return {}

    if path.is_file():
        try:
            if not os.access(path, os.R_OK):
                return {"name": path.name, "type": "file", "size": "no access"}
            return {"name": path.name, "type": "file", "size": f"{path.stat().st_size} bytes"}
        except (PermissionError, OSError):
            return {"name": path.name, "type": "file", "size": "no access"}

    tree = {"name": path.name, "type": "directory", "children": []}

    try:
        if not os.access(path, os.R_OK | os.X_OK):
            tree["children"].append({"name": "no access", "type": "error"})
            return tree

        # Always list direct children, but only recursively list if recursive is True
        children = sorted(path.iterdir(), key=lambda x: x.name.lower())
    except (PermissionError, OSError):
        tree["children"].append({"name": "no access", "type": "error"})
        return tree
    for child in children:
        if not ignore_spec.match_file(child):
            if child.is_file():
                child_tree = generate_file_tree(child, ignore_spec, recursive, max_depth, current_depth)
                tree["children"].append(child_tree)
            elif child.is_dir():
                # Always include directories
                child_tree = generate_file_tree(child, ignore_spec, recursive, max_depth, current_depth + 1)
                if recursive:
                    if child_tree:
                        tree["children"].append(child_tree)
                else:
                    tree["children"].append({"name": child.name, "type": "directory", "children": []})

    return tree


def format_tree(tree: Dict, start: int, end: int) -> str:
    """Format tree structure into string output with line information."""
    lines = []
    _format_tree_recursive(tree, lines, 0)
    total_lines = len(lines)
    is_last_block = end >= total_lines
    output = "\n".join(lines[start - 1 : end])

    header = f"==== Lines: {start}-{end} of {total_lines} ===="
    if is_last_block:
        header = f"==== Lines: {start}-{total_lines} of {total_lines} ===="
        header += f" [LAST BLOCK] (total_lines: {total_lines})"
    return f"{header}\n{output}\n==== End of Block ===="


def _format_tree_recursive(node: Dict, lines: List[str], depth: int):
    """Recursively format tree nodes."""
    indent = "  " * depth
    if node["type"] == "file":
        lines.append(f"{indent}📄 {node['name']} ({node['size']})")
    else:
        lines.append(f"{indent}📁 {node['name']}/")
        for child in node["children"]:
            _format_tree_recursive(child, lines, depth + 1)


if __name__ == "__main__":
    print(git_ls("./", recursive=True, max_depth=30, start_line=1, end_line=500))
