import ast
import os

from loguru import logger

from quantalogic.flow.flow_generator import generate_executable_script  # Import from flow_generator
from quantalogic.flow.flow_manager import WorkflowManager  # Added for YAML saving
from quantalogic.flow.flow_manager_schema import (
    FunctionDefinition,
    NodeDefinition,
    TransitionDefinition,
    WorkflowDefinition,
    WorkflowStructure,
)


class WorkflowExtractor(ast.NodeVisitor):
    """
    AST visitor to extract workflow nodes and structure from a Python file.

    This class parses Python source code to identify workflow components defined with Nodes decorators
    and Workflow construction, building a WorkflowDefinition compatible with WorkflowManager.
    """

    def __init__(self):
        """Initialize the extractor with empty collections for workflow components."""
        self.nodes = {}  # Maps node names to their definitions
        self.functions = {}  # Maps function names to their code
        self.transitions = []  # List of (from_node, to_node, condition) tuples
        self.start_node = None  # Starting node of the workflow
        self.global_vars = {}  # Tracks global variable assignments (e.g., DEFAULT_LLM_PARAMS)
        self.observers = []  # List of observer function names

    def visit_Module(self, node):
        """Log and explicitly process top-level statements in the module."""
        logger.debug(f"Visiting module with {len(node.body)} top-level statements")
        for item in node.body:
            logger.debug(f"Processing top-level node: {type(item).__name__}")
            if isinstance(item, ast.FunctionDef):
                self.visit_FunctionDef(item)
            elif isinstance(item, ast.AsyncFunctionDef):
                self.visit_AsyncFunctionDef(item)
            else:
                self.visit(item)

    def visit_Assign(self, node):
        """Detect global variable assignments and workflow assignments."""
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            var_name = node.targets[0].id
            value = node.value

            # Handle global variable assignments (e.g., MODEL, DEFAULT_LLM_PARAMS)
            if isinstance(value, ast.Dict):
                self.global_vars[var_name] = {}
                for k, v in zip(value.keys, value.values):
                    if isinstance(k, ast.Constant):
                        key = k.value
                        if isinstance(v, ast.Constant):
                            self.global_vars[var_name][key] = v.value
                        elif isinstance(v, ast.Name) and v.id in self.global_vars:
                            # Resolve variable references to previously defined globals
                            self.global_vars[var_name][key] = self.global_vars[v.id]
                logger.debug(
                    f"Captured global variable '{var_name}' with keys: {list(self.global_vars[var_name].keys())}"
                )

            # Handle simple constant assignments (e.g., MODEL = "gemini/gemini-2.0-flash")
            elif isinstance(value, ast.Constant):
                self.global_vars[var_name] = value.value
                logger.debug(f"Captured global constant '{var_name}' with value: {value.value}")

            # Handle workflow assignments, including parenthesized expressions
            if isinstance(value, ast.Tuple) and len(value.elts) == 1:
                value = value.elts[0]  # Unwrap single-element tuple from parentheses
            if isinstance(value, ast.Call):
                self.process_workflow_expr(value, var_name)

        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        """Extract node information from synchronous function definitions."""
        logger.debug(f"Visiting synchronous function definition: '{node.name}'")
        for decorator in node.decorator_list:
            decorator_name = None
            kwargs = {}
            logger.debug(f"Examining decorator for '{node.name}': {ast.dump(decorator)}")

            # Handle simple decorators (e.g., @Nodes.define)
            if (
                isinstance(decorator, ast.Attribute)
                and isinstance(decorator.value, ast.Name)
                and decorator.value.id == "Nodes"
            ):
                decorator_name = decorator.attr
                logger.debug(f"Found simple decorator 'Nodes.{decorator_name}' for '{node.name}'")

            # Handle decorators with arguments (e.g., @Nodes.llm_node(...))
            elif (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "Nodes"
            ):
                decorator_name = decorator.func.attr
                logger.debug(f"Found call decorator 'Nodes.{decorator_name}' for '{node.name}'")
                for kw in decorator.keywords:
                    if kw.arg is None and isinstance(kw.value, ast.Name):  # Handle **kwargs
                        var_name = kw.value.id
                        if var_name in self.global_vars:
                            kwargs.update(self.global_vars[var_name])
                            logger.debug(f"Unpacked '{var_name}' into kwargs: {self.global_vars[var_name]}")
                    elif isinstance(kw.value, ast.Constant):
                        kwargs[kw.arg] = kw.value.value
                    elif kw.arg == "response_model" and isinstance(kw.value, ast.Name):
                        kwargs[kw.arg] = ast.unparse(kw.value)

            # Process recognized decorators
            if decorator_name:
                func_name = node.name
                inputs = [arg.arg for arg in node.args.args]

                if decorator_name == "define":
                    output = kwargs.get("output")
                    self.nodes[func_name] = {
                        "type": "function",
                        "function": func_name,
                        "inputs": inputs,
                        "output": output,
                    }
                elif decorator_name == "llm_node":
                    llm_config = {
                        key: value
                        for key, value in kwargs.items()
                        if key in [
                            "model",
                            "system_prompt",
                            "prompt_template",
                            "prompt_file",  # Added to support external Jinja2 files
                            "temperature",
                            "max_tokens",
                            "top_p",
                            "presence_penalty",
                            "frequency_penalty",
                            "output",
                        ]
                    }
                    self.nodes[func_name] = {
                        "type": "llm",
                        "llm_config": llm_config,
                        "inputs": inputs,
                        "output": llm_config.get("output"),
                    }
                elif decorator_name == "validate_node":
                    output = kwargs.get("output")
                    self.nodes[func_name] = {
                        "type": "function",
                        "function": func_name,
                        "inputs": inputs,
                        "output": output,
                    }
                elif decorator_name == "structured_llm_node":
                    llm_config = {
                        key: value
                        for key, value in kwargs.items()
                        if key in [
                            "model",
                            "system_prompt",
                            "prompt_template",
                            "prompt_file",  # Added to support external Jinja2 files
                            "temperature",
                            "max_tokens",
                            "top_p",
                            "presence_penalty",
                            "frequency_penalty",
                            "output",
                            "response_model",
                        ]
                    }
                    self.nodes[func_name] = {
                        "type": "structured_llm",
                        "llm_config": llm_config,
                        "inputs": inputs,
                        "output": llm_config.get("output"),
                    }
                else:
                    logger.warning(f"Unsupported decorator 'Nodes.{decorator_name}' in function '{func_name}'")

                # Store the function code as embedded
                func_code = ast.unparse(node)
                self.functions[func_name] = {
                    "type": "embedded",
                    "code": func_code,
                }
            else:
                logger.debug(f"No recognized 'Nodes' decorator found for '{node.name}'")

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        """Extract node information from asynchronous function definitions."""
        logger.debug(f"Visiting asynchronous function definition: '{node.name}'")
        for decorator in node.decorator_list:
            decorator_name = None
            kwargs = {}
            logger.debug(f"Examining decorator for '{node.name}': {ast.dump(decorator)}")

            # Handle simple decorators (e.g., @Nodes.define)
            if (
                isinstance(decorator, ast.Attribute)
                and isinstance(decorator.value, ast.Name)
                and decorator.value.id == "Nodes"
            ):
                decorator_name = decorator.attr
                logger.debug(f"Found simple decorator 'Nodes.{decorator_name}' for '{node.name}'")

            # Handle decorators with arguments (e.g., @Nodes.llm_node(...))
            elif (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "Nodes"
            ):
                decorator_name = decorator.func.attr
                logger.debug(f"Found call decorator 'Nodes.{decorator_name}' for '{node.name}'")
                for kw in decorator.keywords:
                    if kw.arg is None and isinstance(kw.value, ast.Name):  # Handle **kwargs
                        var_name = kw.value.id
                        if var_name in self.global_vars:
                            kwargs.update(self.global_vars[var_name])
                            logger.debug(f"Unpacked '{var_name}' into kwargs: {self.global_vars[var_name]}")
                    elif isinstance(kw.value, ast.Constant):
                        kwargs[kw.arg] = kw.value.value
                    elif kw.arg == "response_model" and isinstance(kw.value, ast.Name):
                        kwargs[kw.arg] = ast.unparse(kw.value)

            # Process recognized decorators
            if decorator_name:
                func_name = node.name
                inputs = [arg.arg for arg in node.args.args]

                if decorator_name == "define":
                    output = kwargs.get("output")
                    self.nodes[func_name] = {
                        "type": "function",
                        "function": func_name,
                        "inputs": inputs,
                        "output": output,
                    }
                elif decorator_name == "llm_node":
                    llm_config = {
                        key: value
                        for key, value in kwargs.items()
                        if key in [
                            "model",
                            "system_prompt",
                            "prompt_template",
                            "prompt_file",  # Added to support external Jinja2 files
                            "temperature",
                            "max_tokens",
                            "top_p",
                            "presence_penalty",
                            "frequency_penalty",
                            "output",
                        ]
                    }
                    self.nodes[func_name] = {
                        "type": "llm",
                        "llm_config": llm_config,
                        "inputs": inputs,
                        "output": llm_config.get("output"),
                    }
                elif decorator_name == "validate_node":
                    output = kwargs.get("output")
                    self.nodes[func_name] = {
                        "type": "function",
                        "function": func_name,
                        "inputs": inputs,
                        "output": output,
                    }
                elif decorator_name == "structured_llm_node":
                    llm_config = {
                        key: value
                        for key, value in kwargs.items()
                        if key in [
                            "model",
                            "system_prompt",
                            "prompt_template",
                            "prompt_file",  # Added to support external Jinja2 files
                            "temperature",
                            "max_tokens",
                            "top_p",
                            "presence_penalty",
                            "frequency_penalty",
                            "output",
                            "response_model",
                        ]
                    }
                    self.nodes[func_name] = {
                        "type": "structured_llm",
                        "llm_config": llm_config,
                        "inputs": inputs,
                        "output": llm_config.get("output"),
                    }
                else:
                    logger.warning(f"Unsupported decorator 'Nodes.{decorator_name}' in function '{func_name}'")

                # Store the function code as embedded
                func_code = ast.unparse(node)
                self.functions[func_name] = {
                    "type": "embedded",
                    "code": func_code,
                }
            else:
                logger.debug(f"No recognized 'Nodes' decorator found for '{node.name}'")

        self.generic_visit(node)

    def process_workflow_expr(self, expr, var_name):
        """
        Recursively process Workflow method chaining to build transitions, structure, and observers.

        Args:
            expr: The AST expression to process.
            var_name: The variable name to which the workflow is assigned (for logging/context).

        Returns:
            str or None: The current node name or None if no specific node is returned.
        """
        if not isinstance(expr, ast.Call):
            logger.debug(f"Skipping non-Call node in workflow processing for '{var_name}'")
            return None

        func = expr.func
        logger.debug(f"Processing Call node with func type: {type(func).__name__} for '{var_name}'")

        if isinstance(func, ast.Name) and func.id == "Workflow":
            self.start_node = expr.args[0].value if expr.args else None
            logger.debug(f"Workflow start node set to '{self.start_node}' for variable '{var_name}'")
            return self.start_node
        elif isinstance(func, ast.Attribute):
            method_name = func.attr
            obj = func.value
            previous_node = self.process_workflow_expr(obj, var_name)

            if method_name == "then":
                next_node = expr.args[0].value if expr.args else None
                condition = None
                for keyword in expr.keywords:
                    if keyword.arg == "condition":
                        if isinstance(keyword.value, ast.Lambda):
                            condition = ast.unparse(keyword.value)
                        else:
                            condition = ast.unparse(keyword.value)
                            logger.warning(
                                f"Non-lambda condition in 'then' for '{next_node}' may not be fully supported"
                            )
                if previous_node and next_node:
                    self.transitions.append((previous_node, next_node, condition))
                    logger.debug(f"Added transition: {previous_node} -> {next_node} (condition: {condition})")
                return next_node

            elif method_name == "sequence":
                nodes = [arg.value for arg in expr.args]
                if previous_node:
                    self.transitions.append((previous_node, nodes[0], None))
                for i in range(len(nodes) - 1):
                    self.transitions.append((nodes[i], nodes[i + 1], None))
                    logger.debug(f"Added sequence transition: {nodes[i]} -> {nodes[i + 1]}")
                return nodes[-1] if nodes else previous_node

            elif method_name == "parallel":
                to_nodes = [arg.value for arg in expr.args]
                if previous_node:
                    for to_node in to_nodes:
                        self.transitions.append((previous_node, to_node, None))
                        logger.debug(f"Added parallel transition: {previous_node} -> {to_node}")
                return None  # Parallel transitions reset the current node

            elif method_name == "node":
                node_name = expr.args[0].value if expr.args else None
                if node_name and previous_node:
                    self.transitions.append((previous_node, node_name, None))
                    logger.debug(f"Added node transition: {previous_node} -> {node_name}")
                return node_name

            elif method_name == "add_sub_workflow":
                sub_wf_name = expr.args[0].value
                sub_wf_obj = expr.args[1]
                inputs = {}
                if len(expr.args) > 2 and isinstance(expr.args[2], ast.Dict):
                    inputs = {k.value: v.value for k, v in zip(expr.args[2].keys, expr.args[2].values)}
                output = expr.args[3].value if len(expr.args) > 3 else None
                sub_extractor = WorkflowExtractor()
                sub_extractor.process_workflow_expr(sub_wf_obj, f"{var_name}_{sub_wf_name}")
                self.nodes[sub_wf_name] = {
                    "type": "sub_workflow",
                    "sub_workflow": WorkflowStructure(
                        start=sub_extractor.start_node,
                        transitions=[
                            TransitionDefinition(from_node=t[0], to_node=t[1], condition=t[2]) for t in sub_extractor.transitions
                        ],
                    ),
                    "inputs": list(inputs.keys()),
                    "output": output,
                }
                # Propagate observers from sub-workflow
                self.observers.extend(sub_extractor.observers)
                logger.debug(f"Added sub-workflow node '{sub_wf_name}' with start '{sub_extractor.start_node}'")
                if previous_node:
                    self.transitions.append((previous_node, sub_wf_name, None))
                return sub_wf_name

            elif method_name == "add_observer":
                if expr.args and isinstance(expr.args[0], (ast.Name, ast.Constant)):
                    observer_name = expr.args[0].id if isinstance(expr.args[0], ast.Name) else expr.args[0].value
                    if observer_name not in self.observers:
                        self.observers.append(observer_name)
                        logger.debug(f"Added observer '{observer_name}' to workflow '{var_name}'")
                else:
                    logger.warning(f"Unsupported observer argument in 'add_observer' for '{var_name}'")
                return previous_node

            else:
                logger.warning(f"Unsupported Workflow method '{method_name}' in variable '{var_name}'")
        return None


def extract_workflow_from_file(file_path):
    """
    Extract a WorkflowDefinition and global variables from a Python file containing a workflow.

    Args:
        file_path (str): Path to the Python file to parse.

    Returns:
        tuple: (WorkflowDefinition, Dict[str, Any]) - The workflow definition and captured global variables.
    """
    # Read and parse the file
    with open(file_path) as f:
        source = f.read()
    tree = ast.parse(source)

    # Extract workflow components
    extractor = WorkflowExtractor()
    extractor.visit(tree)

    # Construct FunctionDefinition objects
    functions = {name: FunctionDefinition(**func) for name, func in extractor.functions.items()}

    # Construct NodeDefinition objects
    nodes = {}
    from quantalogic.flow.flow_manager_schema import LLMConfig  # Import LLMConfig explicitly

    for name, node_info in extractor.nodes.items():
        if node_info["type"] == "function":
            nodes[name] = NodeDefinition(
                function=node_info["function"],
                output=node_info["output"],
                retries=3,  # Default values
                delay=1.0,
                timeout=None,
                parallel=False,
            )
        elif node_info["type"] == "llm":
            # Convert llm_config dictionary to LLMConfig object to ensure model is preserved
            llm_config = LLMConfig(**node_info["llm_config"])
            nodes[name] = NodeDefinition(
                llm_config=llm_config,
                output=node_info["output"],
                retries=3,
                delay=1.0,
                timeout=None,
                parallel=False,
            )
        elif node_info["type"] == "structured_llm":
            # Convert llm_config dictionary to LLMConfig object for structured LLM
            llm_config = LLMConfig(**node_info["llm_config"])
            nodes[name] = NodeDefinition(
                llm_config=llm_config,
                output=node_info["output"],
                retries=3,
                delay=1.0,
                timeout=None,
                parallel=False,
            )
        elif node_info["type"] == "sub_workflow":
            nodes[name] = NodeDefinition(
                sub_workflow=node_info["sub_workflow"],
                output=node_info["output"],
                retries=3,
                delay=1.0,
                timeout=None,
                parallel=False,
            )

    # Construct TransitionDefinition objects
    transitions = [
        TransitionDefinition(from_node=from_node, to_node=to_node, condition=cond)
        for from_node, to_node, cond in extractor.transitions
    ]

    # Build WorkflowStructure
    workflow_structure = WorkflowStructure(start=extractor.start_node, transitions=transitions)

    # Assemble WorkflowDefinition with observers
    workflow_def = WorkflowDefinition(
        functions=functions, nodes=nodes, workflow=workflow_structure, observers=extractor.observers
    )

    return workflow_def, extractor.global_vars


def print_workflow_definition(workflow_def):
    """
    Utility function to print a WorkflowDefinition in a human-readable format.

    Args:
        workflow_def (WorkflowDefinition): The workflow definition to print.
    """
    print("### Workflow Definition ###")
    print("\n#### Functions:")
    for name, func in workflow_def.functions.items():
        print(f"- {name}:")
        print(f"  Type: {func.type}")
        print(f"  Code (first line): {func.code.splitlines()[0][:50]}..." if func.code else "  Code: None")

    print("\n#### Nodes:")
    for name, node in workflow_def.nodes.items():
        print(f"- {name}:")
        if node.function:
            print("  Type: Function")
            print(f"  Function: {node.function}")
        elif node.llm_config:
            if node.llm_config.response_model:
                print("  Type: Structured LLM")
                print(f"  Response Model: {node.llm_config.response_model}")
            else:
                print("  Type: LLM")
            print(f"  Model: {node.llm_config.model}")
            print(f"  Prompt Template: {node.llm_config.prompt_template}")
            if node.llm_config.prompt_file:  # Added to display external prompt file if present
                print(f"  Prompt File: {node.llm_config.prompt_file}")
        elif node.sub_workflow:
            print("  Type: Sub-Workflow")
            print(f"  Start Node: {node.sub_workflow.start}")
        print(f"  Output: {node.output or 'None'}")

    print("\n#### Workflow Structure:")
    print(f"Start Node: {workflow_def.workflow.start}")
    print("Transitions:")
    for trans in workflow_def.workflow.transitions:
        condition_str = f" [Condition: {trans.condition}]" if trans.condition else ""
        if isinstance(trans.to_node, list):
            for to_node in trans.to_node:
                print(f"- {trans.from_node} -> {to_node}{condition_str}")
        else:
            print(f"- {trans.from_node} -> {trans.to_node}{condition_str}")

    print("\n#### Observers:")
    for observer in workflow_def.observers:
        print(f"- {observer}")


def main():
    """Demonstrate extracting a workflow from a Python file and saving it to YAML."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Extract workflow from a Python file')
    parser.add_argument('file_path', nargs='?', default="examples/qflow/story_generator_agent.py",
                        help='Path to the Python file containing the workflow')
    parser.add_argument('--output', '-o', default="./generated_workflow.py",
                        help='Output path for the executable Python script')
    parser.add_argument('--yaml', '-y', default="workflow_definition.yaml",
                        help='Output path for the YAML workflow definition')
    
    args = parser.parse_args()
    file_path = args.file_path
    output_file_python = args.output
    yaml_output_path = args.yaml
    
    if not os.path.exists(file_path):
        logger.error(f"File '{file_path}' not found. Please provide a valid file path.")
        logger.info("Example usage: python -m quantalogic.flow.flow_extractor path/to/your/workflow_file.py")
        sys.exit(1)
        
    try:
        workflow_def, global_vars = extract_workflow_from_file(file_path)
        logger.info(f"Successfully extracted workflow from '{file_path}'")
        print_workflow_definition(workflow_def)
        generate_executable_script(workflow_def, global_vars, output_file_python)
        logger.info(f"Executable script generated at '{output_file_python}'")
        
        # Save the workflow to a YAML file
        manager = WorkflowManager(workflow_def)
        manager.save_to_yaml(yaml_output_path)
        logger.info(f"Workflow saved to YAML file '{yaml_output_path}'")
    except Exception as e:
        logger.error(f"Failed to parse or save workflow from '{file_path}': {e}")


if __name__ == "__main__":
    main()