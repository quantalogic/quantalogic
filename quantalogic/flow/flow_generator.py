import ast
import os
import re
from typing import Dict, Optional

from quantalogic.flow.flow import Nodes  # Import Nodes to access NODE_REGISTRY
from quantalogic.flow.flow_manager_schema import BranchCondition, WorkflowDefinition  # Added BranchCondition import


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
    - Workflow instantiation using direct chaining syntax, including branch and converge.
    - A default initial_context inferred from the workflow with customization guidance.
    """
    # Infer initial context if not provided
    if initial_context is None:
        initial_context = {}
        start_node = workflow_def.workflow.start
        if start_node and start_node in workflow_def.nodes:
            node_def = workflow_def.nodes[start_node]
            if node_def.function:
                if start_node in Nodes.NODE_REGISTRY:
                    inputs = Nodes.NODE_REGISTRY[start_node][1]
                    initial_context = {input_name: None for input_name in inputs}
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
                            pass
            elif node_def.llm_config:
                prompt = node_def.llm_config.prompt_template or ""
                input_vars = set(re.findall(r"{{\s*([^}]+?)\s*}}", prompt))
                cleaned_inputs = {
                    re.split(r"\s*[\+\-\*/]\s*", var.strip())[0].strip()
                    for var in input_vars
                    if var.strip().isidentifier()
                }
                initial_context = {var: None for var in cleaned_inputs}
            elif node_def.sub_workflow:
                sub_start = node_def.sub_workflow.start or f"{start_node}_start"
                if sub_start in Nodes.NODE_REGISTRY:
                    inputs = Nodes.NODE_REGISTRY[sub_start][1]
                    initial_context = {input_name: None for input_name in inputs}
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
        # Shebang and metadata
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

        # Imports
        f.write("import anyio\n")
        f.write("from typing import List\n")
        f.write("from loguru import logger\n")
        f.write("from quantalogic.flow import Nodes, Workflow\n\n")

        # Global variables
        for var_name, value in global_vars.items():
            f.write(f"{var_name} = {repr(value)}\n")
        f.write("\n")

        # Embed functions
        for func_name, func_def in workflow_def.functions.items():
            if func_def.type == "embedded" and func_def.code:
                f.write(func_def.code + "\n\n")

        # Register nodes
        f.write("# Register nodes with their workflow names\n")
        for node_name, node_def in workflow_def.nodes.items():
            if node_def.function and node_def.function in workflow_def.functions:
                output = node_def.output or f"{node_name}_result"
                func_name = node_def.function
                inputs = []
                func_def = workflow_def.functions[func_name]
                if func_def.code:
                    try:
                        tree = ast.parse(func_def.code)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.FunctionDef):
                                inputs = [param.arg for param in node.args.args]
                                break
                    except SyntaxError:
                        pass
                f.write(f"Nodes.NODE_REGISTRY['{node_name}'] = ({func_name}, {repr(inputs)}, {repr(output)})\n")

        # Define workflow
        f.write("\n# Define the workflow with branch and converge support\n")
        f.write("workflow = (\n")
        f.write(f'    Workflow("{workflow_def.workflow.start}")\n')

        for node_name, node_def in workflow_def.nodes.items():
            if node_def.sub_workflow:
                sub_start = node_def.sub_workflow.start or f"{node_name}_start"
                f.write(f'    .add_sub_workflow("{node_name}", Workflow("{sub_start}"), ')
                inputs = Nodes.NODE_REGISTRY.get(sub_start, ([], None))[0] if sub_start in Nodes.NODE_REGISTRY else []
                f.write(f'inputs={{{", ".join(f"{k!r}: {k!r}" for k in inputs)}}}, ')
                f.write(f'output="{node_def.output or f"{node_name}_result"}")\n')
            else:
                f.write(f'    .node("{node_name}")\n')

        for trans in workflow_def.workflow.transitions:
            from_node = trans.from_node
            to_node = trans.to_node
            if isinstance(to_node, str):
                condition = f"lambda ctx: {trans.condition}" if trans.condition else "None"
                f.write(f'    .then("{to_node}", condition={condition})\n')
            elif all(isinstance(tn, str) for tn in to_node):
                f.write(f'    .parallel({", ".join(f"{n!r}" for n in to_node)})\n')
            else:  # BranchCondition list
                branches = []
                for branch in to_node:
                    cond = f"lambda ctx: {branch.condition}" if branch.condition else "None"
                    branches.append(f'("{branch.to_node}", {cond})')
                f.write(f'    .branch([{", ".join(branches)}])\n')

        for conv_node in workflow_def.workflow.convergence_nodes:
            f.write(f'    .converge("{conv_node}")\n')

        if hasattr(workflow_def, 'observers'):
            for observer in workflow_def.observers:
                f.write(f"    .add_observer({observer})\n")
        f.write(")\n\n")

        # Main function
        f.write("async def main():\n")
        f.write('    """Main function to run the workflow."""\n')
        f.write("    # Customize initial_context as needed\n")
        f.write("    # Inferred required inputs:\n")
        inferred_inputs = list(initial_context.keys())
        f.write(f"    # {', '.join(inferred_inputs) if inferred_inputs else 'None detected'}\n")
        f.write("    initial_context = {\n")
        for key, value in initial_context.items():
            f.write(f"        {repr(key)}: {repr(value)},\n")
        f.write("    }\n")
        f.write("    engine = workflow.build()\n")
        f.write("    result = await engine.run(initial_context)\n")
        f.write('    logger.info(f"Workflow result: {result}")\n\n')

        # Entry point
        f.write('if __name__ == "__main__":\n')
        f.write("    anyio.run(main)\n")

    os.chmod(output_file, 0o755)


if __name__ == "__main__":
    from quantalogic.flow.flow_manager import WorkflowManager

    manager = WorkflowManager()
    manager.add_function(
        name="greet",
        type_="embedded",
        code="async def greet(name): return f'Hello, {name}!'",
    )
    manager.add_function(
        name="check",
        type_="embedded",
        code="async def check(name): return len(name) > 3",
    )
    manager.add_function(
        name="end",
        type_="embedded",
        code="async def end(greeting): return f'{greeting} Goodbye!'",
    )
    manager.add_node(name="start", function="greet", output="greeting")
    manager.add_node(name="check", function="check", output="condition")
    manager.add_node(name="end", function="end", output="farewell")
    manager.set_start_node("start")
    manager.add_transition(
        from_node="start",
        to_node=[
            BranchCondition(to_node="check", condition="ctx['name'] == 'Alice'")
        ]
    )
    manager.add_convergence_node("end")
    wf_def = manager.workflow
    global_vars = {"MY_CONSTANT": 42}
    generate_executable_script(wf_def, global_vars, "workflow_script.py")