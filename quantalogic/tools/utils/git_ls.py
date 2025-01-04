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

    # Load .gitignore patterns
    ignore_spec = load_gitignore_spec(path)

    # Generate file tree
    tree = generate_file_tree(path, ignore_spec, recursive=recursive, max_depth=max_depth)

    # Format and paginate output
    return format_tree(tree, start_line, end_line)


def load_gitignore_spec(path: Path) -> PathSpec:
    """Load .gitignore patterns from directory."""
    ignore_patterns = []
    gitignore_path = path / ".gitignore"

    if gitignore_path.exists():
        with open(gitignore_path) as f:
            ignore_patterns = f.readlines()

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
        return {"name": path.name, "type": "file", "size": f"{path.stat().st_size} bytes"}

    tree = {"name": path.name, "type": "directory", "children": []}

    if recursive and current_depth < max_depth:
        # Sort children by name before adding to tree
        children = sorted(path.iterdir(), key=lambda x: x.name.lower())
        for child in children:
            if not ignore_spec.match_file(child):
                child_tree = generate_file_tree(child, ignore_spec, recursive, max_depth, current_depth + 1)
                if child_tree:
                    tree["children"].append(child_tree)

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
        header += " [LAST BLOCK]"
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