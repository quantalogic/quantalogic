"""Test automatic deduction of default and next_node parameters in branch method."""
from quantalogic_flow.flow.core.workflow import Workflow
from quantalogic_flow.flow.nodes import Nodes


def test_branch_auto_default_deduction(nodes_registry_backup):
    """Test that default is automatically deduced from the first branch when not provided."""
    # Register test nodes
    @Nodes.define(output="start_output")
    def start(input_data):
        return input_data
    
    @Nodes.define(output="node_a_output")
    def node_a(input_data):
        return f"node_a: {input_data}"
    
    @Nodes.define(output="node_b_output")
    def node_b(input_data):
        return f"node_b: {input_data}"
    
    wf = Workflow("start")
    wf.current_node = "start"
    
    # Branch without explicit default - should use first branch as default
    wf.branch([
        ("node_a", lambda ctx: ctx.get("condition") == "a"),
        ("node_b", lambda ctx: ctx.get("condition") == "b")
    ])
    
    # Verify transitions include auto-deduced default
    assert "start" in wf.transitions
    transitions = wf.transitions["start"]
    
    # Should have: conditional branch to node_a, conditional branch to node_b
    # No separate default transition since node_a is the first branch
    assert len(transitions) == 2
    
    # Current node should be set to the auto-deduced default
    assert wf.current_node == "node_a"
    
    # Both nodes should be registered
    assert "node_a" in wf.nodes
    assert "node_b" in wf.nodes


def test_branch_auto_convergence_with_then(nodes_registry_backup):
    """Test that branch state is tracked for automatic convergence when then() is called."""
    # Register test nodes
    @Nodes.define(output="start_output")
    def start(input_data):
        return input_data
    
    @Nodes.define(output="node_a_output")
    def node_a(input_data):
        return f"node_a: {input_data}"
    
    @Nodes.define(output="node_b_output")
    def node_b(input_data):
        return f"node_b: {input_data}"
    
    @Nodes.define(output="converge_output")
    def converge_node(input_data):
        return f"converged: {input_data}"
    
    wf = Workflow("start")
    wf.current_node = "start"
    
    # Branch without next_node - should set up branch state tracking
    wf.branch([
        ("node_a", lambda ctx: ctx.get("condition") == "a"),
        ("node_b", lambda ctx: ctx.get("condition") == "b")
    ]).then("converge_node")
    
    # Verify branch state was set up and then cleared
    assert not wf.is_branching  # Should be reset after then()
    assert wf.branch_nodes == []  # Should be cleared after then()
    assert wf.branch_source_node is None  # Should be cleared after then()
    
    # Verify convergence transitions were set up
    assert "node_a" in wf.transitions
    assert "node_b" in wf.transitions
    assert ("converge_node", None) in wf.transitions["node_a"]
    assert ("converge_node", None) in wf.transitions["node_b"]
    
    # Current node should be the convergence node
    assert wf.current_node == "converge_node"


def test_branch_fully_automatic(nodes_registry_backup):
    """Test branch with both default and next_node automatically deduced."""
    # Register test nodes
    @Nodes.define(output="start_output")
    def start(input_data):
        return input_data
    
    @Nodes.define(output="process_pdf_output")
    def process_pdf(input_data):
        return f"pdf: {input_data}"
    
    @Nodes.define(output="process_text_output")
    def process_text(input_data):
        return f"text: {input_data}"
    
    @Nodes.define(output="save_result_output")
    def save_result(input_data):
        return f"saved: {input_data}"
    
    wf = Workflow("start")
    wf.current_node = "start"
    
    # Fully automatic branch - no explicit default or next_node
    wf.branch([
        ("process_pdf", lambda ctx: ctx.get("file_type") == "pdf"),
        ("process_text", lambda ctx: ctx.get("file_type") == "text")
    ]).then("save_result")
    
    # Verify the workflow structure
    assert "start" in wf.transitions
    start_transitions = wf.transitions["start"]
    assert len(start_transitions) == 2
    
    # Verify branch nodes have convergence transitions
    assert "process_pdf" in wf.transitions
    assert "process_text" in wf.transitions
    assert ("save_result", None) in wf.transitions["process_pdf"]
    assert ("save_result", None) in wf.transitions["process_text"]
    
    # Current node should be the convergence node
    assert wf.current_node == "save_result"


def test_branch_explicit_default_with_auto_convergence(nodes_registry_backup):
    """Test branch with explicit default but automatic convergence."""
    # Register test nodes
    @Nodes.define(output="start_output")
    def start(input_data):
        return input_data
    
    @Nodes.define(output="node_a_output")
    def node_a(input_data):
        return f"node_a: {input_data}"
    
    @Nodes.define(output="node_b_output")
    def node_b(input_data):
        return f"node_b: {input_data}"
    
    @Nodes.define(output="node_c_output")
    def node_c(input_data):
        return f"node_c: {input_data}"
    
    @Nodes.define(output="converge_output")
    def converge_node(input_data):
        return f"converged: {input_data}"
    
    wf = Workflow("start")
    wf.current_node = "start"
    
    # Explicit default, automatic convergence
    wf.branch([
        ("node_a", lambda ctx: ctx.get("condition") == "a"),
        ("node_b", lambda ctx: ctx.get("condition") == "b")
    ], default="node_c").then("converge_node")
    
    # Verify default transition was added
    assert "start" in wf.transitions
    start_transitions = wf.transitions["start"]
    assert len(start_transitions) == 3  # Two conditional + one default
    
    # Verify convergence from all nodes including default
    assert ("converge_node", None) in wf.transitions["node_a"]
    assert ("converge_node", None) in wf.transitions["node_b"]
    assert ("converge_node", None) in wf.transitions["node_c"]
    
    # Current node should be the convergence node
    assert wf.current_node == "converge_node"


def test_branch_explicit_parameters_still_work(nodes_registry_backup):
    """Test that explicit default and next_node parameters still work as before."""
    # Register test nodes
    @Nodes.define(output="start_output")
    def start(input_data):
        return input_data
    
    @Nodes.define(output="node_a_output")
    def node_a(input_data):
        return f"node_a: {input_data}"
    
    @Nodes.define(output="node_b_output")
    def node_b(input_data):
        return f"node_b: {input_data}"
    
    @Nodes.define(output="node_c_output")
    def node_c(input_data):
        return f"node_c: {input_data}"
    
    @Nodes.define(output="converge_output")
    def converge_node(input_data):
        return f"converged: {input_data}"
    
    wf = Workflow("start")
    wf.current_node = "start"
    
    # Explicit both parameters (legacy usage)
    wf.branch([
        ("node_a", lambda ctx: ctx.get("condition") == "a"),
        ("node_b", lambda ctx: ctx.get("condition") == "b")
    ], default="node_c", next_node="converge_node")
    
    # Verify convergence was set up immediately
    assert not wf.is_branching  # Should not be in branching state
    assert wf.current_node == "converge_node"
    
    # Verify convergence transitions
    assert ("converge_node", None) in wf.transitions["node_a"]
    assert ("converge_node", None) in wf.transitions["node_b"]
    assert ("converge_node", None) in wf.transitions["node_c"]


def test_branch_default_not_duplicate_when_in_branches(nodes_registry_backup):
    """Test that default is not duplicated when it's already in the branch list."""
    # Register test nodes
    @Nodes.define(output="start_output")
    def start(input_data):
        return input_data
    
    @Nodes.define(output="node_a_output")
    def node_a(input_data):
        return f"node_a: {input_data}"
    
    @Nodes.define(output="node_b_output")
    def node_b(input_data):
        return f"node_b: {input_data}"
    
    wf = Workflow("start")
    wf.current_node = "start"
    
    # First branch node is also the explicit default
    wf.branch([
        ("node_a", lambda ctx: ctx.get("condition") == "a"),
        ("node_b", lambda ctx: ctx.get("condition") == "b")
    ], default="node_a")
    
    # Verify no duplicate transitions
    assert "start" in wf.transitions
    start_transitions = wf.transitions["start"]
    assert len(start_transitions) == 2  # Should not duplicate node_a
    
    # Count occurrences of node_a
    node_a_count = sum(1 for target, _ in start_transitions if target == "node_a")
    assert node_a_count == 1  # Should appear only once
