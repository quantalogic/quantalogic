import tree_sitter_c as tsc
from tree_sitter import Language


class CLanguageHandler:
    """Handler for C-specific language processing."""

    def get_language(self):
        """Returns the Tree-sitter Language object for C."""
        return Language(tsc.language())

    def validate_root_node(self, root_node):
        """Validates the root node for C syntax trees."""
        return root_node.type == "translation_unit"

    def process_node(
        self, node, current_class, definitions, process_method, process_function, process_class, process_class_variable
    ):
        """Processes a node in a C syntax tree."""
        if node.type == "function_definition":
            if current_class:
                process_method(node, definitions["classes"][current_class]["methods"])
            else:
                process_function(node, definitions["functions"])
            return "function"
        elif node.type == "struct_specifier":
            class_name = process_class(node)
            definitions["classes"][class_name] = {
                "line": (node.start_point[0] + 1, node.end_point[0] + 1),
                "methods": [],
                "variables": [],
            }
            return "class"
