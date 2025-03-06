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
    Generate an executable Python script from a WorkflowDefinition with global variables using decorators.

    Args:
        workflow_def: The WorkflowDefinition object containing the workflow details.
        global_vars: Dictionary of global variables extracted from the source file.
        output_file: The path where the executable script will be written.
        initial_context: Optional initial context; if None, inferred from the workflow with default values.

    The generated script includes:
    - A shebang using `uv run` for environment management.
    - Metadata specifying the required Python version and dependencies.
    - Global variables from the original script.
    - Functions defined with appropriate Nodes decorators (e.g., @Nodes.define, @Nodes.llm_node).
    - Workflow instantiation using direct chaining syntax with function names, including branch and converge.
    - Support for input mappings and template nodes via workflow configuration and decorators.
    - A default initial_context inferred from the workflow with customization guidance.
    """
    # Infer initial context if not provided
    if initial_context is None:
        initial_context = {}
        start_node = workflow_def.workflow.start
        if start_node and start_node in workflow_def.nodes:
            node_def = workflow_def.nodes[start_node]
            if node_def.function:
                if node_def.function in workflow_def.functions:
                    func_def = workflow_def.functions[node_def.function]
                    if func_def.type == "embedded" and func_def.code:
                        try:
                            tree = ast.parse(func_def.code)
                            for node in ast.walk(tree):
                                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                    inputs = [param.arg for param in node.args.args]
                                    # Assign default values: empty string for strings, 0 for numbers, etc.
                                    for input_name in inputs:
                                        initial_context[input_name] = ""  # Default to empty string for simplicity
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
                for var in cleaned_inputs:
                    initial_context[var] = ""
            elif node_def.template_config:
                template = node_def.template_config.template or ""
                input_vars = set(re.findall(r"{{\s*([^}]+?)\s*}}", template))
                cleaned_inputs = {
                    re.split(r"\s*[\+\-\*/]\s*", var.strip())[0].strip()
                    for var in input_vars
                    if var.strip().isidentifier()
                }
                initial_context = {"rendered_content": "", **{var: "" for var in cleaned_inputs}}
            elif node_def.sub_workflow:
                sub_start = node_def.sub_workflow.start or f"{start_node}_start"
                if sub_start in workflow_def.nodes:
                    sub_node_def = workflow_def.nodes[sub_start]
                    if sub_node_def.function in workflow_def.functions:
                        func_def = workflow_def.functions[sub_node_def.function]
                        if func_def.type == "embedded" and func_def.code:
                            try:
                                tree = ast.parse(func_def.code)
                                for node in ast.walk(tree):
                                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                        inputs = [param.arg for param in node.args.args]
                                        for input_name in inputs:
                                            initial_context[input_name] = ""
                                        break
                            except SyntaxError:
                                pass
            # Apply inputs_mapping if present
            if node_def.inputs_mapping:
                for key, value in node_def.inputs_mapping.items():
                    if not value.startswith("lambda ctx:"):  # Only static mappings contribute to context
                        initial_context[value] = ""

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

        # Define functions with decorators
        for node_name, node_def in workflow_def.nodes.items():
            if node_def.function and node_def.function in workflow_def.functions:
                func_def = workflow_def.functions[node_def.function]
                if func_def.type == "embedded" and func_def.code:
                    # Strip original decorator and apply new one
                    code_lines = func_def.code.split('\n')
                    func_body = ""
                    for line in code_lines:
                        if line.strip().startswith('@Nodes.'):
                            continue  # Skip original decorator
                        func_body += line + "\n"
                    func_body = func_body.rstrip("\n")

                    # Generate new decorator based on node type
                    decorator = ""
                    if node_def.llm_config:
                        params = [f"model={repr(node_def.llm_config.model)}"]
                        if node_def.llm_config.system_prompt:
                            params.append(f"system_prompt={repr(node_def.llm_config.system_prompt)}")
                        if node_def.llm_config.prompt_template:
                            params.append(f"prompt_template={repr(node_def.llm_config.prompt_template)}")
                        if node_def.llm_config.prompt_file:
                            params.append(f"prompt_file={repr(node_def.llm_config.prompt_file)}")
                        params.append(f"output={repr(node_def.output or f'{node_name}_result')}")
                        for param in ["temperature", "max_tokens", "top_p", "presence_penalty", "frequency_penalty"]:
                            value = getattr(node_def.llm_config, param, None)
                            if value is not None:
                                params.append(f"{param}={repr(value)}")
                        decorator = f"@Nodes.llm_node({', '.join(params)})\n"
                    elif node_def.template_config:
                        params = [f"output={repr(node_def.output or f'{node_name}_result')}"]
                        if node_def.template_config.template:
                            params.append(f"template={repr(node_def.template_config.template)}")
                        if node_def.template_config.template_file:
                            params.append(f"template_file={repr(node_def.template_config.template_file)}")
                        decorator = f"@Nodes.template_node({', '.join(params)})\n"
                    else:
                        decorator = f"@Nodes.define(output={repr(node_def.output or f'{node_name}_result')})\n"
                    # Write function with new decorator
                    f.write(f"{decorator}{func_body}\n\n")

        # Define workflow using function names
        f.write("# Define the workflow with branch and converge support\n")
        f.write("workflow = (\n")
        start_node = workflow_def.workflow.start
        start_func = workflow_def.nodes[start_node].function if start_node in workflow_def.nodes and workflow_def.nodes[start_node].function else start_node
        f.write(f'    Workflow("{start_func}")\n')

        for node_name, node_def in workflow_def.nodes.items():
            func_name = node_def.function if node_def.function else node_name
            if node_def.sub_workflow:
                sub_start = node_def.sub_workflow.start or f"{node_name}_start"
                sub_start_func = workflow_def.nodes[sub_start].function if sub_start in workflow_def.nodes and workflow_def.nodes[sub_start].function else sub_start
                f.write(f'    .add_sub_workflow("{node_name}", Workflow("{sub_start_func}"), ')
                if node_def.inputs_mapping:
                    inputs_mapping_str = "{"
                    for k, v in node_def.inputs_mapping.items():
                        if v.startswith("lambda ctx:"):
                            inputs_mapping_str += f"{repr(k)}: {v}, "
                        else:
                            inputs_mapping_str += f"{repr(k)}: {repr(v)}, "
                    inputs_mapping_str = inputs_mapping_str.rstrip(", ") + "}"
                    f.write(f"inputs={inputs_mapping_str}, ")
                else:
                    inputs = []
                    if sub_start in workflow_def.nodes and workflow_def.nodes[sub_start].function in workflow_def.functions:
                        func_def = workflow_def.functions[workflow_def.nodes[sub_start].function]
                        if func_def.code:
                            try:
                                tree = ast.parse(func_def.code)
                                for node in ast.walk(tree):
                                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                        inputs = [param.arg for param in node.args.args]
                                        break
                            except SyntaxError:
                                pass
                    f.write(f'inputs={{{", ".join(f"{k!r}: {k!r}" for k in inputs)}}}, ')
                f.write(f'output="{node_def.output or f"{node_name}_result"}")\n')
            else:
                if node_def.inputs_mapping:
                    inputs_mapping_str = "{"
                    for k, v in node_def.inputs_mapping.items():
                        if v.startswith("lambda ctx:"):
                            inputs_mapping_str += f"{repr(k)}: {v}, "
                        else:
                            inputs_mapping_str += f"{repr(k)}: {repr(v)}, "
                    inputs_mapping_str = inputs_mapping_str.rstrip(", ") + "}"
                    f.write(f'    .node("{func_name}", inputs_mapping={inputs_mapping_str})\n')
                else:
                    f.write(f'    .node("{func_name}")\n')

        for trans in workflow_def.workflow.transitions:
            from_node = trans.from_node
            from_func = workflow_def.nodes[from_node].function if from_node in workflow_def.nodes and workflow_def.nodes[from_node].function else from_node
            to_node = trans.to_node
            if isinstance(to_node, str):
                to_func = workflow_def.nodes[to_node].function if to_node in workflow_def.nodes and workflow_def.nodes[to_node].function else to_node
                condition = f"lambda ctx: {trans.condition}" if trans.condition else "None"
                f.write(f'    .then("{to_func}", condition={condition})\n')
            elif all(isinstance(tn, str) for tn in to_node):
                to_funcs = [workflow_def.nodes[tn].function if tn in workflow_def.nodes and workflow_def.nodes[tn].function else tn for tn in to_node]
                f.write(f'    .parallel({", ".join(f"{n!r}" for n in to_funcs)})\n')
            else:  # BranchCondition list
                branches = []
                for branch in to_node:
                    branch_func = workflow_def.nodes[branch.to_node].function if branch.to_node in workflow_def.nodes and workflow_def.nodes[branch.to_node].function else branch.to_node
                    cond = f"lambda ctx: {branch.condition}" if branch.condition else "None"
                    branches.append(f'("{branch_func}", {cond})')
                f.write(f'    .branch([{", ".join(branches)}])\n')

        for conv_node in workflow_def.workflow.convergence_nodes:
            conv_func = workflow_def.nodes[conv_node].function if conv_node in workflow_def.nodes and workflow_def.nodes[conv_node].function else conv_node
            f.write(f'    .converge("{conv_func}")\n')

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
    manager.add_node(name="start", function="greet", output="greeting", inputs_mapping={"name": "user_name"})
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