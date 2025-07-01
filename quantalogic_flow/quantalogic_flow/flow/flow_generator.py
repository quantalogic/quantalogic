import ast
import os
import re
from typing import Dict, Optional

from quantalogic_flow.flow.flow_manager_schema import BranchCondition, WorkflowDefinition


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
    - Workflow instantiation using direct chaining syntax with function names, including branch, converge, and loop support.
    - Support for input mappings and template nodes via workflow configuration and decorators.
    - A default initial_context inferred from the workflow with customization guidance.
    """
    # Infer initial context if not provided
    if initial_context is None:
        initial_context = {}
        start_node = workflow_def.workflow.start
        if start_node and start_node in workflow_def.nodes:
            node_def = workflow_def.nodes[start_node]
            if node_def.function and node_def.function in workflow_def.functions:
                func_def = workflow_def.functions[node_def.function]
                if func_def.type == "embedded" and func_def.code:
                    try:
                        tree = ast.parse(func_def.code)
                        for node in ast.walk(tree):
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                inputs = [param.arg for param in node.args.args]
                                for input_name in inputs:
                                    initial_context[input_name] = ""  # Default to empty string
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
            if node_def.inputs_mapping:
                for key, value in node_def.inputs_mapping.items():
                    if not value.startswith("lambda ctx:"):  # Static mappings only
                        initial_context[value] = ""

    # Detect loops and nested loops from schema
    loops = []
    if hasattr(workflow_def.workflow, 'loops') and workflow_def.workflow.loops:
        # Use explicit loop definitions from schema
        for loop_def in workflow_def.workflow.loops:
            loops.append({
                'nodes': loop_def.nodes,
                'condition': loop_def.condition,
                'exit_node': loop_def.exit_node
            })
    else:
        # Legacy: detect simple loops from transitions
        loop_nodes = []
        for trans in workflow_def.workflow.transitions:
            if isinstance(trans.to_node, str) and trans.condition:
                # Check for loop-back transition
                if any(t.from_node == trans.to_node and t.to_node == trans.from_node for t in workflow_def.workflow.transitions):
                    loop_nodes.append(trans.from_node)
                    loop_nodes.append(trans.to_node)
        loop_nodes = list(dict.fromkeys(loop_nodes))  # Remove duplicates, preserve order
        if loop_nodes:
            # Create simple loop structure
            loops.append({
                'nodes': loop_nodes,
                'condition': 'True',  # Placeholder
                'exit_node': 'end'
            })

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
        f.write('#     "quantalogic_flow>=0.35",\n')
        f.write('#     "jinja2",\n')
        f.write('#     "instructor[litellm]",\n')
        f.write("# ]\n")
        f.write("# ///\n\n")

        # Imports
        f.write("import anyio\n")
        f.write("from typing import List\n")
        f.write("from loguru import logger\n")
        f.write("from quantalogic_flow.flow import Nodes, Workflow\n\n")

        # Global variables
        for var_name, value in global_vars.items():
            if isinstance(value, str):
                f.write(f'{var_name} = "{value}"\n')
            else:
                f.write(f"{var_name} = {repr(value)}\n")
        f.write("\n")

        # Define functions with decorators
        for node_name, node_def in workflow_def.nodes.items():
            decorator = ""
            func_body = ""
            
            # Handle LLM nodes
            if node_def.llm_config:
                params = []
                if node_def.llm_config.model.startswith("lambda ctx:"):
                    params.append(f"model={node_def.llm_config.model}")
                else:
                    params.append(f"model={repr(node_def.llm_config.model)}")
                if node_def.llm_config.system_prompt_file:
                    params.append(f"system_prompt_file={repr(node_def.llm_config.system_prompt_file)}")
                elif node_def.llm_config.system_prompt:
                    params.append(f"system_prompt={repr(node_def.llm_config.system_prompt)}")
                if node_def.llm_config.prompt_template:
                    params.append(f"prompt_template={repr(node_def.llm_config.prompt_template)}")
                if node_def.llm_config.prompt_file:
                    params.append(f"prompt_file={repr(node_def.llm_config.prompt_file)}")
                default_output = f'{node_name}_result'
                params.append(f"output={repr(node_def.output or default_output)}")
                for param in ["temperature", "max_tokens", "top_p", "presence_penalty", "frequency_penalty"]:
                    value = getattr(node_def.llm_config, param, None)
                    if value is not None:
                        params.append(f"{param}={repr(value)}")
                decorator = f"@Nodes.llm_node({', '.join(params)})\n"
                func_body = f"def {node_name}(input):\n    pass\n"
                
            # Handle template nodes
            elif node_def.template_config:
                default_output = f'{node_name}_result'
                params = [f"output={repr(node_def.output or default_output)}"]
                if node_def.template_config.template:
                    params.append(f"template={repr(node_def.template_config.template)}")
                if node_def.template_config.template_file:
                    params.append(f"template_file={repr(node_def.template_config.template_file)}")
                decorator = f"@Nodes.template_node({', '.join(params)})\n"
                func_body = f"def {node_name}(input):\n    pass\n"
                
            # Handle function-based nodes
            elif node_def.function and node_def.function in workflow_def.functions:
                func_def = workflow_def.functions[node_def.function]
                if func_def.type == "embedded" and func_def.code:
                    code_lines = func_def.code.split('\n')
                    func_body = "".join(
                        line + "\n" for line in code_lines if not line.strip().startswith('@Nodes.')
                    ).rstrip("\n")
                    
                    # Build decorator parameters
                    default_output = f'{node_name}_result'
                    params = [f"output={repr(node_def.output or default_output)}"]
                    
                    # Add input mappings if present
                    if node_def.inputs_mapping:
                        mapping_dict = {}
                        for key, value in node_def.inputs_mapping.items():
                            mapping_dict[key] = value
                        params.append(f"inputs_mapping={repr(mapping_dict)}")
                    
                    decorator = f"@Nodes.define({', '.join(params)})\n"
            
            if decorator and func_body:
                f.write(f"{decorator}{func_body}\n\n")

        # Define workflow using chaining syntax with loop support
        f.write("# Define the workflow with branch, converge, and loop support\n")
        f.write("workflow = (\n")
        start_node = workflow_def.workflow.start
        f.write(f'    Workflow("{start_node}")\n')

        # Build sequence from transitions
        # Look for simple sequential transitions (no conditions, single targets)
        # But first check if start node has multiple transitions (indicating branches)
        start_transitions = [t for t in workflow_def.workflow.transitions if t.from_node == start_node]
        
        sequence_nodes = []
        current = start_node
        processed_transitions = set()
        
        # Only look for sequences if start node doesn't have multiple transitions
        if len(start_transitions) <= 1:
            # Find sequential chain from start node  
            while True:
                found_next = False
                for trans in workflow_def.workflow.transitions:
                    if (trans.from_node == current and 
                        isinstance(trans.to_node, str) and 
                        trans.condition is None):
                        sequence_nodes.append(trans.to_node)
                        processed_transitions.add((trans.from_node, trans.to_node))
                        current = trans.to_node
                        found_next = True
                        break
                if not found_next:
                    break
        
        # If we found a sequence, use .sequence()
        if sequence_nodes:
            # Use node names directly
            node_names_quoted = [f'"{node_name}"' for node_name in sequence_nodes]
            f.write(f'    .sequence({", ".join(node_names_quoted)})\n')
        
        # Group remaining transitions by from_node to detect branches
        remaining_transitions = [trans for trans in workflow_def.workflow.transitions 
                               if (trans.from_node, trans.to_node) not in processed_transitions]
        
        transitions_by_node = {}
        for trans in remaining_transitions:
            if trans.from_node not in transitions_by_node:
                transitions_by_node[trans.from_node] = []
            transitions_by_node[trans.from_node].append(trans)
        
        # Process grouped transitions
        for from_node, transitions in transitions_by_node.items():
            if len(transitions) > 1:
                # Multiple transitions from same node = branch
                branches = []
                default_branch = None
                
                for trans in transitions:
                    if isinstance(trans.to_node, str):
                        if trans.condition:
                            # Remove "lambda ctx: " prefix if it exists to avoid double lambda
                            condition = trans.condition
                            if condition.startswith("lambda ctx: "):
                                condition = condition[12:]  # Remove "lambda ctx: " prefix
                            cond = f"lambda ctx: {condition}"
                            branches.append(f'("{trans.to_node}", {cond})')
                        else:
                            default_branch = trans.to_node
                
                if branches:
                    if default_branch:
                        f.write(f'    .branch([{", ".join(branches)}], default="{default_branch}")\n')
                    else:
                        f.write(f'    .branch([{", ".join(branches)}])\n')
            else:
                # Single transition
                trans = transitions[0]
                if isinstance(trans.to_node, str):
                    condition = f"lambda ctx: {trans.condition}" if trans.condition else "None"
                    f.write(f'    .then("{trans.to_node}", condition={condition})\n')
                elif all(isinstance(tn, str) for tn in trans.to_node):
                    to_nodes_quoted = [f'"{tn}"' for tn in trans.to_node]
                    f.write(f'    .parallel({", ".join(to_nodes_quoted)})\n')
                else:  # BranchCondition list
                    branches = []
                    for branch in trans.to_node:
                        cond = f"lambda ctx: {branch.condition}" if branch.condition else "None"
                        branches.append(f'("{branch.to_node}", {cond})')
                    f.write(f'    .branch([{", ".join(branches)}])\n')

        # Generate loops (including nested loops)
        for loop in loops:
            if loop['nodes']:
                f.write('    .start_loop()\n')
                # Add nodes in loop sequence
                for i, node in enumerate(loop['nodes']):
                    if i == 0:
                        f.write(f'    .node("{node}")\n')
                    else:
                        f.write(f'    .then("{node}")\n')
                # End loop with condition
                condition = loop['condition']
                if not condition.startswith('lambda ctx:'):
                    condition = f"lambda ctx: {condition}"
                f.write(f'    .end_loop({condition}, "{loop["exit_node"]}")\n')

        for conv_node in workflow_def.workflow.convergence_nodes:
            # Always use node names for workflow construction
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
    from quantalogic_flow.flow.flow_manager import WorkflowManager

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