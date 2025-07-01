import tree_sitter_rust as tsrust
from tree_sitter import Language


class RustLanguageHandler:
    """Handler for Rust-specific language processing."""

    def get_language(self):
        """Returns the Tree-sitter Language object for Rust."""
        return Language(tsrust.language())

    def validate_root_node(self, root_node):
        """Validates the root node for Rust syntax trees."""
        return root_node.type == "source_file"

    def process_node(
        self, node, current_class, definitions, process_method, process_function, process_class, process_class_variable
    ):
        """Processes a node in a Rust syntax tree."""
        if node.type == "function_item":
            if current_class:
                process_method(node, definitions["classes"][current_class]["methods"])
            else:
                process_function(node, definitions["functions"])
            return "function"
        elif node.type == "struct_item":
            class_name = process_class(node)
            definitions["classes"][class_name] = {
                "line": (node.start_point[0] + 1, node.end_point[0] + 1),
                "methods": [],
                "variables": [],
            }
            return "class"
