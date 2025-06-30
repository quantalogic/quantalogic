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
