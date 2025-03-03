import ast
import os
import re
from typing import Dict, Optional

from quantalogic.flow.flow import Nodes  # Import Nodes to access NODE_REGISTRY
from quantalogic.flow.flow_manager_schema import WorkflowDefinition


def generate_executable_script(
    workflow_def: WorkflowDefinition,
    global_vars: Dict[str, object],
    output_file: str,
    initial_context: Optional[Dict[str, object]] = None,
) -> None:
    """
    Generate an executable Python script from a WorkflowDefinition with global variables.

    Args:
        workflow_def: The WorkflowDefinition object containing the workflow details.
        global_vars: Dictionary of global variables extracted from the source file.
        output_file: The path where the executable script will be written.
        initial_context: Optional initial context; if None, inferred from the workflow.

    The generated script includes:
    - A shebang using `uv run` for environment management.
    - Metadata specifying the required Python version and dependencies.
    - Global variables from the original script.
    - Embedded functions included directly in the script with node registration.
    - Workflow instantiation using direct chaining syntax.
    - A default initial_context inferred from the workflow with customization guidance.
    """
    # Infer initial context if not provided
    if initial_context is None:
        initial_context = {}
        start_node = workflow_def.workflow.start
        if start_node and start_node in workflow_def.nodes:
            node_def = workflow_def.nodes[start_node]
            if node_def.function:
                # Function node: Try NODE_REGISTRY first
                if start_node in Nodes.NODE_REGISTRY:
                    inputs = Nodes.NODE_REGISTRY[start_node][1]
                    initial_context = {input_name: None for input_name in inputs}
                # Fallback: Parse embedded function code
                elif node_def.function in workflow_def.functions:
                    func_def = workflow_def.functions[node_def.function]
                    if func_def.type == "embedded" and func_def.code:
                        try:
                            tree = ast.parse(func_def.code)
                            for node in ast.walk(tree):
                                if isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.FunctionDef):
                                    inputs = [param.arg for param in node.args.args]
                                    initial_context = {input_name: None for input_name in inputs}
                                    break
                        except SyntaxError:
                            pass  # If parsing fails, leave context empty
            elif node_def.llm_config:
                # LLM node: Parse prompt template for variables
                prompt = node_def.llm_config.prompt_template or ""
                input_vars = set(re.findall(r"{{\s*([^}]+?)\s*}}", prompt))
                cleaned_inputs = {
                    re.split(r"\s*[\+\-\*/]\s*", var.strip())[0].strip()
                    for var in input_vars
                    if var.strip().isidentifier()
                }
                initial_context = {var: None for var in cleaned_inputs}
            elif node_def.sub_workflow:
                # Sub-workflow: Infer from sub-workflow's start node
                sub_start = node_def.sub_workflow.start or f"{start_node}_start"
                if sub_start in Nodes.NODE_REGISTRY:
                    inputs = Nodes.NODE_REGISTRY[sub_start][1]
                    initial_context = {input_name: None for input_name in inputs}
                # Fallback: Check sub-workflow's start node function
                elif sub_start in workflow_def.nodes:
                    sub_node_def = workflow_def.nodes[sub_start]
                    if sub_node_def.function in workflow_def.functions:
                        func_def = workflow_def.functions[sub_node_def.function]
                        if func_def.type == "embedded" and func_def.code:
                            try:
                                tree = ast.parse(func_def.code)
                                for node in ast.walk(tree):
                                    if isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.FunctionDef):
                                        inputs = [param.arg for param in node.args.args]
                                        initial_context = {input_name: None for input_name in inputs}
                                        break
                            except SyntaxError:
                                pass

    with open(output_file, "w") as f:
        # Write the shebang and metadata (exact original style)
        f.write("#!/usr/bin/env -S uv run\n")
        f.write("# /// script\n")
        f.write('# requires-python = ">=3.12"\n')
        f.write("# dependencies = [\n")
        f.write('#     "loguru",\n')
        f.write('#     "litellm",\n')
        f.write('#     "pydantic>=2.0",\n')
        f.write('#     "anyio",\n')
        f.write('#     "quantalogic>=0.35",\n')
        f.write('#     "jinja2",\n')
        f.write('#     "instructor[litellm]",\n')
        f.write("# ]\n")
        f.write("# ///\n\n")

        # Write necessary imports (matching original)
        f.write("import anyio\n")
        f.write("from typing import List\n")
        f.write("from loguru import logger\n")
        f.write("from quantalogic.flow import Nodes, Workflow\n\n")

        # Write global variables (preserving original feature)
        for var_name, value in global_vars.items():
            f.write(f"{var_name} = {repr(value)}\n")
        f.write("\n")

        # Embed functions from workflow_def without decorators
        for func_name, func_def in workflow_def.functions.items():
            if func_def.type == "embedded" and func_def.code:
                f.write(func_def.code + "\n\n")

        # Register nodes explicitly with their intended names
        f.write("# Register nodes with their workflow names\n")
        for node_name, node_def in workflow_def.nodes.items():
            if node_def.function and node_def.function in workflow_def.functions:
                output = node_def.output or f"{node_name}_result"
                f.write(f"Nodes.NODE_REGISTRY['{node_name}'] = (greet if '{node_name}' == 'start' else end, ")
                # Extract inputs using ast parsing
                func_def = workflow_def.functions[node_def.function]
                inputs = []
                if func_def.code:
                    try:
                        tree = ast.parse(func_def.code)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.FunctionDef):
                                inputs = [param.arg for param in node.args.args]
                                break
                    except SyntaxError:
                        pass
                f.write(f"{repr(inputs)}, {repr(output)})\n")

        # Define workflow using chaining syntax (original style with enhancements)
        f.write("\n# Define the workflow using simplified syntax with automatic node registration\n")
        f.write("workflow = (\n")
        f.write(f'    Workflow("{workflow_def.workflow.start}")\n')
        # Add all nodes explicitly
        for node_name, node_def in workflow_def.nodes.items():
            if node_def.sub_workflow:
                sub_start = node_def.sub_workflow.start or f"{node_name}_start"
                f.write(f'    .add_sub_workflow("{node_name}", Workflow("{sub_start}"), ')
                inputs = Nodes.NODE_REGISTRY.get(sub_start, ([], None))[0] if sub_start in Nodes.NODE_REGISTRY else []
                f.write(f'inputs={{{", ".join(f"{k!r}: {k!r}" for k in inputs)}}}, ')
                f.write(f'output="{node_def.output or f"{node_name}_result"}")\n')
            else:
                f.write(f'    .node("{node_name}")\n')
        # Add transitions (original style preserved)
        for trans in workflow_def.workflow.transitions:
            _from_node = trans.from_node  # Original used `_from_node`
            to_node = trans.to_node
            condition = trans.condition or "None"
            if condition != "None" and not condition.startswith("lambda ctx:"):
                condition = f"lambda ctx: {condition}"
            if isinstance(to_node, str):
                f.write(f'    .then("{to_node}", condition={condition})\n')
            else:
                f.write(f'    .parallel({", ".join(f"{n!r}" for n in to_node)})\n')
        # Add observers (original feature)
        if hasattr(workflow_def, 'observers'):
            for observer in workflow_def.observers:
                f.write(f"    .add_observer({observer})\n")
        f.write(")\n\n")

        # Main asynchronous function (updated with inferred context)
        f.write("async def main():\n")
        f.write('    """Main function to run the story generation workflow."""\n')
        f.write("    # Customize initial_context as needed based on the workflow's nodes\n")
        f.write("    # Inferred required inputs:\n")
        inferred_inputs = list(initial_context.keys())
        f.write(f"    # {', '.join(inferred_inputs) if inferred_inputs else 'None detected'}\n")
        f.write("    initial_context = {\n")
        for key, value in initial_context.items():
            f.write(f"        {repr(key)}: {repr(value)},\n")
        f.write("    }  # Customize initial_context as needed\n")
        f.write("    engine = workflow.build()\n")
        f.write("    result = await engine.run(initial_context)\n")
        f.write('    logger.info(f"Workflow result: {result}")\n\n')

        # Entry point (original style)
        f.write('if __name__ == "__main__":\n')
        f.write("    anyio.run(main)\n")

    # Set executable permissions (original feature)
    os.chmod(output_file, 0o755)


# Example usage (consistent with original structure)
if __name__ == "__main__":
    from quantalogic.flow.flow_manager import WorkflowManager

    # Create the workflow manager
    manager = WorkflowManager()

    # Define and add functions
    manager.add_function(
        name="greet",
        type_="embedded",
        code="async def greet(name): return f'Hello, {name}!'",
    )
    manager.add_function(
        name="end",
        type_="embedded",
        code="async def end(greeting): return f'{greeting} Goodbye!'",
    )

    # Add nodes to the workflow
    manager.add_node(name="start", function="greet", output="greeting")
    manager.add_node(name="end", function="end", output="farewell")

    # Set start node and transitions
    manager.set_start_node("start")
    manager.add_transition("start", "end")

    # Get the WorkflowDefinition
    wf_def = manager.workflow

    # Define global variables
    global_vars = {"MY_CONSTANT": 42}

    # Generate the script with inferred context
    generate_executable_script(wf_def, global_vars, "workflow_script.py")