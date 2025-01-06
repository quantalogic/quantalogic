import tree_sitter_java as tsjava
from tree_sitter import Language


class JavaLanguageHandler:
    """Handler for Java-specific language processing."""

    def get_language(self):
        """Returns the Tree-sitter Language object for Java."""
        return Language(tsjava.language())

    def validate_root_node(self, root_node):
        """Validates the root node for Java syntax trees."""
        return root_node.type == "program"

    def process_node(
        self, node, current_class, definitions, process_method, process_function, process_class, process_class_variable
    ):
        """Processes a node in a Java syntax tree."""
        if node.type == "method_declaration":
            if current_class:
                process_method(node, definitions["classes"][current_class]["methods"])
            else:
                process_function(node, definitions["functions"])
            return "method"
        elif node.type == "class_declaration":
            class_name = process_class(node)
            definitions["classes"][class_name] = {
                "line": (node.start_point[0] + 1, node.end_point[0] + 1),
                "methods": [],
                "variables": [],
            }
            return "class"
        elif node.type == "field_declaration":
            if current_class:
                process_class_variable(node, definitions["classes"][current_class]["variables"])
            return "variable"
