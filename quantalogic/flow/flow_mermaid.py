import re
from typing import Dict, List, Optional, Set, Tuple

from quantalogic.flow.flow_manager import WorkflowManager
from quantalogic.flow.flow_manager_schema import NodeDefinition, WorkflowDefinition


def get_node_label_and_type(node_name: str, node_def: Optional[NodeDefinition], has_conditions: bool) -> Tuple[str, str, str]:
    """
    Generate a label, type identifier, and shape for a node based on its definition and transition context.

    Args:
        node_name: The name of the node.
        node_def: The NodeDefinition object from the workflow, or None if undefined.
        has_conditions: True if the node has outgoing transitions with conditions.

    Returns:
        A tuple of (display label, type key for styling, shape identifier).
    """
    # No truncation unless necessary, escape quotes for safety
    escaped_name = node_name.replace('"', '\\"')

    # Use diamond shape for nodes with conditional transitions, rectangle otherwise
    shape = "diamond" if has_conditions else "rect"

    if not node_def:
        return f"{escaped_name} (unknown)", "unknown", shape
    
    if node_def.function:
        return f"{escaped_name} (function)", "function", shape
    elif node_def.llm_config:
        if node_def.llm_config.response_model:
            return f"{escaped_name} (structured LLM)", "structured_llm", shape
        return f"{escaped_name} (LLM)", "llm", shape
    elif node_def.sub_workflow:
        return f"{escaped_name} (Sub-Workflow)", "sub_workflow", shape
    return f"{escaped_name} (unknown)", "unknown", shape


def generate_mermaid_diagram(
    workflow_def: WorkflowDefinition,
    include_subgraphs: bool = False,
    title: Optional[str] = None,
    include_legend: bool = True,
    diagram_type: str = "flowchart"
) -> str:
    """
    Generate a Mermaid diagram (flowchart or stateDiagram) from a WorkflowDefinition with pastel colors and optimal UX.

    Args:
        workflow_def: The workflow definition to visualize.
        include_subgraphs: If True, nests sub-workflows in Mermaid subgraphs (flowchart only).
        title: Optional title for the diagram.
        include_legend: If True, adds a comment-based legend explaining node types.
        diagram_type: Type of diagram to generate: "flowchart" (default) or "stateDiagram".

    Returns:
        A string containing the Mermaid syntax for the diagram.

    Raises:
        ValueError: If node names contain invalid Mermaid characters or diagram_type is invalid.
    """
    if diagram_type not in ("flowchart", "stateDiagram"):
        raise ValueError(f"Invalid diagram_type '{diagram_type}'; must be 'flowchart' or 'stateDiagram'")

    # Pastel color scheme for a soft, user-friendly look
    node_styles: Dict[str, str] = {
        "function": "fill:#90CAF9,stroke:#42A5F5,stroke-width:2px",           # Pastel Blue
        "structured_llm": "fill:#A5D6A7,stroke:#66BB6A,stroke-width:2px",    # Pastel Green
        "llm": "fill:#CE93D8,stroke:#AB47BC,stroke-width:2px",               # Pastel Purple
        "sub_workflow": "fill:#FFCCBC,stroke:#FF7043,stroke-width:2px",      # Pastel Orange
        "unknown": "fill:#CFD8DC,stroke:#B0BEC5,stroke-width:2px"            # Pastel Grey
    }

    # Shape mappings for flowchart syntax
    shape_syntax: Dict[str, Tuple[str, str]] = {
        "rect": ("[", "]"),      # Rectangle for standard nodes
        "diamond": ("{{", "}}")   # Diamond for decision points
    }

    # Validate node names for Mermaid compatibility (alphanumeric, underscore, hyphen)
    invalid_chars = r'[^a-zA-Z0-9_-]'
    all_nodes: Set[str] = set()
    if workflow_def.workflow.start:
        if re.search(invalid_chars, workflow_def.workflow.start):
            raise ValueError(f"Invalid node name '{workflow_def.workflow.start}' for Mermaid")
        all_nodes.add(workflow_def.workflow.start)
    for trans in workflow_def.workflow.transitions:
        if re.search(invalid_chars, trans.from_node):
            raise ValueError(f"Invalid node name '{trans.from_node}' for Mermaid")
        all_nodes.add(trans.from_node)
        if isinstance(trans.to_node, str):
            if re.search(invalid_chars, trans.to_node):
                raise ValueError(f"Invalid node name '{trans.to_node}' for Mermaid")
            all_nodes.add(trans.to_node)
        else:
            for to_node in trans.to_node:
                if re.search(invalid_chars, to_node):
                    raise ValueError(f"Invalid node name '{to_node}' for Mermaid")
                all_nodes.add(to_node)

    # Determine which nodes have conditional transitions
    conditional_nodes: Set[str] = set()
    for trans in workflow_def.workflow.transitions:
        if trans.condition and isinstance(trans.to_node, str):
            conditional_nodes.add(trans.from_node)

    # Shared node definitions and types
    node_types: Dict[str, str] = {}
    node_shapes: Dict[str, str] = {}  # Only used for flowchart

    # Assemble the Mermaid syntax
    mermaid_code = "```mermaid\n"
    if diagram_type == "flowchart":
        mermaid_code += "graph TD\n"  # Top-down layout
    else:  # stateDiagram
        mermaid_code += "stateDiagram-v2\n"

    if title:
        mermaid_code += f"    %% Diagram: {title}\n"

    # Optional legend for UX
    if include_legend:
        mermaid_code += "    %% Legend:\n"
        if diagram_type == "flowchart":
            mermaid_code += "    %% - Rectangle: Process Step\n"
            mermaid_code += "    %% - Diamond: Decision Point\n"
        mermaid_code += "    %% - Colors: Blue (Function), Green (Structured LLM), Purple (LLM), Orange (Sub-Workflow), Grey (Unknown)\n"

    if diagram_type == "flowchart":
        # Flowchart-specific: Generate node definitions with shapes
        node_defs: List[str] = []
        for node in all_nodes:
            node_def_flow: Optional[NodeDefinition] = workflow_def.nodes.get(node)
            has_conditions = node in conditional_nodes
            label, node_type, shape = get_node_label_and_type(node, node_def_flow, has_conditions)
            start_shape, end_shape = shape_syntax[shape]
            node_defs.append(f'{node}{start_shape}"{label}"{end_shape}')
            node_types[node] = node_type
            node_shapes[node] = shape

        # Add node definitions
        for node_def_str in node_defs:
            mermaid_code += f"    {node_def_str}\n"

        # Generate arrows for transitions (all solid lines)
        for trans in workflow_def.workflow.transitions:
            from_node = trans.from_node
            if isinstance(trans.to_node, str):
                to_node = trans.to_node
                condition = trans.condition
                if condition:
                    cond = condition.replace('"', '\\"')[:30] + ("..." if len(condition) > 30 else "")
                    mermaid_code += f'    {from_node} -->|"{cond}"| {to_node}\n'
                else:
                    mermaid_code += f'    {from_node} --> {to_node}\n'
            else:
                for to_node in trans.to_node:
                    mermaid_code += f'    {from_node} --> {to_node}\n'

        # Add styles for node types
        for node, node_type in node_types.items():
            if node_type in node_styles:
                mermaid_code += f"    style {node} {node_styles[node_type]}\n"

        # Highlight the start node
        if workflow_def.workflow.start and workflow_def.workflow.start in node_types:
            mermaid_code += f"    style {workflow_def.workflow.start} stroke-width:4px\n"

        # Optional: Subgraphs for sub-workflows
        if include_subgraphs:
            for node, node_def_entry in workflow_def.nodes.items():
                if node_def_entry and node_def_entry.sub_workflow:
                    mermaid_code += f"    subgraph {node}_sub[Sub-Workflow: {node}]\n"
                    sub_nodes: Set[str] = {node_def_entry.sub_workflow.start} if node_def_entry.sub_workflow.start else set()
                    for trans in node_def_entry.sub_workflow.transitions:
                        sub_nodes.add(trans.from_node)
                        if isinstance(trans.to_node, str):
                            sub_nodes.add(trans.to_node)
                        else:
                            sub_nodes.update(trans.to_node)
                    for sub_node in sub_nodes:
                        mermaid_code += f"        {sub_node}[[{sub_node}]]\n"
                    mermaid_code += "    end\n"

    else:  # stateDiagram
        # StateDiagram-specific: Define states
        for node in all_nodes:
            node_def_state: Optional[NodeDefinition] = workflow_def.nodes.get(node)
            has_conditions = node in conditional_nodes
            label, node_type, _ = get_node_label_and_type(node, node_def_state, has_conditions)  # Shape unused
            mermaid_code += f"    state \"{label}\" as {node}\n"
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
                # Parallel transitions approximated with a note
                for to_node in trans.to_node:
                    mermaid_code += f"    {from_node} --> {to_node} : parallel\n"

        # Add styles for node types
        for node, node_type in node_types.items():
            if node_type in node_styles:
                mermaid_code += f"    style {node} {node_styles[node_type]}\n"

    mermaid_code += "```\n"
    return mermaid_code


def main() -> None:
    """Create a complex workflow and print its improved Mermaid diagram representation."""
    manager = WorkflowManager()

    # Add functions
    manager.add_function(
        name="analyze_sentiment",
        type_="embedded",
        code="async def analyze_sentiment(summary: str) -> str:\n    return 'positive' if 'good' in summary.lower() else 'negative'",
    )
    manager.add_function(
        name="extract_keywords",
        type_="embedded",
        code="async def extract_keywords(summary: str) -> str:\n    return 'key1, key2'",
    )
    manager.add_function(
        name="publish_content",
        type_="embedded",
        code="async def publish_content(summary: str, sentiment: str, keywords: str) -> str:\n    return 'Published'",
    )
    manager.add_function(
        name="revise_content",
        type_="embedded",
        code="async def revise_content(summary: str) -> str:\n    return 'Revised summary'",
    )

    # Add LLM node
    llm_config = {
        "model": "grok/xai",
        "system_prompt": "You are a concise summarizer.",
        "prompt_template": "Summarize the following text: {{ input_text }}",
        "temperature": "0.5",
        "max_tokens": "150",
    }
    manager.add_node(name="summarize_text", llm_config=llm_config, output="summary")

    # Add function nodes
    manager.add_node(name="sentiment_analysis", function="analyze_sentiment", output="sentiment")
    manager.add_node(name="keyword_extraction", function="extract_keywords", output="keywords")
    manager.add_node(name="publish", function="publish_content", output="status")
    manager.add_node(name="revise", function="revise_content", output="revised_summary")

    # Define workflow structure
    manager.set_start_node("summarize_text")
    manager.add_transition(from_node="summarize_text", to_node=["sentiment_analysis", "keyword_extraction"])
    manager.add_transition(from_node="sentiment_analysis", to_node="publish", condition="ctx['sentiment'] == 'positive'")
    manager.add_transition(from_node="sentiment_analysis", to_node="revise", condition="ctx['sentiment'] == 'negative'")
    manager.add_transition(from_node="keyword_extraction", to_node="publish")

    # Generate and print both diagrams
    workflow_def = manager.workflow
    print("Flowchart (default):")
    print(generate_mermaid_diagram(workflow_def, include_subgraphs=False, title="Content Processing Workflow"))
    print("\nState Diagram:")
    print(generate_mermaid_diagram(workflow_def, diagram_type="stateDiagram", title="Content Processing Workflow"))
    

if __name__ == "__main__":
    main()