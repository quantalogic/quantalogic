"""Tool for searching definition names in a directory using Tree-sitter."""

import logging
import os
from pathlib import Path
from typing import Dict, List, Union

from pathspec import PathSpec
from tree_sitter import Parser

from quantalogic.tools.language_handlers.c_handler import CLanguageHandler
from quantalogic.tools.language_handlers.cpp_handler import CppLanguageHandler
from quantalogic.tools.language_handlers.go_handler import GoLanguageHandler
from quantalogic.tools.language_handlers.java_handler import JavaLanguageHandler
from quantalogic.tools.language_handlers.javascript_handler import JavaScriptLanguageHandler
from quantalogic.tools.language_handlers.python_handler import PythonLanguageHandler
from quantalogic.tools.language_handlers.rust_handler import RustLanguageHandler
from quantalogic.tools.language_handlers.scala_handler import ScalaLanguageHandler
from quantalogic.tools.language_handlers.typescript_handler import TypeScriptLanguageHandler
from quantalogic.tools.tool import Tool, ToolArgument

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SearchDefinitionNames(Tool):
    """Tool for searching definition names in a directory using Tree-sitter.

    Supports searching for:
    - Functions (including async functions)
    - Classes
    - Methods
    - Class variables
    - JavaScript functions and classes
    """

    name: str = "search_definition_names_tool"
    description: str = (
        "Searches for definition names (classes, functions, methods) in a directory using Tree-sitter. "
        "Very useful to locate quickly code locations of classes, functions, methods in large projects."
        "Returns the list of definition names grouped by file name, with line numbers. "
    )
    arguments: list = [
        ToolArgument(
            name="directory_path",
            arg_type="string",
            description="The path to the directory to search in.",
            required=True,
            example="./path/to",
        ),
        ToolArgument(
            name="language_name",
            arg_type="string",
            description="The Tree-sitter language name (python, javascript, typescript, java, scala, go, rust, c, cpp).",
            required=True,
            example="python",
        ),
        ToolArgument(
            name="file_pattern",
            arg_type="string",
            description="Optional glob pattern to filter files (default: '*').",
            required=False,
            example="**/*.py",
        ),
        ToolArgument(
            name="page",
            arg_type="int",
            description="The page number to retrieve (1-based index).",
            required=False,
            example="1",
            default="1",
        ),
        ToolArgument(
            name="page_size",
            arg_type="int",
            description="The number of results per page (default: 10).",
            required=False,
            example="10",
            default="10",
        ),
    ]

    def _get_language_handler(self, language_name: str):
        """Returns a language-specific handler based on the language name."""
        if language_name == "python":
            return PythonLanguageHandler()
        elif language_name == "javascript":
            return JavaScriptLanguageHandler()
        elif language_name == "typescript":
            return TypeScriptLanguageHandler()
        elif language_name == "java":
            return JavaLanguageHandler()
        elif language_name == "scala":
            return ScalaLanguageHandler()
        elif language_name == "go":
            return GoLanguageHandler()
        elif language_name == "rust":
            return RustLanguageHandler()
        elif language_name == "c":
            return CLanguageHandler()
        elif language_name == "cpp":
            return CppLanguageHandler()
        else:
            raise ValueError(f"Unsupported language: {language_name}")

    def execute(
        self,
        directory_path: str,
        language_name: str,
        file_pattern: str = "*",
        output_format: str = "text",
        page: int = 1,
        page_size: int = 10,
    ) -> Union[str, Dict]:
        """Searches for definition names in a directory using Tree-sitter.

        Args:
            directory_path (str): The path to the directory to search in.
            language_name (str): The Tree-sitter language name.
            file_pattern (str): Optional glob pattern to filter files (default: '*').
            output_format (str): Output format ('text', 'json', 'markdown').
            page (int): The page number to retrieve (1-based index).
            page_size (int): The number of results per page (default: 10).

        Returns:
            Union[str, Dict]: The search results in the specified format.
        """
        try:
            page = int(page)
            page_size = int(page_size)

            # Validate pagination parameters
            if page < 1:
                raise ValueError("Page number must be a positive integer.")
            if page_size < 1:
                raise ValueError("Page size must be a positive integer.")

            # Set up Tree-sitter based on language
            language_handler = self._get_language_handler(language_name)
            parser = Parser(language_handler.get_language())

            # Find files matching the pattern
            directory_path = os.path.expanduser(directory_path)
            gitignore_spec = self._load_gitignore_spec(Path(directory_path))
            files = list(Path(directory_path).rglob(file_pattern))

            results = []

            for file_path in files:
                # Skip files matching .gitignore patterns
                if gitignore_spec.match_file(file_path):
                    continue

                if file_path.is_file():
                    try:
                        with open(file_path, "rb") as f:
                            source_code = f.read()

                        tree = parser.parse(source_code)
                        root_node = tree.root_node

                        # Validate root node using language handler
                        if not language_handler.validate_root_node(root_node):
                            continue

                        definitions = self._extract_definitions(root_node, language_name)

                        if definitions:
                            results.append({"file_path": str(file_path), "definitions": definitions})

                    except Exception as e:
                        logger.warning(f"Error processing file {file_path}: {str(e)}")
                        continue

            # Apply pagination
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_results = results[start_index:end_index]

            return self._format_results(
                paginated_results,
                directory_path,
                language_name,
                file_pattern,
                output_format,
                page,
                page_size,
                len(results),
            )

        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            return {"error": str(e)}

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

    def _extract_definitions(self, root_node, language_name: str) -> Dict:
        """Extracts definitions from a Tree-sitter syntax tree node.

        Args:
            root_node: The root node of the syntax tree.
            language_name: The language being parsed.

        Returns:
            Dict: Dictionary containing classes with their methods and variables,
                  and standalone functions.
        """
        definitions = {"classes": {}, "functions": []}

        current_class = None
        language_handler = self._get_language_handler(language_name)

        def process_node(node):
            nonlocal current_class

            # Delegate node processing to language handler
            node_type = language_handler.process_node(
                node,
                current_class,
                definitions,
                self._process_method,
                self._process_function,
                self._process_class,
                self._process_class_variable,
            )

            # Update current_class if processing a class node
            if node_type == "class":
                current_class = self._process_class(node)
            elif node_type == "end_class":
                current_class = None

            # Recursively process child nodes
            for child in node.children:
                process_node(child)

        process_node(root_node)
        return definitions

    def _process_function(self, node, definitions):
        """Process a function definition node."""
        name_node = node.child_by_field_name("name")
        if name_node and name_node.type == "identifier":
            definition_name = name_node.text.decode("utf-8")
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1

            # Extract function signature
            parameters_node = node.child_by_field_name("parameters")
            if parameters_node:
                signature = f"{definition_name}{parameters_node.text.decode('utf-8')}"
                definitions.append((signature, start_line, end_line))
            else:
                definitions.append((definition_name, start_line, end_line))

    def _process_class(self, node) -> tuple:
        """Process a class definition node.

        Args:
            node: The class definition node.

        Returns:
            tuple: (class_name, start_line, end_line)
        """
        name_node = node.child_by_field_name("name")
        if name_node and name_node.type == "identifier":
            return (name_node.text.decode("utf-8"), node.start_point[0] + 1, node.end_point[0] + 1)
        return ("", 0, 0)

    def _process_method(self, node, definitions):
        """Process a method definition node."""
        name_node = node.child_by_field_name("name")
        if name_node and name_node.type == "identifier":
            definition_name = name_node.text.decode("utf-8")
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            definitions.append((definition_name, start_line, end_line))

    def _process_class_variable(self, node, definitions):
        """Process a class variable definition node."""
        name_node = node.child_by_field_name("name")
        if name_node and name_node.type == "identifier":
            definition_name = name_node.text.decode("utf-8")
            line_number = name_node.start_point[0] + 1
            definitions.append((definition_name, line_number))

    def _format_results(
        self,
        results: List[Dict],
        directory_path: str,
        language_name: str,
        file_pattern: str,
        output_format: str = "text",
        page: int = 1,
        page_size: int = 10,
        total_results: int = 0,
    ) -> Union[str, Dict]:
        """Formats the search results in the specified format.

        Args:
            results: The search results to format.
            directory_path: The directory that was searched.
            language_name: The language that was searched.
            file_pattern: The file pattern that was used.
            output_format: The desired output format.
            page: The page number.
            page_size: The number of results per page.
            total_results: The total number of results.

        Returns:
            Union[str, Dict]: The formatted results.
        """
        if output_format == "json":
            formatted_results = {
                "directory": directory_path,
                "language": language_name,
                "file_pattern": file_pattern,
                "page": page,
                "page_size": page_size,
                "total_results": total_results,
                "results": [],
            }

            for result in results:
                file_result = {
                    "file_path": result["file_path"],
                    "classes": [],
                    "functions": [
                        {"name": name, "start_line": start, "end_line": end}
                        for name, start, end in result["definitions"]["functions"]
                    ],
                }

                for class_name, class_info in result["definitions"]["classes"].items():
                    class_data = {
                        "name": class_name,
                        "start_line": class_info["line"][0],
                        "end_line": class_info["line"][1],
                        "methods": [
                            {"name": name, "start_line": start, "end_line": end}
                            for name, start, end in class_info["methods"]
                        ],
                        "variables": [
                            {"name": name, "start_line": start, "end_line": end}
                            for name, start, end in class_info["variables"]
                        ],
                    }
                    file_result["classes"].append(class_data)

                formatted_results["results"].append(file_result)

            return formatted_results

        elif output_format == "markdown":
            markdown = "# Search Results\n\n"
            markdown += f"- **Directory**: `{directory_path}`\n"
            markdown += f"- **Language**: `{language_name}`\n"
            markdown += f"- **File Pattern**: `{file_pattern}`\n"
            markdown += f"- **Page**: {page}\n"
            markdown += f"- **Page Size**: {page_size}\n"
            markdown += f"- **Total Results**: {total_results}\n\n"

            for result in results:
                markdown += f"## File: {result['file_path']}\n"

                # Add standalone functions
                if result["definitions"]["functions"]:
                    markdown += "### Functions\n"
                    for func, start, end in result["definitions"]["functions"]:
                        markdown += f"- `{func}` (lines {start}-{end})\n"
                    markdown += "\n"

                # Add classes with their methods and variables
                for class_name, class_info in result["definitions"]["classes"].items():
                    markdown += f"### Class: {class_name} (lines {class_info['line'][0]}-{class_info['line'][1]})\n"

                    if class_info["methods"]:
                        markdown += "#### Methods\n"
                        for method, start, end in class_info["methods"]:
                            markdown += f"- `{method}` (lines {start}-{end})\n"

                    if class_info["variables"]:
                        markdown += "#### Variables\n"
                        for var, start, end in class_info["variables"]:
                            markdown += f"- `{var}` (lines {start}-{end})\n"

                    markdown += "\n"

            return markdown

        else:
            # Default to text format
            text = "Search Results\n"
            text += "==============\n"
            text += f"Directory: {directory_path}\n"
            text += f"Language: {language_name}\n"
            text += f"File Pattern: {file_pattern}\n"
            text += f"Page: {page}\n"
            text += f"Page Size: {page_size}\n"
            text += f"Total Results: {total_results}\n\n"

            for result in results:
                text += f"File: {result['file_path']}\n"

                # Add standalone functions
                if result["definitions"]["functions"]:
                    text += "Functions:\n"
                    for func, start, end in result["definitions"]["functions"]:
                        text += f"  - {func} (lines {start}-{end})\n"
                    text += "\n"

                # Add classes with their methods and variables
                for class_name, class_info in result["definitions"]["classes"].items():
                    text += f"Class: {class_name} (lines {class_info['line'][0]}-{class_info['line'][1]})\n"

                    if class_info["methods"]:
                        text += "  Methods:\n"
                        for method, start, end in class_info["methods"]:
                            text += f"    - {method} (lines {start}-{end})\n"

                    if class_info["variables"]:
                        text += "  Variables:\n"
                        for var, start, end in class_info["variables"]:
                            text += f"    - {var} (lines {start}-{end})\n"

                    text += "\n"

            return text


if __name__ == "__main__":
    tool = SearchDefinitionNames()
    print(tool.to_markdown())

    # Example usage with different output formats
    result_text = tool.execute(
        directory_path="./quantalogic", language_name="python", file_pattern="**/*.py", output_format="text"
    )
    # print(result_text)

    result_json = tool.execute(
        directory_path="./quantalogic", language_name="python", file_pattern="**/*.py", output_format="json"
    )
    # print(result_json)

    result_markdown = tool.execute(
        directory_path="./quantalogic", language_name="python", file_pattern="**/*.py", output_format="markdown"
    )
    print(result_markdown)

    result_markdown = tool.execute(
        directory_path=".", language_name="javascript", file_pattern="**/*.js", output_format="markdown"
    )
    print(result_markdown)

    result_markdown = tool.execute(
        directory_path=".",
        language_name="javascript",
        file_pattern="./quantalogic/server/static/js/quantalogic.js",
        output_format="markdown",
    )
    print(result_markdown)
