import ast

from loguru import logger

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
        self.nodes = {}           # Maps node names to their definitions
        self.functions = {}       # Maps function names to their code
        self.transitions = []     # List of (from_node, to_node, condition) tuples
        self.start_node = None    # Starting node of the workflow
        self.global_vars = {}     # Tracks global variable assignments (e.g., DEFAULT_LLM_PARAMS)

    def visit_Assign(self, node):
        """Detect global variable assignments and workflow assignments."""
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            var_name = node.targets[0].id
            value = node.value

            # Handle global variable assignments (e.g., DEFAULT_LLM_PARAMS)
            if isinstance(value, ast.Dict):
                self.global_vars[var_name] = {k.s: v.s for k, v in zip(value.keys, value.values) if isinstance(k, ast.Str) and isinstance(v, (ast.Str, ast.Num))}
                logger.debug(f"Captured global variable '{var_name}' with keys: {list(self.global_vars[var_name].keys())}")

            # Handle workflow assignments, including parenthesized expressions
            if hasattr(value, 'value'):  # Handle Expr nodes if present
                value = value.value
            if isinstance(value, ast.Tuple) and len(value.elts) == 1:
                value = value.elts[0]  # Unwrap single-element tuple from parentheses
            if isinstance(value, ast.Call):
                if (isinstance(value.func, ast.Name) and value.func.id == 'Workflow') or \
                   (isinstance(value.func, ast.Attribute) and hasattr(value.func, 'value') and 
                    isinstance(value.func.value, ast.Name) and value.func.value.id == 'Workflow'):
                    logger.debug(f"Detected workflow assignment to '{var_name}'")
                    self.process_workflow_expr(value, var_name)

        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        """Extract node information from decorated function definitions."""
        for decorator in node.decorator_list:
            if (isinstance(decorator, ast.Attribute) and
                    isinstance(decorator.value, ast.Name) and
                    decorator.value.id == 'Nodes'):
                decorator_name = decorator.attr
                func_name = node.name
                inputs = [arg.arg for arg in node.args.args]

                # Extract decorator keyword arguments, including unpacked dictionaries
                kwargs = {}
                for kw in decorator.keywords:
                    if kw.arg is None and isinstance(kw.value, ast.Name):  # Handle **kwargs
                        var_name = kw.value.id
                        if var_name in self.global_vars:
                            kwargs.update(self.global_vars[var_name])
                            logger.debug(f"Unpacked '{var_name}' into decorator kwargs: {self.global_vars[var_name]}")
                    elif hasattr(kw.value, 'value'):
                        kwargs[kw.arg] = kw.value.value
                    elif kw.arg == 'response_model' and isinstance(kw.value, ast.Name):
                        kwargs[kw.arg] = ast.unparse(kw.value)

                # Process known decorators
                if decorator_name == 'define':
                    output = kwargs.get('output')
                    self.nodes[func_name] = {
                        'type': 'function',
                        'function': func_name,
                        'inputs': inputs,
                        'output': output,
                    }
                elif decorator_name == 'llm_node':
                    llm_config = {
                        key: value for key, value in kwargs.items()
                        if key in ['model', 'system_prompt', 'prompt_template', 'temperature',
                                   'max_tokens', 'top_p', 'presence_penalty', 'frequency_penalty', 'output']
                    }
                    self.nodes[func_name] = {
                        'type': 'llm',
                        'llm_config': llm_config,
                        'inputs': inputs,
                        'output': llm_config.get('output'),
                    }
                elif decorator_name == 'validate_node':
                    output = kwargs.get('output')
                    self.nodes[func_name] = {
                        'type': 'function',  # Treated as a function node with validation
                        'function': func_name,
                        'inputs': inputs,
                        'output': output,
                    }
                elif decorator_name == 'structured_llm_node':
                    llm_config = {
                        key: value for key, value in kwargs.items()
                        if key in ['model', 'system_prompt', 'prompt_template', 'temperature',
                                   'max_tokens', 'top_p', 'presence_penalty', 'frequency_penalty', 'output',
                                   'response_model']
                    }
                    self.nodes[func_name] = {
                        'type': 'structured_llm',
                        'llm_config': llm_config,
                        'inputs': inputs,
                        'output': llm_config.get('output'),
                    }
                else:
                    logger.warning(f"Unsupported decorator 'Nodes.{decorator_name}' in function '{func_name}'")

                # Store the function code as embedded
                func_code = ast.unparse(node)
                self.functions[func_name] = {
                    'type': 'embedded',
                    'code': func_code,
                }

        self.generic_visit(node)

    def process_workflow_expr(self, expr, var_name):
        """
        Recursively process Workflow method chaining to build transitions and structure.
        
        Args:
            expr: The AST expression to process.
            var_name: The variable name to which the workflow is assigned (for logging/context).
        
        Returns:
            str or None: The current node name or None if no specific node is returned.
        """
        if not isinstance(expr, ast.Call):
            return None

        func = expr.func
        if isinstance(func, ast.Name) and func.id == 'Workflow':
            self.start_node = expr.args[0].value if expr.args else None
            logger.debug(f"Workflow start node set to '{self.start_node}' for variable '{var_name}'")
            return self.start_node
        elif isinstance(func, ast.Attribute):
            method_name = func.attr
            obj = func.value
            previous_node = self.process_workflow_expr(obj, var_name)

            if method_name == 'then':
                next_node = expr.args[0].value if expr.args else None
                condition = None
                for keyword in expr.keywords:
                    if keyword.arg == 'condition':
                        if isinstance(keyword.value, ast.Lambda):
                            condition = ast.unparse(keyword.value)  # Capture full lambda expression
                        else:
                            condition = ast.unparse(keyword.value)
                            logger.warning(f"Non-lambda condition in 'then' for '{next_node}' may not be fully supported")
                if previous_node and next_node:
                    self.transitions.append((previous_node, next_node, condition))
                    logger.debug(f"Added transition: {previous_node} -> {next_node} (condition: {condition})")
                return next_node

            elif method_name == 'sequence':
                nodes = [arg.value for arg in expr.args]
                if previous_node:
                    self.transitions.append((previous_node, nodes[0], None))
                for i in range(len(nodes) - 1):
                    self.transitions.append((nodes[i], nodes[i + 1], None))
                    logger.debug(f"Added sequence transition: {nodes[i]} -> {nodes[i + 1]}")
                return nodes[-1] if nodes else previous_node

            elif method_name == 'parallel':
                to_nodes = [arg.value for arg in expr.args]
                if previous_node:
                    for to_node in to_nodes:
                        self.transitions.append((previous_node, to_node, None))
                        logger.debug(f"Added parallel transition: {previous_node} -> {to_node}")
                return None  # Parallel transitions reset the current node

            elif method_name == 'node':
                node_name = expr.args[0].value if expr.args else None
                if node_name and previous_node:
                    self.transitions.append((previous_node, node_name, None))
                    logger.debug(f"Added node transition: {previous_node} -> {node_name}")
                return node_name

            elif method_name == 'add_sub_workflow':
                sub_wf_name = expr.args[0].value
                sub_wf_obj = expr.args[1]
                inputs = {}
                if len(expr.args) > 2 and isinstance(expr.args[2], ast.Dict):
                    inputs = {k.s: v.s for k, v in zip(expr.args[2].keys, expr.args[2].values)}
                output = expr.args[3].value if len(expr.args) > 3 else None
                sub_extractor = WorkflowExtractor()
                sub_extractor.process_workflow_expr(sub_wf_obj, f"{var_name}_{sub_wf_name}")
                self.nodes[sub_wf_name] = {
                    'type': 'sub_workflow',
                    'sub_workflow': WorkflowStructure(
                        start=sub_extractor.start_node,
                        transitions=[
                            TransitionDefinition(from_=t[0], to=t[1], condition=t[2])
                            for t in sub_extractor.transitions
                        ]
                    ),
                    'inputs': list(inputs.keys()),
                    'output': output,
                }
                logger.debug(f"Added sub-workflow node '{sub_wf_name}' with start '{sub_extractor.start_node}'")
                if previous_node:
                    self.transitions.append((previous_node, sub_wf_name, None))
                return sub_wf_name

            else:
                logger.warning(f"Unsupported Workflow method '{method_name}' in variable '{var_name}'")
        return None


def extract_workflow_from_file(file_path):
    """
    Extract a WorkflowDefinition from a Python file containing a workflow.

    Args:
        file_path (str): Path to the Python file to parse.

    Returns:
        WorkflowDefinition: A schema object representing the workflow, usable by WorkflowManager.
    """
    # Read and parse the file
    with open(file_path, 'r') as f:
        source = f.read()
    tree = ast.parse(source)

    # Extract workflow components
    extractor = WorkflowExtractor()
    extractor.visit(tree)

    # Construct FunctionDefinition objects
    functions = {
        name: FunctionDefinition(**func)
        for name, func in extractor.functions.items()
    }

    # Construct NodeDefinition objects
    nodes = {}
    for name, node_info in extractor.nodes.items():
        if node_info['type'] == 'function':
            nodes[name] = NodeDefinition(
                function=node_info['function'],
                output=node_info['output'],
                retries=3,    # Default values
                delay=1.0,
                timeout=None,
                parallel=False,
            )
        elif node_info['type'] == 'llm':
            nodes[name] = NodeDefinition(
                llm_config=node_info['llm_config'],
                output=node_info['output'],
                retries=3,
                delay=1.0,
                timeout=None,
                parallel=False,
            )
        elif node_info['type'] == 'structured_llm':
            nodes[name] = NodeDefinition(
                llm_config=node_info['llm_config'],
                output=node_info['output'],
                retries=3,
                delay=1.0,
                timeout=None,
                parallel=False,
            )
        elif node_info['type'] == 'sub_workflow':
            nodes[name] = NodeDefinition(
                sub_workflow=node_info['sub_workflow'],
                output=node_info['output'],
                retries=3,
                delay=1.0,
                timeout=None,
                parallel=False,
            )

    # Construct TransitionDefinition objects
    transitions = [
        TransitionDefinition(from_=from_, to=to, condition=cond)
        for from_, to, cond in extractor.transitions
    ]

    # Build WorkflowStructure
    workflow_structure = WorkflowStructure(
        start=extractor.start_node,
        transitions=transitions
    )

    # Assemble WorkflowDefinition
    workflow_def = WorkflowDefinition(
        functions=functions,
        nodes=nodes,
        workflow=workflow_structure
    )

    return workflow_def


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
            print(f"  Type: Function")
            print(f"  Function: {node.function}")
        elif node.llm_config:
            print(f"  Type: LLM")
            print(f"  Model: {node.llm_config.get('model', 'N/A')}")
            print(f"  Prompt Template: {node.llm_config.get('prompt_template', 'N/A')}")
        elif node.sub_workflow:
            print(f"  Type: Sub-Workflow")
            print(f"  Start Node: {node.sub_workflow.start}")
        print(f"  Output: {node.output or 'None'}")

    print("\n#### Workflow Structure:")
    print(f"Start Node: {workflow_def.workflow.start}")
    print("Transitions:")
    for trans in workflow_def.workflow.transitions:
        print(f"- {trans.from_} -> {trans.to}" + (f" [Condition: {trans.condition}]" if trans.condition else ""))


def main():
    """Demonstrate parsing the story_generator_agent.py workflow."""
    file_path = "examples/qflow/story_generator_agent.py"
    try:
        workflow_def = extract_workflow_from_file(file_path)
        logger.info(f"Successfully extracted workflow from '{file_path}'")
        print_workflow_definition(workflow_def)
    except FileNotFoundError:
        logger.error(f"File '{file_path}' not found. Please ensure it exists in the specified directory.")
    except Exception as e:
        logger.error(f"Failed to parse workflow from '{file_path}': {e}")


if __name__ == "__main__":
    main()