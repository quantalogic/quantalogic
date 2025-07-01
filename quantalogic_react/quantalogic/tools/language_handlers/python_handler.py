import tree_sitter_python as tspython
from tree_sitter import Language


class PythonLanguageHandler:
    """Handler for Python-specific language processing."""

    def get_language(self):
        """Returns the Tree-sitter Language object for Python."""
        return Language(tspython.language())

    def validate_root_node(self, root_node):
        """Validates the root node for Python syntax trees."""
        return root_node.type == "module"

    def process_node(
        self, node, current_class, definitions, process_method, process_function, process_class, process_class_variable
    ):
        """Processes a node in a Python syntax tree."""
        if node.type in ("function_definition", "async_function_definition"):
            if current_class:
                process_method(node, definitions["classes"][current_class]["methods"])
            else:
                process_function(node, definitions["functions"])
            return "function"
        elif node.type == "class_definition":
            class_name, start_line, end_line = process_class(node)
            definitions["classes"][class_name] = {"line": (start_line, end_line), "methods": [], "variables": []}
            return "class"
