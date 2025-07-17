#!/usr/bin/env python3
"""Test for the new automatic convergence feature in the branch method"""
from quantalogic_flow.flow.core.workflow import Workflow
from quantalogic_flow.flow.nodes import Nodes


class TestAutomaticConvergence:
    """Test the automatic convergence feature with branch method"""
    
    def test_branch_automatic_convergence(self):
        """Test that branch method with next_node automatically sets up convergence"""
        
        @Nodes.define(output="start_output")
        def start_node(input_data):
            return input_data
        
        @Nodes.define(output="branch1_output")
        def branch1_node(data):
            return f"branch1: {data}"
        
        @Nodes.define(output="branch2_output")
        def branch2_node(data):
            return f"branch2: {data}"
        
        @Nodes.define(output="convergence_output")
        def convergence_node(data):
            return f"converged: {data}"
        
        # Create workflow with automatic convergence
        workflow = Workflow("start_node")
        workflow.branch([
            ("branch1_node", lambda ctx: ctx.get("use_branch1", False)),
            ("branch2_node", lambda ctx: ctx.get("use_branch2", False))
        ], default="branch1_node", next_node="convergence_node")
        
        # Verify that convergence transitions are set up automatically
        assert workflow.current_node == "convergence_node"
        
        # Check that branch nodes have transitions to convergence node
        assert "branch1_node" in workflow.transitions
        assert "branch2_node" in workflow.transitions
        
        branch1_transitions = workflow.transitions["branch1_node"]
        branch2_transitions = workflow.transitions["branch2_node"]
        
        # Both branches should have convergence transitions
        assert ("convergence_node", None) in branch1_transitions
        assert ("convergence_node", None) in branch2_transitions
        
    def test_branch_without_convergence(self):
        """Test that branch method without next_node sets up branch state tracking"""
        
        @Nodes.define(output="start_output")
        def start_node(input_data):
            return input_data
        
        @Nodes.define(output="branch1_output")
        def branch1_node(data):
            return f"branch1: {data}"
        
        @Nodes.define(output="branch2_output")
        def branch2_node(data):
            return f"branch2: {data}"
        
        # Create workflow without explicit convergence
        workflow = Workflow("start_node")
        workflow.branch([
            ("branch1_node", lambda ctx: ctx.get("use_branch1", False)),
            ("branch2_node", lambda ctx: ctx.get("use_branch2", False))
        ], default="branch1_node")
        
        # Verify that branch state tracking is set up
        assert workflow.is_branching  # Should be in branching state
        assert workflow.current_node == "branch1_node"  # Should be set to default
        assert workflow.branch_nodes == ["branch1_node", "branch2_node"]  # Branch nodes tracked
        assert workflow.branch_source_node == "start_node"  # Source node tracked
        
        # Branch nodes should not have convergence transitions yet
        assert "branch1_node" not in workflow.transitions or not workflow.transitions["branch1_node"]
        assert "branch2_node" not in workflow.transitions or not workflow.transitions["branch2_node"]


if __name__ == "__main__":
    test = TestAutomaticConvergence()
    test.test_branch_automatic_convergence()
    test.test_branch_without_convergence()
    print("All tests passed!")
