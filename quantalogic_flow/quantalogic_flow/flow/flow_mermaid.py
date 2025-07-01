import re
from typing import Dict, List, Set, Tuple

from quantalogic_flow.flow.flow_manager import WorkflowManager
from quantalogic_flow.flow.flow_manager_schema import BranchCondition, NodeDefinition, WorkflowDefinition


def parse_mermaid_flowchart(mermaid_text: str) -> dict:
    """
    Minimal parser for Mermaid flowchart syntax. Extracts nodes and edges.
    Returns a dict with 'nodes' and 'edges' keys.
    Handles basic syntax and ignores advanced features.
    """
    import re

    nodes = set()
    edges = []
    if not isinstance(mermaid_text, str) or not mermaid_text.strip():
        return {}
    lines = mermaid_text.strip().splitlines()
    for line in lines:
        line = line.strip()
        # Match edges: A --> B, optionally with labels
        edge_match = re.match(r"([A-Za-z0-9_\-]+)[\[(]?.*?[\])]?(?:\s*-->|\s*--\|.*?\|-->)\s*([A-Za-z0-9_\-]+)", line)
        if edge_match:
            src, dst = edge_match.groups()
            nodes.add(src)
            nodes.add(dst)
            edges.append((src, dst))
        # Match node definitions: A[Label], B((Label)), etc.
        node_match = re.match(r"([A-Za-z0-9_\-]+)\s*([\[(])", line)
        if node_match:
            nodes.add(node_match.group(1))
    return {"nodes": list(nodes), "edges": edges}


def get_node_label_and_type(
    node_name: str, node_def: NodeDefinition | None, has_conditions: bool
) -> Tuple[str, str, str]:
    """
    Generate a label, type identifier, and shape for a node based on its definition and transition context.

    Args:
        node_name: The name of the node.
        node_def: The NodeDefinition object from the workflow, or None if undefined.
        has_conditions: True if the node has outgoing transitions with conditions (branching).

    Returns:
        A tuple of (display label, type key for styling, shape identifier).
    """
    # Escape quotes for Mermaid compatibility
    escaped_name = node_name.replace('"', '\\"')
    shape = "diamond" if has_conditions else "rect"

    if not node_def:
        return f"{escaped_name} (unknown)", "unknown", shape

    # Base label starts with node name and type
    if node_def.function:
        label = f"{escaped_name} (function)"
        node_type = "function"
    elif node_def.llm_config:
        if node_def.llm_config.response_model:
            label = f"{escaped_name} (structured LLM)"
            node_type = "structured_llm"
        else:
            label = f"{escaped_name} (LLM)"
            node_type = "llm"
    elif node_def.template_config:
        label = f"{escaped_name} (template)"
        node_type = "template"
    elif node_def.sub_workflow:
        label = f"{escaped_name} (Sub-Workflow)"
        node_type = "sub_workflow"
    else:
        label = f"{escaped_name} (unknown)"
        node_type = "unknown"

    # Append inputs_mapping if present
    if node_def and node_def.inputs_mapping:
        mapping_str = ", ".join(f"{k}={v}" for k, v in node_def.inputs_mapping.items())
        # Truncate if too long for readability (e.g., > 30 chars)
        if len(mapping_str) > 30:
            mapping_str = mapping_str[:27] + "..."
        label += f"\\nInputs: {mapping_str}"

    return label, node_type, shape


def generate_mermaid_diagram(
    workflow_def: WorkflowDefinition,
    include_subgraphs: bool = False,
    title: str | None = None,
    include_legend: bool = True,
    diagram_type: str = "flowchart",
) -> str:
    """
    Generate a Mermaid diagram (flowchart or stateDiagram) from a WorkflowDefinition with pastel colors and optimal UX.

    Args:
        workflow_def: The workflow definition to visualize.
        include_subgraphs: If True, nests sub-workflows in Mermaid subgraphs (flowchart only).
        title: Optional title for the diagram.
        include_legend: If True, adds a comment-based legend explaining node types and shapes.
        diagram_type: Type of diagram to generate: "flowchart" (default) or "stateDiagram".

    Returns:
        A string containing the Mermaid syntax for the diagram.

    Raises:
        ValueError: If node names contain invalid Mermaid characters or diagram_type is invalid.
    """
    if diagram_type not in ("flowchart", "stateDiagram"):
        raise ValueError(f"Invalid diagram_type '{diagram_type}'; must be 'flowchart' or 'stateDiagram'")

    # Professional pastel color scheme with high contrast for text readability
    # Color Palette Guidelines:
    # - Light backgrounds (#E3F2FD family) for excellent readability
    # - Dark stroke and text colors for strong contrast
    # - Each node type has distinct colors following Material Design principles
    # - Colors are accessible and print-friendly
    node_styles: Dict[str, str] = {
        "function": "fill:#E3F2FD,stroke:#1976D2,stroke-width:2px,color:#1565C0",  # Light Blue with dark blue text
        "structured_llm": "fill:#E8F5E8,stroke:#388E3C,stroke-width:2px,color:#2E7D32",  # Light Green with dark green text
        "llm": "fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px,color:#6A1B9A",  # Light Purple with dark purple text
        "template": "fill:#FFF0F5,stroke:#C2185B,stroke-width:2px,color:#AD1457",  # Light Pink with dark pink text
        "sub_workflow": "fill:#FFF3E0,stroke:#F57C00,stroke-width:2px,color:#EF6C00",  # Light Orange with dark orange text
        "unknown": "fill:#F5F5F5,stroke:#616161,stroke-width:2px,color:#424242",  # Light Grey with dark grey text
    }

    # Shape mappings for flowchart syntax
    shape_syntax: Dict[str, Tuple[str, str]] = {
        "rect": ("[", "]"),  # Rectangle for standard nodes
        "diamond": ("{{", "}}"),  # Diamond for decision points (branching)
    }

    # Validate node names for Mermaid compatibility (alphanumeric, underscore, hyphen)
    invalid_chars = r"[^a-zA-Z0-9_-]"
    # Collect all nodes from the workflow structure and the nodes dict
    all_nodes: Set[str] = set()
    # Add all nodes from the workflow structure (dict keys)
    if hasattr(workflow_def.workflow, "nodes"):
        if isinstance(workflow_def.workflow.nodes, dict):
            all_nodes.update(workflow_def.workflow.nodes.keys())
        elif isinstance(workflow_def.workflow.nodes, list):
            all_nodes.update(workflow_def.workflow.nodes)
    # Add all nodes from the nodes dict (for legacy/test compatibility)
    if hasattr(workflow_def, "nodes") and isinstance(workflow_def.nodes, dict):
        all_nodes.update(workflow_def.nodes.keys())
    # Add all nodes from transitions
    all_transitions = []
    if hasattr(workflow_def.workflow, "transitions") and workflow_def.workflow.transitions:
        all_transitions.extend(workflow_def.workflow.transitions)
    if hasattr(workflow_def, "transitions") and workflow_def.transitions:
        all_transitions.extend(workflow_def.transitions)

    for trans in all_transitions:
        all_nodes.add(trans.from_node)
        if isinstance(trans.to_node, str):
            all_nodes.add(trans.to_node)
        else:
            for tn in trans.to_node:
                target = tn if isinstance(tn, str) else tn.to_node
                all_nodes.add(target)
    # Add all convergence nodes
    for conv_node in getattr(workflow_def.workflow, "convergence_nodes", []):
        all_nodes.add(conv_node)
    # Validate node names for Mermaid compatibility
    for node in all_nodes:
        if re.search(invalid_chars, node):
            raise ValueError(f"Invalid node name '{node}' for Mermaid")

    # Determine nodes with conditional transitions (branching)
    conditional_nodes: Set[str] = set()
    for trans in all_transitions:
        if (trans.condition and isinstance(trans.to_node, str)) or (
            isinstance(trans.to_node, list)
            and any(isinstance(tn, BranchCondition) and tn.condition for tn in trans.to_node)
        ):
            conditional_nodes.add(trans.from_node)

    # Identify convergence nodes
    convergence_nodes: Set[str] = set(workflow_def.workflow.convergence_nodes)

    # Shared node definitions and types
    node_types: Dict[str, str] = {}
    node_shapes: Dict[str, str] = {}  # Only used for flowchart

    # Assemble the Mermaid syntax
    mermaid_code = "```mermaid\n"
    if diagram_type == "flowchart":
        mermaid_code += "flowchart TD\n"  # Top-down layout (use 'flowchart' for compatibility)
    else:  # stateDiagram
        mermaid_code += "stateDiagram-v2\n"

    if title:
        mermaid_code += f"    %% Diagram: {title}\n"

    # Optional legend for UX
    if include_legend:
        mermaid_code += "    %% Legend:\n"
        if diagram_type == "flowchart":
            mermaid_code += "    %% - Rectangle: Process Step or Convergence Point\n"
            mermaid_code += "    %% - Diamond: Decision Point (Branching)\n"
        mermaid_code += "    %% - Colors: Blue (Function), Green (Structured LLM), Purple (LLM), Pink (Template), Orange (Sub-Workflow), Grey (Unknown)\n"
        mermaid_code += "    %% - Dashed Border: Convergence Node\n"

    if diagram_type == "flowchart":
        # Flowchart-specific: Generate node definitions with shapes
        node_defs: List[str] = []
        for node in sorted(all_nodes):
            # Try to get node definition from workflow_def.nodes, fallback to workflow_def.workflow.nodes
            node_def_flow = None
            if hasattr(workflow_def, "nodes") and isinstance(workflow_def.nodes, dict):
                node_def_flow = workflow_def.nodes.get(node)
            if not node_def_flow and hasattr(workflow_def.workflow, "nodes"):
                if isinstance(workflow_def.workflow.nodes, dict):
                    node_def_flow = workflow_def.workflow.nodes.get(node)
            has_conditions = node in conditional_nodes
            label, node_type, shape = get_node_label_and_type(node, node_def_flow, has_conditions)
            start_shape, end_shape = shape_syntax[shape]
            node_defs.append(f'{node}{start_shape}"{label}"{end_shape}')
            node_types[node] = node_type
            node_shapes[node] = shape

        # Add node definitions
        for node_def_str in node_defs:  # Already sorted
            mermaid_code += f"    {node_def_str}\n"

        # Generate arrows for transitions (ensure all are output, including conditions)
        transitions = []
        # Try to get transitions from workflow_def.workflow first, then fallback to workflow_def
        if hasattr(workflow_def.workflow, "transitions") and workflow_def.workflow.transitions:
            transitions = workflow_def.workflow.transitions
        elif hasattr(workflow_def, "transitions") and workflow_def.transitions:
            transitions = workflow_def.transitions
        for trans in transitions:
            from_node = trans.from_node
            if isinstance(trans.to_node, str):
                to_node = trans.to_node
                condition = trans.condition
                if condition:
                    # Try to extract a user-friendly label from the condition string
                    # e.g., lambda ctx: ctx.get('use_branch1', False) -> use_branch1
                    label = None
                    match = re.search(r"ctx\\.get\(['\"]([a-zA-Z0-9_]+)['\"]", condition)
                    if match:
                        label = match.group(1)
                    if not label:
                        match = re.search(r"['\"]([a-zA-Z0-9_]+)['\"]", condition)
                        if match:
                            label = match.group(1)
                    cond = (
                        label
                        if label
                        else (condition.replace('"', '\\"')[:30] + ("..." if len(condition) > 30 else ""))
                    )
                    mermaid_code += f'    {from_node} -->|"{cond}"| {to_node}\n'
                else:
                    mermaid_code += f"    {from_node} --> {to_node}\n"
            else:
                for tn in trans.to_node:
                    if isinstance(tn, str):
                        mermaid_code += f"    {from_node} --> {tn}\n"
                    else:  # BranchCondition
                        to_node = tn.to_node
                        condition = tn.condition
                        if condition:
                            label = None
                            match = re.search(r"ctx\\.get\(['\"]([a-zA-Z0-9_]+)['\"]", condition)
                            if match:
                                label = match.group(1)
                            if not label:
                                match = re.search(r"['\"]([a-zA-Z0-9_]+)['\"]", condition)
                                if match:
                                    label = match.group(1)
                            cond = (
                                label
                                if label
                                else (condition.replace('"', '\\"')[:30] + ("..." if len(condition) > 30 else ""))
                            )
                            mermaid_code += f'    {from_node} -->|"{cond}"| {to_node}\n'
                        else:
                            mermaid_code += f"    {from_node} --> {to_node}\n"

        # Add loop visualization for flowchart
        if hasattr(workflow_def.workflow, 'loops') and workflow_def.workflow.loops:
            for i, loop_def in enumerate(workflow_def.workflow.loops):
                if loop_def.nodes:
                    # Create a subgraph for the loop
                    mermaid_code += f"    subgraph Loop{i+1}[Loop {i+1}]\n"
                    for node in loop_def.nodes:
                        mermaid_code += f"        {node}\n"
                    mermaid_code += "    end\n"
                    # Add loop back edge
                    last_node = loop_def.nodes[-1]
                    first_node = loop_def.nodes[0]
                    mermaid_code += f'    {last_node} -->|"loop"| {first_node}\n'
                    mermaid_code += f'    {last_node} -->|"exit"| {loop_def.exit_node}\n'

        # Add styles for node types
        for node, node_type in node_types.items():
            if node_type in node_styles:
                style = node_styles[node_type]
                # Add dashed stroke for convergence nodes
                if node in convergence_nodes:
                    style += ",stroke-dasharray:5 5"
                mermaid_code += f"    style {node} {style}\n"

        # Highlight the start node with a thicker border
        if workflow_def.workflow.start and workflow_def.workflow.start in node_types:
            mermaid_code += f"    style {workflow_def.workflow.start} stroke-width:4px\n"

        # Optional: Subgraphs for sub-workflows
        if include_subgraphs:
            for node, node_def_entry in workflow_def.nodes.items():
                if node_def_entry and node_def_entry.sub_workflow:
                    mermaid_code += f"    subgraph {node}_sub[Sub-Workflow: {node}]\n"
                    sub_nodes: Set[str] = (
                        {node_def_entry.sub_workflow.start} if node_def_entry.sub_workflow.start else set()
                    )
                    for trans in node_def_entry.sub_workflow.transitions:
                        sub_nodes.add(trans.from_node)
                        if isinstance(trans.to_node, str):
                            sub_nodes.add(trans.to_node)
                        else:
                            for tn in trans.to_node:
                                target = tn if isinstance(tn, str) else tn.to_node
                                sub_nodes.add(target)
                    for sub_node in sorted(sub_nodes):  # Sort for consistency
                        mermaid_code += f"        {sub_node}[[{sub_node}]]\n"
                    mermaid_code += "    end\n"

    else:  # stateDiagram
        # StateDiagram-specific: Define states
        for node in all_nodes:
            node_def_state: NodeDefinition | None = workflow_def.nodes.get(node)
            has_conditions = node in conditional_nodes
            label, node_type, _ = get_node_label_and_type(node, node_def_state, has_conditions)  # Shape unused
            # Append (Convergence) to label for convergence nodes
            if node in convergence_nodes:
                label += " (Convergence)"
            mermaid_code += f'    state "{label}" as {node}\n'
            node_types[node] = node_type

        # Start state
        if workflow_def.workflow.start:
            mermaid_code += f"    [*] --> {workflow_def.workflow.start}\n"

        # Transitions
        for trans in workflow_def.workflow.transitions:
            from_node = trans.from_node
            if isinstance(trans.to_node, str):
                to_node = trans.to_node
                condition = trans.condition
                if condition:
                    cond = condition.replace('"', '\\"')[:30] + ("..." if len(condition) > 30 else "")
                    mermaid_code += f"    {from_node} --> {to_node} : {cond}\n"
                else:
                    mermaid_code += f"    {from_node} --> {to_node}\n"
            else:
                for tn in trans.to_node:
                    if isinstance(tn, str):
                        # Parallel transition approximated with a note
                        mermaid_code += f"    {from_node} --> {tn} : parallel\n"
                    else:  # BranchCondition
                        to_node = tn.to_node
                        condition = tn.condition
                        if condition:
                            cond = condition.replace('"', '\\"')[:30] + ("..." if len(condition) > 30 else "")
                            mermaid_code += f"    {from_node} --> {to_node} : {cond}\n"
                        else:
                            mermaid_code += f"    {from_node} --> {to_node}\n"

        # Add loop visualization for stateDiagram
        if hasattr(workflow_def.workflow, 'loops') and workflow_def.workflow.loops:
            for i, loop_def in enumerate(workflow_def.workflow.loops):
                if loop_def.nodes:
                    # Add note about loop structure
                    first_node = loop_def.nodes[0]
                    last_node = loop_def.nodes[-1]
                    mermaid_code += f"    note right of {first_node} : Loop {i+1}\n"
                    mermaid_code += f"    {last_node} --> {first_node} : loop condition\n"
                    mermaid_code += f"    {last_node} --> {loop_def.exit_node} : exit condition\n"

        # Add styles for node types
        for node, node_type in node_types.items():
            if node_type in node_styles:
                style = node_styles[node_type]
                # Add dashed stroke for convergence nodes
                if node in convergence_nodes:
                    style += ",stroke-dasharray:5 5"
                mermaid_code += f"    style {node} {style}\n"

    mermaid_code += "```\n"
    return mermaid_code


def main() -> None:
    """Create a complex workflow with branch, converge, template node, and input mapping, and print its Mermaid diagram."""
    manager = WorkflowManager()

    # Add functions
    manager.add_function(name="say_hello", type_="embedded", code="def say_hello():\n    return 'Hello, World!'")
    manager.add_function(
        name="check_condition",
        type_="embedded",
        code="def check_condition(text: str):\n    return 'yes' if 'Hello' in text else 'no'",
    )
    manager.add_function(name="say_goodbye", type_="embedded", code="def say_goodbye():\n    return 'Goodbye, World!'")
    manager.add_function(name="finalize", type_="embedded", code="def finalize(text: str):\n    return 'Done'")

    # Add nodes
    manager.add_node(name="start", function="say_hello", output="text")
    manager.add_node(name="check", function="check_condition", output="result", inputs_mapping={"text": "text"})
    manager.add_node(name="goodbye", function="say_goodbye", output="farewell")
    manager.add_node(
        name="finalize",
        function="finalize",
        output="status",
        inputs_mapping={"text": "lambda ctx: ctx['farewell'] if ctx['result'] == 'no' else ctx['ai_result']"},
    )

    # Add LLM node
    manager.add_node(
        name="ai_node",
        llm_config={"model": "gpt-3.5-turbo", "prompt_template": "{{text}}", "temperature": 0.7},
        output="ai_result",
    )

    # Add template node
    manager.add_node(
        name="template_node",
        template_config={"template": "Response: {{text}} - {{result}}"},
        output="template_output",
        inputs_mapping={"text": "text", "result": "result"},
    )

    # Define workflow structure with branch and converge
    manager.set_start_node("start")
    manager.add_transition(from_node="start", to_node="check")
    manager.add_transition(
        from_node="check",
        to_node=[
            BranchCondition(to_node="ai_node", condition="ctx['result'] == 'yes'"),
            BranchCondition(to_node="goodbye", condition="ctx['result'] == 'no'"),
        ],
    )
    manager.add_transition(from_node="ai_node", to_node="finalize")
    manager.add_transition(from_node="goodbye", to_node="finalize")
    manager.add_transition(from_node="finalize", to_node="template_node")
    manager.add_convergence_node("finalize")

    # Generate and print both diagrams
    workflow_def = manager.workflow
    print("Flowchart (default):")
    print(
        generate_mermaid_diagram(
            workflow_def, include_subgraphs=False, title="Sample Workflow with Template and Mapping"
        )
    )
    print("\nState Diagram:")
    print(
        generate_mermaid_diagram(
            workflow_def, diagram_type="stateDiagram", title="Sample Workflow with Template and Mapping"
        )
    )


if __name__ == "__main__":
    main()
