"""Unit tests for Workflow class."""

from unittest.mock import MagicMock

import pytest

from quantalogic_flow.flow.flow import Nodes, Workflow, WorkflowEngine


class TestWorkflow:
    """Test Workflow class functionality."""
    
    def test_workflow_creation(self, nodes_registry_backup):
        """Test basic workflow creation."""
        # Register a node first
        @Nodes.define(output="start_output")
        def start_node(input_data):
            return input_data
        
        workflow = Workflow("start_node")
        
        assert workflow.start_node == "start_node"
        assert workflow.current_node == "start_node"
        assert "start_node" in workflow.nodes
        assert workflow.transitions == {}
        assert workflow.node_inputs["start_node"] == ["input_data"]
        assert workflow.node_outputs["start_node"] == "start_output"
        assert workflow.node_input_mappings == {}
    
    def test_workflow_creation_with_unregistered_node(self, nodes_registry_backup):
        """Test workflow creation fails with unregistered node."""
        with pytest.raises(ValueError, match="Node nonexistent_node not registered"):
            Workflow("nonexistent_node")
    
    def test_register_simple_node(self, nodes_registry_backup):
        """Test registering a simple node."""
        # Register a test node
        @Nodes.define(output="test_output")
        def test_node(input_param):
            return f"processed: {input_param}"
        
        workflow = Workflow("test_node")
        
        assert "test_node" in workflow.nodes
        assert workflow.node_inputs["test_node"] == ["input_param"]
        assert workflow.node_outputs["test_node"] == "test_output"
    
    def test_sequence_method(self, nodes_registry_backup):
        """Test adding nodes in sequence."""
        # Register test nodes
        @Nodes.define(output="output1")
        def node1(input1):
            return f"result1: {input1}"
        
        @Nodes.define(output="output2") 
        def node2(input2):
            return f"result2: {input2}"
        
        @Nodes.define(output="output3")
        def node3(input3):
            return f"result3: {input3}"
        
        workflow = Workflow("node1")
        workflow.sequence("node2", "node3")
        
        # Check transitions are set up correctly
        assert ("node2", None) in workflow.transitions["node1"]
        assert ("node3", None) in workflow.transitions["node2"]
        assert workflow.current_node == "node3"
    
    def test_then_method(self, nodes_registry_backup):
        """Test adding conditional transitions."""
        @Nodes.define(output="output1")
        def node1(input1):
            return input1
        
        @Nodes.define(output="output2")
        def node2(input2):
            return input2
        
        def condition(ctx):
            return ctx.get("proceed", True)
        
        workflow = Workflow("node1")
        workflow.then("node2", condition)
        
        assert ("node2", condition) in workflow.transitions["node1"]
        assert workflow.current_node == "node2"
    
    def test_branch_method(self, nodes_registry_backup):
        """Test branching workflow paths."""
        @Nodes.define(output="start_output")
        def start_node(input_data):
            return input_data
        
        @Nodes.define(output="branch1_output")
        def branch1_node(data):
            return f"branch1: {data}"
        
        @Nodes.define(output="branch2_output")
        def branch2_node(data):
            return f"branch2: {data}"
        
        @Nodes.define(output="default_output")
        def default_node(data):
            return f"default: {data}"
        
        def condition1(ctx):
            return ctx.get("use_branch1", False)
        
        def condition2(ctx):
            return ctx.get("use_branch2", False)
        
        workflow = Workflow("start_node")
        workflow.branch([
            ("branch1_node", condition1),
            ("branch2_node", condition2)
        ], default="default_node")
        
        # Check all branches are set up
        transitions = workflow.transitions["start_node"]
        assert ("branch1_node", condition1) in transitions
        assert ("branch2_node", condition2) in transitions
        assert ("default_node", None) in transitions
    
    def test_parallel_method(self, nodes_registry_backup):
        """Test parallel node execution setup."""
        @Nodes.define(output="start_output")
        def start_node(input_data):
            return input_data
        
        @Nodes.define(output="parallel1_output")
        def parallel1_node(data):
            return f"parallel1: {data}"
        
        @Nodes.define(output="parallel2_output") 
        def parallel2_node(data):
            return f"parallel2: {data}"
        
        workflow = Workflow("start_node")
        workflow.parallel("parallel1_node", "parallel2_node")
        
        # Check parallel transitions
        transitions = workflow.transitions["start_node"]
        assert ("parallel1_node", None) in transitions
        assert ("parallel2_node", None) in transitions
        assert workflow.current_node is None  # No current node after parallel
    
    def test_node_input_mapping(self, nodes_registry_backup):
        """Test node input mapping functionality."""
        @Nodes.define(output="mapped_output")
        def mapped_node(param1, param2):
            return f"{param1} + {param2}"
        
        def param2_mapper(ctx):
            return ctx.get("value") * 2
        
        mapping = {
            "param1": "context_key1",
            "param2": param2_mapper
        }
        
        workflow = Workflow("mapped_node")
        workflow.node("mapped_node", inputs_mapping=mapping)
        
        assert workflow.node_input_mappings["mapped_node"] == mapping
    
    def test_add_observer(self, nodes_registry_backup):
        """Test adding workflow observers."""
        @Nodes.define(output="start_output")
        def start_node(input_data):
            return input_data
            
        workflow = Workflow("start_node")
        
        observer1 = MagicMock()
        observer2 = MagicMock()
        
        workflow.add_observer(observer1)
        workflow.add_observer(observer2)
        
        assert observer1 in workflow._observers
        assert observer2 in workflow._observers
        
        # Test duplicate observer is not added
        workflow.add_observer(observer1)
        assert workflow._observers.count(observer1) == 1
    
    def test_build_workflow_engine(self, nodes_registry_backup):
        """Test building WorkflowEngine from Workflow."""
        @Nodes.define(output="test_output")
        def test_node(input_param):
            return input_param
        
        workflow = Workflow("test_node")
        observer = MagicMock()
        workflow.add_observer(observer)
        
        engine = workflow.build()
        
        assert isinstance(engine, WorkflowEngine)
        assert engine.workflow == workflow
        assert observer in engine.observers
    
    def test_loop_functionality(self, nodes_registry_backup):
        """Test workflow loop creation."""
        @Nodes.define(output="start_output")
        def start_node(counter):
            return counter
        
        @Nodes.define(output="loop_output")
        def loop_node(counter):
            return counter + 1
        
        @Nodes.define(output="end_output")
        def end_node(counter):
            return f"finished: {counter}"
        
        workflow = Workflow("start_node")
        workflow.start_loop()
        workflow.node("loop_node")
        
        def loop_condition(ctx):
            return ctx.get("counter", 0) > 5
        workflow.end_loop(loop_condition, "end_node")
        
        # Verify loop structure
        assert workflow.current_node == "end_node"
        assert not workflow.in_loop
        assert workflow.loop_nodes == []
        assert workflow.loop_entry_node is None
    
    def test_loop_without_current_node_fails(self, nodes_registry_backup):
        """Test that starting a loop without current node fails."""
        @Nodes.define(output="start_output")
        def start_node(input_data):
            return input_data
            
        workflow = Workflow("start_node")
        workflow.current_node = None
        
        with pytest.raises(ValueError, match="Cannot start loop without a current node"):
            workflow.start_loop()
    
    def test_end_loop_without_loop_nodes_fails(self, nodes_registry_backup):
        """Test that ending loop without nodes fails."""
        @Nodes.define(output="start_output")
        def start_node(input_data):
            return input_data
        
        @Nodes.define(output="end_output")
        def end_node(input_data):
            return input_data
        
        workflow = Workflow("start_node")
        workflow.start_loop()
        
        def always_true(ctx):
            return True
        
        with pytest.raises(ValueError, match="No loop nodes defined"):
            workflow.end_loop(always_true, "end_node")
    
    def test_complex_workflow_structure(self, nodes_registry_backup):
        """Test building a complex workflow with multiple patterns."""
        # Register nodes
        @Nodes.define(output="start_result")
        def start_node(input_data):
            return input_data
        
        @Nodes.define(output="process_result")
        def process_node(data):
            return f"processed: {data}"
        
        @Nodes.define(output="validate_result")
        def validate_node(data):
            return f"validated: {data}"
        
        @Nodes.define(output="finalize_result")
        def finalize_node(data):
            return f"finalized: {data}"
        
        def is_valid_condition(ctx):
            return ctx.get("is_valid", True)
        
        # Build complex workflow
        workflow = Workflow("start_node")
        workflow.sequence("process_node", "validate_node")
        workflow.then("finalize_node", is_valid_condition)
        
        # Verify structure
        assert workflow.start_node == "start_node"
        assert workflow.current_node == "finalize_node"
        assert len(workflow.nodes) == 4
        assert ("process_node", None) in workflow.transitions["start_node"]
        assert ("validate_node", None) in workflow.transitions["process_node"]
    
    def test_sub_workflow_node_creation(self, nodes_registry_backup):
        """Test SubWorkflowNode creation and functionality."""
        from quantalogic_flow.flow.flow import SubWorkflowNode
        
        # Create a sub-workflow
        @Nodes.define(output="sub_output")
        def sub_node(sub_input):
            return f"sub_processed: {sub_input}"
        
        sub_workflow = Workflow("sub_node")
        
        # Create SubWorkflowNode
        sub_workflow_node = SubWorkflowNode(
            sub_workflow=sub_workflow,
            inputs={"sub_input": "main_input"},
            output="sub_result"
        )
        
        assert sub_workflow_node.sub_workflow == sub_workflow
        assert sub_workflow_node.inputs == {"sub_input": "main_input"}
        assert sub_workflow_node.output == "sub_result"

    def test_add_sub_workflow(self, nodes_registry_backup):
        """Test adding sub-workflow to main workflow."""
        # Create main workflow nodes
        @Nodes.define(output="main_output")
        def main_node(main_input):
            return main_input
        
        # Create sub-workflow
        @Nodes.define(output="sub_output")
        def sub_node(sub_input):
            return f"sub_processed: {sub_input}"
        
        sub_workflow = Workflow("sub_node")
        main_workflow = Workflow("main_node")
        
        # Add sub-workflow
        main_workflow.add_sub_workflow(
            name="sub_workflow_node",
            sub_workflow=sub_workflow,
            inputs={"sub_input": "main_output"},
            output="final_result"
        )
        
        assert "sub_workflow_node" in main_workflow.nodes
        assert main_workflow.node_outputs["sub_workflow_node"] == "final_result"
        assert main_workflow.current_node == "sub_workflow_node"

    def test_workflow_with_multiple_observers(self, nodes_registry_backup):
        """Test workflow with multiple observers."""
        @Nodes.define(output="test_output")
        def test_node(input_data):
            return input_data
        
        workflow = Workflow("test_node")
        
        observer1 = MagicMock()
        observer2 = MagicMock()
        observer3 = MagicMock()
        
        workflow.add_observer(observer1)
        workflow.add_observer(observer2)
        workflow.add_observer(observer3)
        
        assert len(workflow._observers) == 3
        assert observer1 in workflow._observers
        assert observer2 in workflow._observers
        assert observer3 in workflow._observers

    def test_workflow_input_mapping_with_callable(self, nodes_registry_backup):
        """Test workflow with callable input mapping."""
        @Nodes.define(output="mapped_output")
        def mapped_node(param1, param2):
            return f"{param1} + {param2}"
        
        def dynamic_mapper(ctx):
            return ctx.get("base_value", 0) * 2
        
        workflow = Workflow("mapped_node")
        workflow.node(
            "mapped_node",
            inputs_mapping={
                "param1": "static_key",
                "param2": dynamic_mapper
            }
        )
        
        mapping = workflow.node_input_mappings["mapped_node"]
        assert mapping["param1"] == "static_key"
        assert callable(mapping["param2"])
        assert mapping["param2"] == dynamic_mapper

    def test_workflow_complex_branching_with_default(self, nodes_registry_backup):
        """Test complex branching with default path."""
        @Nodes.define(output="start_output")
        def start_node(input_data):
            return input_data
        
        @Nodes.define(output="branch1_output")
        def branch1_node(data):
            return f"branch1: {data}"
        
        @Nodes.define(output="branch2_output")
        def branch2_node(data):
            return f"branch2: {data}"
        
        @Nodes.define(output="branch3_output")
        def branch3_node(data):
            return f"branch3: {data}"
        
        @Nodes.define(output="default_output")
        def default_node(data):
            return f"default: {data}"
        
        @Nodes.define(output="final_output")
        def final_node(data):
            return f"final: {data}"
        
        def condition1(ctx):
            return ctx.get("use_branch1", False)
        
        def condition2(ctx):
            return ctx.get("use_branch2", False)
        
        def condition3(ctx):
            return ctx.get("use_branch3", False)
        
        workflow = Workflow("start_node")
        workflow.branch([
            ("branch1_node", condition1),
            ("branch2_node", condition2),
            ("branch3_node", condition3)
        ], default="default_node", next_node="final_node")
        
        # Check all branches and default are set up
        transitions = workflow.transitions["start_node"]
        assert ("branch1_node", condition1) in transitions
        assert ("branch2_node", condition2) in transitions
        assert ("branch3_node", condition3) in transitions
        assert ("default_node", None) in transitions
        assert workflow.current_node == "final_node"

    def test_workflow_converge_functionality(self, nodes_registry_backup):
        """Test workflow convergence functionality."""
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
        
        workflow = Workflow("start_node")
        workflow.parallel("branch1_node", "branch2_node")
        workflow.converge("convergence_node")
        
        # Check convergence setup
        assert workflow.current_node == "convergence_node"
        # Should have transitions from orphaned nodes to convergence
        convergence_transitions = []
        for node, transitions in workflow.transitions.items():
            for target, condition in transitions:
                if target == "convergence_node":
                    convergence_transitions.append(node)
        
        assert len(convergence_transitions) > 0

    def test_workflow_nested_loops(self, nodes_registry_backup):
        """Test workflow with nested loop structure."""
        @Nodes.define(output="outer_start")
        def outer_start_node(counter):
            return {"outer": counter, "inner": 0}
        
        @Nodes.define(output="outer_loop")
        def outer_loop_node(data):
            data["outer"] += 1
            return data
        
        @Nodes.define(output="inner_start")
        def inner_start_node(data):
            data["inner"] = 0
            return data
        
        @Nodes.define(output="inner_loop")
        def inner_loop_node(data):
            data["inner"] += 1
            return data
        
        @Nodes.define(output="final_output")
        def final_node(data):
            return f"final: outer={data['outer']}, inner={data['inner']}"
        
        workflow = Workflow("outer_start_node")
        
        # Outer loop
        workflow.start_loop()
        workflow.node("outer_loop_node")
        
        # Inner loop
        workflow.node("inner_start_node")
        workflow.start_loop()
        workflow.node("inner_loop_node")
        
        def inner_condition(ctx):
            return ctx.get("inner", 0) > 3
        
        workflow.end_loop(inner_condition, "outer_loop_node")
        
        def outer_condition(ctx):
            return ctx.get("outer", 0) > 5
        
        workflow.end_loop(outer_condition, "final_node")
        
        assert workflow.current_node == "final_node"
        assert not workflow.in_loop

    def test_workflow_error_handling_cases(self, nodes_registry_backup):
        """Test various error handling scenarios."""
        @Nodes.define(output="valid_output")
        def valid_node(input_data):
            return input_data
        
        workflow = Workflow("valid_node")
        
        # Test adding unregistered node
        with pytest.raises(ValueError, match="Node unregistered_node not registered"):
            workflow.then("unregistered_node")
        
        # Test sequence with unregistered node
        with pytest.raises(ValueError, match="Node unregistered_node not registered"):
            workflow.sequence("unregistered_node")
        
        # Test branch with unregistered node
        with pytest.raises(ValueError, match="Node unregistered_node not registered"):
            workflow.branch([("unregistered_node", None)])

    def test_workflow_state_management(self, nodes_registry_backup):
        """Test workflow state management."""
        @Nodes.define(output="start_output")
        def start_node(input_data):
            return input_data
        
        @Nodes.define(output="middle_output")
        def middle_node(input_data):
            return input_data
        
        @Nodes.define(output="end_output")
        def end_node(input_data):
            return input_data
        
        workflow = Workflow("start_node")
        
        # Test initial state
        assert workflow.current_node == "start_node"
        assert not workflow.in_loop
        assert workflow.loop_nodes == []
        assert workflow.loop_entry_node is None
        
        # Test state changes
        workflow.then("middle_node")
        assert workflow.current_node == "middle_node"
        
        workflow.then("end_node")
        assert workflow.current_node == "end_node"
        
        # Test loop state
        workflow.start_loop()
        assert workflow.in_loop is True
        assert workflow.loop_entry_node == "end_node"
        
        workflow.node("middle_node")
        assert "middle_node" in workflow.loop_nodes
        
        def loop_condition(ctx):
            return ctx.get("exit_loop", False)
        
        workflow.end_loop(loop_condition, "start_node")
        assert not workflow.in_loop
        assert workflow.loop_nodes == []
        assert workflow.loop_entry_node is None

    def test_workflow_chaining_methods(self, nodes_registry_backup):
        """Test method chaining functionality."""
        @Nodes.define(output="node1_output")
        def node1(input_data):
            return input_data
        
        @Nodes.define(output="node2_output")
        def node2(input_data):
            return input_data
        
        @Nodes.define(output="node3_output")
        def node3(input_data):
            return input_data
        
        @Nodes.define(output="observer_output")
        def observer_node(input_data):
            return input_data
        
        observer = MagicMock()
        
        # Test chaining multiple methods
        result = (Workflow("node1")
                 .then("node2")
                 .then("node3")
                 .add_observer(observer)
                 .node("observer_node"))
        
        assert isinstance(result, Workflow)
        assert result.current_node == "observer_node"
        assert observer in result._observers

    def test_workflow_with_no_current_node_scenarios(self, nodes_registry_backup):
        """Test scenarios where current_node is None."""
        @Nodes.define(output="start_output")
        def start_node(input_data):
            return input_data
        
        @Nodes.define(output="parallel1_output")
        def parallel1_node(input_data):
            return input_data
        
        @Nodes.define(output="parallel2_output")
        def parallel2_node(input_data):
            return input_data
        
        workflow = Workflow("start_node")
        
        # After parallel, current_node becomes None
        workflow.parallel("parallel1_node", "parallel2_node")
        assert workflow.current_node is None
        
        # Test operations with None current_node
        workflow.then("start_node")  # Should work
        assert workflow.current_node == "start_node"

    def test_sequence_prevents_self_loop(self, nodes_registry_backup):
        """Test that sequence method prevents self-loops."""
        @Nodes.define(output="output1")
        def node1(input1):
            return input1
        
        @Nodes.define(output="output2")
        def node2(input2):
            return input2
        
        workflow = Workflow("node1")
        
        # This should NOT create a self-loop
        workflow.sequence("node1", "node2")
        
        # Check that no self-loop was created
        node1_transitions = workflow.transitions.get("node1", [])
        self_loops = [t for t in node1_transitions if t[0] == "node1"]
        assert len(self_loops) == 0, "Self-loop should not be created"
        
        # Check that correct transition was created
        next_transitions = [t for t in node1_transitions if t[0] == "node2"]
        assert len(next_transitions) == 1, "Transition to node2 should exist"
        
        # Check that transition between sequence nodes still works
        assert ("node2", None) in workflow.transitions.get("node1", [])
        assert workflow.current_node == "node2"

    def test_then_prevents_self_loop(self, nodes_registry_backup):
        """Test that then method prevents self-loops."""
        @Nodes.define(output="output1")
        def node1(input1):
            return input1
        
        workflow = Workflow("node1")
        
        # This should NOT create a self-loop
        workflow.then("node1")
        
        # Check that no self-loop was created
        node1_transitions = workflow.transitions.get("node1", [])
        self_loops = [t for t in node1_transitions if t[0] == "node1"]
        assert len(self_loops) == 0, "Self-loop should not be created"
        
        # Current node should still be updated
        assert workflow.current_node == "node1"

    def test_sequence_with_valid_transitions(self, nodes_registry_backup):
        """Test that sequence method still works correctly for valid transitions."""
        @Nodes.define(output="output1")
        def node1(input1):
            return input1
        
        @Nodes.define(output="output2")
        def node2(input2):
            return input2
        
        @Nodes.define(output="output3")
        def node3(input3):
            return input3
        
        workflow = Workflow("node1")
        
        # This should create normal transitions
        workflow.sequence("node2", "node3")
        
        # Check transitions
        assert ("node2", None) in workflow.transitions.get("node1", [])
        assert ("node3", None) in workflow.transitions.get("node2", [])
        assert workflow.current_node == "node3"

    def test_then_with_valid_transitions(self, nodes_registry_backup):
        """Test that then method still works correctly for valid transitions."""
        @Nodes.define(output="output1")
        def node1(input1):
            return input1
        
        @Nodes.define(output="output2")
        def node2(input2):
            return input2
        
        workflow = Workflow("node1")
        
        # This should create normal transition
        workflow.then("node2")
        
        # Check transition
        assert ("node2", None) in workflow.transitions.get("node1", [])
        assert workflow.current_node == "node2"

    def test_conditional_then_prevents_self_loop(self, nodes_registry_backup):
        """Test that conditional then method prevents self-loops."""
        @Nodes.define(output="output1")
        def node1(input1):
            return input1
        
        def condition(ctx):
            return ctx.get("proceed", True)
        
        workflow = Workflow("node1")
        
        # This should NOT create a self-loop even with condition
        workflow.then("node1", condition)
        
        # Check that no self-loop was created
        node1_transitions = workflow.transitions.get("node1", [])
        self_loops = [t for t in node1_transitions if t[0] == "node1"]
        assert len(self_loops) == 0, "Self-loop should not be created even with condition"
        
        # Current node should still be updated
        assert workflow.current_node == "node1"
