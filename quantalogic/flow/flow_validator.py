import ast
import re
from collections import defaultdict
from typing import Dict, List, Optional, Set, Union

from pydantic import BaseModel

from quantalogic.flow.flow_manager import WorkflowManager
from quantalogic.flow.flow_manager_schema import (
    BranchCondition,
    NodeDefinition,
    TransitionDefinition,
    WorkflowDefinition,
    WorkflowStructure,
)


class NodeError(BaseModel):
    """Represents an error associated with a specific node or workflow component."""
    node_name: Optional[str] = None  # None if the error isn’t tied to a specific node
    description: str


def get_function_params(code: str, func_name: str) -> List[str]:
    """Extract parameter names from an embedded function's code."""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return [arg.arg for arg in node.args.args]
        raise ValueError(f"Function '{func_name}' not found in code")
    except SyntaxError as e:
        raise ValueError(f"Invalid syntax in code: {e}")


def validate_workflow_definition(workflow_def: WorkflowDefinition) -> List[NodeError]:
    """Validate a workflow definition and return a list of NodeError objects."""
    issues: List[NodeError] = []
    output_names: Set[str] = set()

    # Validate function definitions
    for name, func_def in workflow_def.functions.items():
        if func_def.type == "embedded" and not func_def.code:
            issues.append(NodeError(node_name=None, description=f"Embedded function '{name}' is missing 'code'"))
        elif func_def.type == "external" and (not func_def.module or not func_def.function):
            issues.append(NodeError(node_name=None, description=f"External function '{name}' is missing 'module' or 'function'"))

    # Validate nodes
    for name, node_def in workflow_def.nodes.items():
        if node_def.function and node_def.function not in workflow_def.functions:
            issues.append(NodeError(node_name=name, description=f"References undefined function '{node_def.function}'"))

        if node_def.output:
            if not node_def.output.isidentifier():
                issues.append(NodeError(node_name=name, description=f"Has invalid output name '{node_def.output}'"))
            elif node_def.output in output_names:
                issues.append(NodeError(node_name=name, description=f"Has duplicate output name '{node_def.output}'"))
            output_names.add(node_def.output)

        if node_def.sub_workflow:
            sub_issues = validate_workflow_structure(node_def.sub_workflow, workflow_def.nodes)
            issues.extend(
                NodeError(node_name=f"{name}/{issue.node_name}" if issue.node_name else name, description=issue.description)
                for issue in sub_issues
            )

        if node_def.llm_config:
            llm = node_def.llm_config
            if not llm.model:
                issues.append(NodeError(node_name=name, description="Missing 'model' in llm_config"))
            if not llm.prompt_template and not llm.prompt_file:
                issues.append(NodeError(node_name=name, description="Missing 'prompt_template' or 'prompt_file' in llm_config"))
            if llm.temperature < 0 or llm.temperature > 1:
                issues.append(NodeError(node_name=name, description=f"Has invalid temperature: {llm.temperature}"))

        if node_def.template_config:
            template = node_def.template_config
            if not template.template and not template.template_file:
                issues.append(NodeError(node_name=name, description="Missing 'template' or 'template_file' in template_config"))

    # Validate main workflow structure
    issues.extend(validate_workflow_structure(workflow_def.workflow, workflow_def.nodes, is_main=True))
    issues.extend(check_circular_transitions(workflow_def))

    # Build the unified graph for main workflow and sub-workflows
    successors = defaultdict(list)
    predecessors = defaultdict(list)
    all_nodes = set(workflow_def.nodes.keys())

    # Add main workflow transitions
    for trans in workflow_def.workflow.transitions:
        from_node = trans.from_node
        to_nodes = [trans.to_node] if isinstance(trans.to_node, str) else [tn if isinstance(tn, str) else tn.to_node for tn in trans.to_node]
        for to_node in to_nodes:
            successors[from_node].append(to_node)
            predecessors[to_node].append(from_node)
            all_nodes.add(to_node)

    # Add sub-workflow transitions with namespaced node names
    for parent_name, node_def in workflow_def.nodes.items():
        if node_def.sub_workflow:
            for trans in node_def.sub_workflow.transitions:
                from_node = f"{parent_name}/{trans.from_node}"
                to_nodes = [trans.to_node] if isinstance(trans.to_node, str) else [tn if isinstance(tn, str) else tn.to_node for tn in trans.to_node]
                namespaced_to_nodes = [f"{parent_name}/{to_node}" for to_node in to_nodes]
                all_nodes.add(from_node)
                all_nodes.update(namespaced_to_nodes)
                successors[from_node].extend(namespaced_to_nodes)
                for to_node in namespaced_to_nodes:
                    predecessors[to_node].append(from_node)

    # Define function to get ancestors, handling cycles with a visited set
    def get_ancestors(node: str, visited: Set[str] = None) -> Set[str]:
        if visited is None:
            visited = set()
        if node in visited or node not in all_nodes:
            return set()
        visited.add(node)
        ancestors = set(predecessors[node])
        for pred in predecessors[node]:
            ancestors.update(get_ancestors(pred, visited.copy()))
        return ancestors

    # Create output-to-node mapping, including sub-workflow nodes
    output_to_node = {}
    for node_name, node_def in workflow_def.nodes.items():
        if node_def.output:
            output_to_node[node_def.output] = node_name
        if node_def.sub_workflow:
            for sub_node_name, sub_node_def in workflow_def.nodes.items():
                if sub_node_def.output:
                    output_to_node[sub_node_def.output] = f"{node_name}/{sub_node_name}"

    # Check each node's inputs against ancestors' outputs, including sub-workflows
    for node_name, node_def in workflow_def.nodes.items():
        required_inputs = set()
        full_node_name = node_name

        # Handle inputs_mapping
        if node_def.inputs_mapping:
            for input_name, mapping in node_def.inputs_mapping.items():
                if mapping.startswith("lambda ctx:"):
                    try:
                        # Basic syntax check for lambda
                        compile(mapping, "<string>", "eval")
                    except SyntaxError:
                        issues.append(NodeError(
                            node_name=node_name,
                            description=f"Invalid lambda expression in inputs_mapping for '{input_name}': {mapping}"
                        ))
                elif not mapping.isidentifier():
                    issues.append(NodeError(
                        node_name=node_name,
                        description=f"Invalid context key in inputs_mapping for '{input_name}': {mapping}"
                    ))

        if node_def.function:
            maybe_func_def = workflow_def.functions.get(node_def.function)
            if maybe_func_def is None:
                issues.append(NodeError(
                    node_name=node_name,
                    description=f"Function '{node_def.function}' not found in workflow functions"
                ))
            else:
                func_def = maybe_func_def
                if func_def.type == "embedded" and func_def.code:
                    try:
                        params = get_function_params(func_def.code, node_def.function)
                        required_inputs = set(params)
                    except ValueError as e:
                        issues.append(NodeError(node_name=node_name, description=f"Failed to parse function '{node_def.function}': {e}"))
        elif node_def.llm_config:
            prompt_template = node_def.llm_config.prompt_template or ""
            input_vars = set(re.findall(r"{{\s*([^}]+?)\s*}}", prompt_template))
            cleaned_inputs = set()
            for var in input_vars:
                base_var = re.split(r"\s*[\+\-\*/]\s*", var.strip())[0].strip()
                if base_var.isidentifier():
                    cleaned_inputs.add(base_var)
            required_inputs = cleaned_inputs
        elif node_def.template_config:
            template = node_def.template_config.template or ""
            input_vars = set(re.findall(r"{{\s*([^}]+?)\s*}}", template))
            cleaned_inputs = set()
            for var in input_vars:
                base_var = re.split(r"\s*[\+\-\*/]\s*", var.strip())[0].strip()
                if base_var.isidentifier():
                    cleaned_inputs.add(base_var)
            required_inputs = cleaned_inputs
        elif node_def.sub_workflow:
            for sub_node_name, sub_node_def in workflow_def.nodes.items():
                full_node_name = f"{node_name}/{sub_node_name}"
                if sub_node_def.function:
                    maybe_func_def = workflow_def.functions.get(sub_node_def.function)
                    if maybe_func_def is None:
                        issues.append(NodeError(
                            node_name=full_node_name,
                            description=f"Function '{sub_node_def.function}' not found in workflow functions"
                        ))
                    else:
                        func_def = maybe_func_def
                        if func_def.type == "embedded" and func_def.code:
                            try:
                                params = get_function_params(func_def.code, sub_node_def.function)
                                required_inputs = set(params)
                            except ValueError as e:
                                issues.append(NodeError(
                                    node_name=full_node_name,
                                    description=f"Failed to parse function '{sub_node_def.function}': {e}"
                                ))
                elif sub_node_def.llm_config:
                    prompt_template = sub_node_def.llm_config.prompt_template or ""
                    input_vars = set(re.findall(r"{{\s*([^}]+?)\s*}}", prompt_template))
                    cleaned_inputs = set()
                    for var in input_vars:
                        base_var = re.split(r"\s*[\+\-\*/]\s*", var.strip())[0].strip()
                        if base_var.isidentifier():
                            cleaned_inputs.add(base_var)
                    required_inputs = cleaned_inputs
                elif sub_node_def.template_config:
                    template = sub_node_def.template_config.template or ""
                    input_vars = set(re.findall(r"{{\s*([^}]+?)\s*}}", template))
                    cleaned_inputs = set()
                    for var in input_vars:
                        base_var = re.split(r"\s*[\+\-\*/]\s*", var.strip())[0].strip()
                        if base_var.isidentifier():
                            cleaned_inputs.add(base_var)
                    required_inputs = cleaned_inputs

                if required_inputs:
                    ancestors = get_ancestors(full_node_name)
                    for input_name in required_inputs:
                        # Check if input is mapped
                        if node_def.inputs_mapping and input_name in node_def.inputs_mapping:
                            mapping = node_def.inputs_mapping[input_name]
                            if not mapping.startswith("lambda ctx:") and mapping in output_to_node:
                                producer_node = output_to_node.get(mapping)
                                if producer_node not in ancestors:
                                    issues.append(NodeError(
                                        node_name=full_node_name,
                                        description=f"inputs_mapping for '{input_name}' maps to '{mapping}', but it is not produced by an ancestor"
                                    ))
                            continue
                        producer_node = output_to_node.get(input_name)
                        if producer_node is None or producer_node not in ancestors:
                            issues.append(NodeError(
                                node_name=full_node_name,
                                description=f"Requires input '{input_name}', but it is not produced by any ancestor"
                            ))
            continue

        if not required_inputs:
            continue

        ancestors = get_ancestors(full_node_name)
        for input_name in required_inputs:
            # Check if input is mapped
            if node_def.inputs_mapping and input_name in node_def.inputs_mapping:
                mapping = node_def.inputs_mapping[input_name]
                if not mapping.startswith("lambda ctx:") and mapping in output_to_node:
                    producer_node = output_to_node.get(mapping)
                    if producer_node not in ancestors:
                        issues.append(NodeError(
                            node_name=full_node_name,
                            description=f"inputs_mapping for '{input_name}' maps to '{mapping}', but it is not produced by an ancestor"
                        ))
                continue
            producer_node = output_to_node.get(input_name)
            if producer_node is None or producer_node not in ancestors:
                issues.append(NodeError(
                    node_name=full_node_name,
                    description=f"Requires input '{input_name}', but it is not produced by any ancestor"
                ))

    # Validate observers
    for observer in workflow_def.observers:
        if observer not in workflow_def.functions:
            issues.append(NodeError(node_name=None, description=f"Observer '{observer}' references undefined function"))

    # Validate convergence nodes
    for conv_node in workflow_def.workflow.convergence_nodes:
        if conv_node not in workflow_def.nodes:
            issues.append(NodeError(node_name=conv_node, description="Convergence node is not defined in nodes"))
        # Check if the convergence node has multiple incoming transitions
        incoming = [t for t in workflow_def.workflow.transitions if
                    (isinstance(t.to_node, str) and t.to_node == conv_node) or
                    (isinstance(t.to_node, list) and any(isinstance(tn, str) and tn == conv_node or
                                                        isinstance(tn, BranchCondition) and tn.to_node == conv_node
                                                        for tn in t.to_node))]
        if len(incoming) < 2:
            issues.append(NodeError(node_name=conv_node, description="Convergence node has fewer than 2 incoming transitions"))

    return issues


def validate_workflow_structure(structure: WorkflowStructure, nodes: Dict[str, NodeDefinition],
                              is_main: bool = False) -> List[NodeError]:
    """Validate a WorkflowStructure for consistency, including branch and converge support."""
    issues: List[NodeError] = []

    if is_main and not structure.start:
        issues.append(NodeError(node_name=None, description="Main workflow is missing a start node"))
    elif structure.start and structure.start not in nodes:
        issues.append(NodeError(node_name=structure.start, description="Start node is not defined in nodes"))

    for trans in structure.transitions:
        if trans.from_node not in nodes:
            issues.append(NodeError(node_name=trans.from_node, description="Transition from undefined node"))

        to_nodes: List[Union[str, BranchCondition]] = [trans.to_node] if isinstance(trans.to_node, str) else trans.to_node
        for to_node in to_nodes:
            target_node = to_node if isinstance(to_node, str) else to_node.to_node
            if target_node not in nodes:
                issues.append(NodeError(node_name=target_node, description=f"Transition to undefined node from '{trans.from_node}'"))
            if isinstance(to_node, BranchCondition) and to_node.condition:
                try:
                    compile(to_node.condition, "<string>", "eval")
                except SyntaxError:
                    issues.append(NodeError(node_name=trans.from_node, description=f"Invalid branch condition syntax: {to_node.condition}"))

        if trans.condition and isinstance(trans.to_node, str):
            try:
                compile(trans.condition, "<string>", "eval")
            except SyntaxError:
                issues.append(NodeError(node_name=trans.from_node, description=f"Invalid condition syntax in transition: {trans.condition}"))

    return issues


def check_circular_transitions(workflow_def: WorkflowDefinition) -> List[NodeError]:
    """Detect circular transitions in the workflow using DFS, allowing cycles with conditions."""
    issues: List[NodeError] = []

    def dfs(node: str, visited: Set[str], path: Set[str], transitions: List[TransitionDefinition], path_transitions: List[TransitionDefinition]) -> None:
        if node in path:
            cycle_nodes = list(path)[list(path).index(node):] + [node]
            cycle = " -> ".join(cycle_nodes)
            cycle_transitions = [
                t for t in path_transitions
                if t.from_node in cycle_nodes and
                   ((isinstance(t.to_node, str) and t.to_node in cycle_nodes) or
                    (isinstance(t.to_node, list) and any((isinstance(tn, str) and tn in cycle_nodes) or
                                                        (isinstance(tn, BranchCondition) and tn.to_node in cycle_nodes)
                                                        for tn in t.to_node)))
            ]
            # Check if all transitions in the cycle are unconditional
            if all((t.condition is None if isinstance(t.to_node, str) else
                    all(isinstance(tn, str) or (isinstance(tn, BranchCondition) and tn.condition is None) for tn in t.to_node))
                   for t in cycle_transitions):
                issues.append(NodeError(node_name=None, description=f"Unconditional circular transition detected: {cycle}"))
            return
        if node in visited or node not in workflow_def.nodes:
            return

        visited.add(node)
        path.add(node)

        for trans in transitions:
            if trans.from_node == node:
                path_transitions.append(trans)
                to_nodes = [trans.to_node] if isinstance(trans.to_node, str) else trans.to_node
                for to_node in to_nodes:
                    next_node = to_node if isinstance(to_node, str) else to_node.to_node
                    dfs(next_node, visited, path, transitions, path_transitions)
                path_transitions.pop()

        path.remove(node)

    if workflow_def.workflow.start:
        dfs(workflow_def.workflow.start, set(), set(), workflow_def.workflow.transitions, [])

    for node_name, node_def in workflow_def.nodes.items():
        if node_def.sub_workflow and node_def.sub_workflow.start:
            dfs(node_def.sub_workflow.start, set(), set(), node_def.sub_workflow.transitions, [])

    return issues


def main():
    """Build a sample workflow with branch, converge, template node, and input mapping using WorkflowManager and validate it."""
    manager = WorkflowManager()

    # Define functions
    manager.add_function(
        name="say_hello",
        type_="embedded",
        code="def say_hello():\n    return 'Hello, World!'"
    )
    manager.add_function(
        name="say_goodbye",
        type_="embedded",
        code="def say_goodbye():\n    return 'Goodbye, World!'"
    )
    manager.add_function(
        name="check_condition",
        type_="embedded",
        code="def check_condition(text: str):\n    return 'yes' if 'Hello' in text else 'no'"
    )
    manager.add_function(
        name="finalize",
        type_="embedded",
        code="def finalize(text: str):\n    return 'Done'"
    )

    # Add nodes for main workflow
    manager.add_node(name="start", function="say_hello", output="text")
    manager.add_node(name="check", function="check_condition", output="result",
                     inputs_mapping={"text": "text"})  # Mapping input to context key
    manager.add_node(name="goodbye", function="say_goodbye", output="farewell")
    manager.add_node(name="finalize", function="finalize", output="status",
                     inputs_mapping={"text": "lambda ctx: ctx['farewell'] if ctx['result'] == 'no' else ctx['ai_result']"})
    manager.add_node(name="outro", function="non_existent")  # Intentional: undefined function

    # Add LLM node with valid temperature
    manager.add_node(
        name="ai_node",
        llm_config={
            "model": "gpt-3.5-turbo",
            "prompt_template": "{{text}}",
            "temperature": 0.7
        },
        output="ai_result"
    )

    # Add template node
    manager.add_node(
        name="template_node",
        template_config={
            "template": "Response: {{text}} - {{result}}"
        },
        output="template_output"
    )

    # Add nodes and sub-workflow
    manager.add_node(name="nested_start", function="say_hello", output="nested_text")
    manager.add_node(name="nested_end", function="say_goodbye")
    sub_workflow = WorkflowStructure(start="nested_start")
    sub_workflow.transitions.append(TransitionDefinition(from_node="nested_start", to_node="nested_end"))
    manager.add_node(name="nested", sub_workflow=sub_workflow)

    # Configure main workflow with branch and converge
    manager.set_start_node("start")
    manager.add_transition(from_node="start", to_node="check")
    manager.add_transition(
        from_node="check",
        to_node=[
            BranchCondition(to_node="ai_node", condition="ctx['result'] == 'yes'"),
            BranchCondition(to_node="goodbye", condition="ctx['result'] == 'no'")
        ]
    )
    manager.add_transition(from_node="ai_node", to_node="finalize")
    manager.add_transition(from_node="goodbye", to_node="finalize")
    manager.add_transition(from_node="finalize", to_node="template_node")
    manager.add_transition(from_node="start", to_node="outro")
    manager.add_transition(from_node="outro", to_node="start")  # Intentional: circular
    manager.add_convergence_node("finalize")

    # Add observer with error handling
    try:
        manager.add_observer("undefined_observer")  # Intentional: undefined observer
    except ValueError:
        pass  # Allow validation to proceed

    # Validate the constructed workflow
    workflow = manager.workflow
    issues = validate_workflow_definition(workflow)

    # Display results
    if issues:
        print("Issues found in workflow definition:")
        for issue in sorted(issues, key=lambda x: (x.node_name or '', x.description)):
            node_part = f"Node '{issue.node_name}'" if issue.node_name else "Workflow"
            print(f"- {node_part}: {issue.description}")
    else:
        print("No issues found in workflow definition.")


if __name__ == "__main__":
    main()