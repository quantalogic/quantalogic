from typing import Dict, List, Set

from quantalogic.flow.flow_manager import WorkflowManager
from quantalogic.flow.flow_manager_schema import (
    FunctionDefinition,
    LLMConfig,
    NodeDefinition,
    TransitionDefinition,
    WorkflowDefinition,
    WorkflowStructure,
)
from pydantic import ValidationError


def validate_workflow_definition(workflow_def: WorkflowDefinition) -> List[str]:
    """Validate a workflow definition and return a list of issues found."""
    issues = []
    output_names: Set[str] = set()

    for name, func_def in workflow_def.functions.items():
        if func_def.type == "embedded" and not func_def.code:
            issues.append(f"Embedded function '{name}' is missing 'code'")
        elif func_def.type == "external" and (not func_def.module or not func_def.function):
            issues.append(f"External function '{name}' is missing 'module' or 'function'")

    for name, node_def in workflow_def.nodes.items():
        if node_def.function and node_def.function not in workflow_def.functions:
            issues.append(f"Node '{name}' references undefined function '{node_def.function}'")

        if node_def.output:
            if not node_def.output.isidentifier():
                issues.append(f"Node '{name}' has invalid output name '{node_def.output}'")
            elif node_def.output in output_names:
                issues.append(f"Node '{name}' has duplicate output name '{node_def.output}'")
            output_names.add(node_def.output)

        if node_def.sub_workflow:
            sub_issues = validate_workflow_structure(node_def.sub_workflow, workflow_def.nodes)
            issues.extend(f"Sub-workflow in node '{name}': {issue}" for issue in sub_issues)

        if node_def.llm_config:
            llm = node_def.llm_config
            if not llm.model:
                issues.append(f"LLM node '{name}' is missing 'model' in llm_config")
            if not llm.prompt_template:
                issues.append(f"LLM node '{name}' is missing 'prompt_template' in llm_config")
            if llm.temperature < 0 or llm.temperature > 1:
                issues.append(f"LLM node '{name}' has invalid temperature: {llm.temperature}")

    issues.extend(validate_workflow_structure(workflow_def.workflow, workflow_def.nodes, is_main=True))
    issues.extend(check_circular_transitions(workflow_def))

    for observer in workflow_def.observers:
        if observer not in workflow_def.functions:
            issues.append(f"Observer '{observer}' references undefined function")

    return issues


def validate_workflow_structure(structure: WorkflowStructure, nodes: Dict[str, NodeDefinition], 
                              is_main: bool = False) -> List[str]:
    """Validate a WorkflowStructure for consistency."""
    issues = []

    if is_main and not structure.start:
        issues.append("Main workflow is missing a start node")
    elif structure.start and structure.start not in nodes:
        issues.append(f"Start node '{structure.start}' is not defined in nodes")

    for trans in structure.transitions:
        if trans.from_node not in nodes:
            issues.append(f"Transition from undefined node '{trans.from_node}'")
        to_nodes = [trans.to_node] if isinstance(trans.to_node, str) else trans.to_node
        for to_node in to_nodes:
            if to_node not in nodes:
                issues.append(f"Transition to undefined node '{to_node}' from '{trans.from_node}'")
        if trans.condition:
            try:
                compile(trans.condition, "<string>", "eval")
            except SyntaxError:
                issues.append(f"Invalid condition syntax in transition from '{trans.from_node}': {trans.condition}")

    return issues


def check_circular_transitions(workflow_def: WorkflowDefinition) -> List[str]:
    """Detect circular transitions in the workflow using DFS."""
    issues = []

    def dfs(node: str, visited: Set[str], path: Set[str], transitions: List[TransitionDefinition]) -> None:
        if node in path:
            cycle = " -> ".join(list(path) + [node])
            issues.append(f"Circular transition detected: {cycle}")
            return
        if node in visited or node not in workflow_def.nodes:
            return

        visited.add(node)
        path.add(node)

        for trans in transitions:
            if trans.from_node == node:
                to_nodes = [trans.to_node] if isinstance(trans.to_node, str) else trans.to_node
                for next_node in to_nodes:
                    dfs(next_node, visited, path, transitions)

        path.remove(node)

    if workflow_def.workflow.start:
        dfs(workflow_def.workflow.start, set(), set(), workflow_def.workflow.transitions)

    for node_name, node_def in workflow_def.nodes.items():
        if node_def.sub_workflow and node_def.sub_workflow.start:
            dfs(node_def.sub_workflow.start, set(), set(), node_def.sub_workflow.transitions)

    return issues


def main():
    """Build a sample workflow using WorkflowManager and validate it."""
    manager = WorkflowManager()

    # Define functions
    manager.add_function(
        name="say_hello",
        type_="embedded",
        code="def say_hello():\n    return 'Hello, World!'"
    )
    manager.add_function(
        name="say_goodbye",
        type_="external",
        module="external_module",
        function="goodbye_func"
    )

    # Add nodes for main workflow
    manager.add_node(name="start", function="say_hello", output="result")
    manager.add_node(name="outro", function="non_existent")  # Intentional: undefined function
    
    # Add LLM node with valid temperature
    manager.add_node(
        name="ai_node",
        llm_config={
            "model": "gpt-3.5-turbo", 
            "prompt_template": "{{input}}", 
            "temperature": 0.7
        }
    )

    # Add nodes and sub-workflow
    manager.add_node(name="nested_start", function="say_hello")
    manager.add_node(name="nested_end", function="say_goodbye")
    sub_workflow = WorkflowStructure(start="nested_start")
    sub_workflow.transitions.extend([
        TransitionDefinition(from_node="nested_start", to_node="nested_end"),
        TransitionDefinition(from_node="nested_end", to_node="nested_start")  # Intentional: circular
    ])
    manager.add_node(name="nested", sub_workflow=sub_workflow)

    # Configure main workflow
    manager.set_start_node("start")
    manager.add_transition(from_node="start", to_node="outro")
    manager.add_transition(from_node="outro", to_node="start")  # Intentional: circular
    manager.add_transition(from_node="start", to_node="missing_node")  # Intentional: undefined node

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
        for issue in sorted(issues):
            print(f"- {issue}")
    else:
        print("No issues found in workflow definition.")


if __name__ == "__main__":
    main()