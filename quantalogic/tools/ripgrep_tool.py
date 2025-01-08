"""A tool to search for text blocks in files using ripgrep."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from pathspec import PathSpec
from pydantic import ValidationError

from quantalogic.tools.tool import Tool, ToolArgument

MAX_LINE_LENGTH = 120  # Maximum length for each line before truncation


class RipgrepTool(Tool):
    """Search files using ripgrep with regex and file filters."""

    name: str = "ripgrep_search_tool"
    description: str = "Search files using ripgrep with regex and file filters."

    arguments: list = [
        ToolArgument(
            name="cwd",
            arg_type="string",
            description="Base path for relative searches",
            required=False,
            default=None,
        ),
        ToolArgument(
            name="directory_path",
            arg_type="string",
            description="The directory path to search in.",
            required=True,
        ),
        ToolArgument(
            name="regex_rust_syntax",
            arg_type="string",
            description="The regex pattern to search for (Regex must be in Rust syntax).",
            required=True,
        ),
        ToolArgument(
            name="file_pattern",
            arg_type="string",
            description="Optional glob pattern to filter files.",
            required=False,
            default="**/*",
        ),
        ToolArgument(
            name="context_lines",
            arg_type="string",
            description="Number of context lines to include before and after matches.",
            required=True,
            default="4",
        ),
    ]

    model_config = {"extra": "allow"}

    def _load_gitignore_spec(self, path: Path) -> PathSpec:
        """Load .gitignore patterns from directory and all parent directories."""
        from pathspec import PathSpec
        from pathspec.patterns import GitWildMatchPattern

        ignore_patterns = []
        current = path.absolute()

        # Traverse up the directory tree
        while current != current.parent:  # Stop at root
            gitignore_path = current / ".gitignore"
            if gitignore_path.exists():
                with open(gitignore_path) as f:
                    # Filter out empty lines and comments
                    patterns = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]
                    ignore_patterns.extend(patterns)
            current = current.parent

        return PathSpec.from_lines(GitWildMatchPattern, ignore_patterns)

    def execute(
        self,
        cwd: Optional[str] = None,
        directory_path: str = ".",
        regex_rust_syntax: str = "search",
        file_pattern: str = "**/*",
        context_lines: str = "1",
    ) -> str:
        """Execute the ripgrep search and return formatted results.

        Args:
            cwd (Optional[str]): The current working directory for relative path calculation.
            directory_path (str): The directory path to search in.
            regex_rust_syntax (str): The regex pattern to search for (Rust syntax).
            file_pattern (str): Optional glob pattern to filter files.
            context_lines (str): Number of context lines to include before and after matches.

        Returns:
            str: Formatted search results with context.

        Raises:
            ValueError: If the directory path is invalid.
            RuntimeError: If ripgrep is not found or fails to execute.
        """
        # Validate and normalize the directory path
        directory_path = str(Path(directory_path).resolve())
        if not os.path.isdir(directory_path):
            raise ValueError(f"Directory not found: {directory_path}")

        # Use current working directory if not specified
        cwd = str(Path(cwd or directory_path).resolve())
        rg_path = self._find_rg_binary()
        if not rg_path:
            raise RuntimeError("Could not find ripgrep binary.")

        # Load .gitignore patterns
        gitignore_spec = self._load_gitignore_spec(Path(directory_path))

        args = [
            "--json",  # Output in JSON format for easier parsing
            "-e",
            regex_rust_syntax,  # Regex pattern to search for
            "--glob",
            file_pattern,  # File pattern to filter files
            "--context",
            context_lines,  # Include context lines before and after matches
            directory_path,  # Directory to search in
        ]

        # Find files matching the pattern
        files = list(Path(directory_path).rglob(file_pattern))
        filtered_files = [str(f) for f in files if f.is_file() and not gitignore_spec.match_file(f)]

        if not filtered_files:
            return "No files matching the pattern (after .gitignore filtering)"

        try:
            logger.debug(f"Executing ripgrep with args: {args}")
            # Add filtered files to ripgrep command
            args.extend(filtered_files)
            output = subprocess.check_output([rg_path] + args, text=True, cwd=cwd)
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:
                return "No results found."
            elif e.returncode == 2:
                return f"Invalid regex pattern: {regex_rust_syntax}"
            raise RuntimeError(f"Ripgrep process error (code {e.returncode}): {e}")

        results = self._parse_rg_output(output, cwd)
        return self._format_results(results, cwd)

    def _find_rg_binary(self) -> Optional[str]:
        """Locate the ripgrep binary in common installation paths.

        Returns:
            Optional[str]: Path to the ripgrep binary, or None if not found.
        """
        bin_name = "rg.exe" if os.name == "nt" else "rg"

        # Check environment variable first
        env_path = os.environ.get("RIPGREP_PATH")
        if env_path and Path(env_path).exists():
            return env_path

        # Common system paths
        system_paths = []
        if os.name == "nt":  # Windows
            system_paths.extend(
                [
                    Path(os.environ.get("ProgramFiles", "C:\\Program Files"), "ripgrep", bin_name),
                    Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "ripgrep", bin_name),
                ]
            )
        else:  # Unix-like systems
            system_paths.extend(
                [
                    Path("/usr/local/bin", bin_name),
                    Path("/usr/bin", bin_name),
                    Path("/opt/local/bin", bin_name),
                    Path.home() / ".cargo" / "bin" / bin_name,  # Common Rust installation path
                ]
            )

        # VSCode/Node.js paths
        node_paths = [
            Path("node_modules", "@vscode", "ripgrep", "bin", bin_name),
            Path("node_modules", "vscode-ripgrep", "bin", bin_name),
            Path("node_modules.asar.unpacked", "vscode-ripgrep", "bin", bin_name),
            Path("node_modules.asar.unpacked", "@vscode", "ripgrep", "bin", bin_name),
        ]

        # Check all possible paths
        for path in system_paths + node_paths:
            full_path = Path(__file__).parent.parent / path if str(path).startswith("node_modules") else path
            if full_path.exists():
                logger.debug(f"Found ripgrep at: {full_path}")
                return str(full_path)

        # Check system PATH using which/where
        try:
            command = "where" if os.name == "nt" else "which"
            rg_path = subprocess.check_output([command, bin_name], text=True).strip()
            if rg_path:
                logger.debug(f"Found ripgrep in PATH at: {rg_path}")
                return rg_path
        except subprocess.CalledProcessError:
            logger.debug("Ripgrep not found in system PATH")

        logger.warning("Could not locate ripgrep binary")
        return None

    def _parse_rg_output(self, output: str, cwd: str) -> List[Dict[str, Any]]:
        """Parse the JSON output from ripgrep into structured results.

        Args:
            output (str): The raw JSON output from ripgrep.
            cwd (str): The current working directory for relative path calculation.

        Returns:
            List[Dict[str, Any]]: A list of parsed search results.

        Raises:
            ValueError: If the JSON data structure is invalid or missing required fields.
        """
        results = []
        current_result = None

        for line in output.strip().split("\n"):
            if not line.strip():
                continue

            try:
                data = json.loads(line)
                if not isinstance(data, dict):
                    logger.warning(f"Skipping non-dict JSON line: {line}")
                    continue

                if data.get("type") == "match":
                    try:
                        # Validate required fields in match data
                        match_data = data["data"]
                        if not all(key in match_data for key in ["path", "line_number", "submatches", "lines"]):
                            raise ValueError("Missing required fields in match data")

                        if current_result:
                            results.append(current_result)
                        current_result = {
                            "file": os.path.relpath(match_data["path"]["text"], cwd),
                            "line": match_data["line_number"],
                            "column": match_data["submatches"][0]["start"],
                            "match": match_data["lines"]["text"].strip(),
                            "before_context": [],
                            "after_context": [],
                        }
                    except (KeyError, ValueError) as e:
                        logger.error(f"Invalid match data structure: {e}\nLine: {line}")
                        continue

                elif data.get("type") == "context" and current_result:
                    try:
                        context_data = data["data"]
                        if not all(key in context_data for key in ["line_number", "lines"]):
                            raise ValueError("Missing required fields in context data")

                        if context_data["line_number"] < current_result["line"]:
                            current_result["before_context"].append(context_data["lines"]["text"].strip())
                        else:
                            current_result["after_context"].append(context_data["lines"]["text"].strip())
                    except (KeyError, ValueError) as e:
                        logger.error(f"Invalid context data structure: {e}\nLine: {line}")
                        continue

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON line: {line}\nError: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error parsing line: {line}\nError: {e}")
                continue

        if current_result:
            results.append(current_result)
        return results

    def _format_results(self, results: List[Dict[str, Any]], cwd: str) -> str:
        """Format the parsed search results into a readable string.

        Args:
            results (List[Dict[str, Any]]): The parsed search results.
            cwd (str): The current working directory for relative path calculation.

        Returns:
            str: Formatted search results with context and line numbers.
        """
        if not results:
            return "No results found."

        formatted_output = []
        grouped_results: Dict[str, List[Dict[str, Any]]] = {}

        # Group results by file
        for result in results:
            if result["file"] not in grouped_results:
                grouped_results[result["file"]] = []
            grouped_results[result["file"]].append(result)

        # Format each group
        for file, file_results in grouped_results.items():
            formatted_output.append(f"\n📄 File: {file}")
            formatted_output.append("=" * (len(file) + 8))  # Adjust divider length for "File: " prefix

            for result in file_results:
                # Add context before the match with line numbers
                for i, line in enumerate(
                    result["before_context"], start=result["line"] - len(result["before_context"])
                ):
                    truncated_line = (line[:MAX_LINE_LENGTH] + "...") if len(line) > MAX_LINE_LENGTH else line
                    formatted_output.append(f"{i:4d} │ {truncated_line}")

                # Highlight the match line with line number
                truncated_match = (
                    (result["match"][:MAX_LINE_LENGTH] + "...")
                    if len(result["match"]) > MAX_LINE_LENGTH
                    else result["match"]
                )
                formatted_output.append(f"{result['line']:4d} ▶ {truncated_match}")  # Use ▶ to highlight match

                # Add context after the match with line numbers
                for i, line in enumerate(result["after_context"], start=result["line"] + 1):
                    truncated_line = (line[:MAX_LINE_LENGTH] + "...") if len(line) > MAX_LINE_LENGTH else line
                    formatted_output.append(f"{i:4d} │ {truncated_line}")

                formatted_output.append("─" * 80)  # Add a visual separator between matches

        if not formatted_output:
            return "No results found."

        # Add summary of results
        total_matches = sum(len(matches) for matches in grouped_results.values())
        formatted_output.insert(0, f"🔍 Found {total_matches} matches across {len(grouped_results)} files\n")

        return "\n".join(formatted_output).strip()


# Example usage:
if __name__ == "__main__":
    try:
        tool = RipgrepTool()
        print(tool.execute(directory_path=".", regex="search", file_pattern="**/*.py", context_lines="2"))
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
    except RuntimeError as e:
        logger.error(f"Runtime error: {e}")
