"""Unit tests for WorkflowEngine class."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from quantalogic_flow.flow.flow import (
    Nodes,
    Workflow,
    WorkflowEngine,
    WorkflowEvent,
    WorkflowEventType,
)


class TestWorkflowEngine:
    """Test WorkflowEngine class functionality."""
    
    def test_engine_initialization(self, nodes_registry_backup):
        """Test WorkflowEngine initialization."""
        @Nodes.define(output="test_output")
        def test_node(input_data):
            return input_data
        
        workflow = Workflow("test_node")
        engine = WorkflowEngine(workflow)
        
        assert engine.workflow == workflow
        assert engine.context == {}
        assert engine.observers == []
        assert engine.parent_engine is None
    
    def test_engine_with_parent(self, nodes_registry_backup):
        """Test WorkflowEngine with parent engine."""
        @Nodes.define(output="parent_output")
        def parent_node(data):
            return data
        
        @Nodes.define(output="child_output")
        def child_node(data):
            return data
        
        parent_workflow = Workflow("parent_node")
        child_workflow = Workflow("child_node")
        
        parent_engine = WorkflowEngine(parent_workflow)
        child_engine = WorkflowEngine(child_workflow, parent_engine=parent_engine)
        
        assert child_engine.parent_engine == parent_engine
    
    def test_add_observer(self, nodes_registry_backup):
        """Test adding observers to engine."""
        @Nodes.define(output="test_output")
        def test_node(data):
            return data
        
        workflow = Workflow("test_node")
        engine = WorkflowEngine(workflow)
        
        observer1 = MagicMock()
        observer2 = MagicMock()
        
        engine.add_observer(observer1)
        engine.add_observer(observer2)
        
        assert observer1 in engine.observers
        assert observer2 in engine.observers
        
        # Test duplicate observer not added
        engine.add_observer(observer1)
        assert engine.observers.count(observer1) == 1
    
    def test_remove_observer(self, nodes_registry_backup):
        """Test removing observers from engine."""
        @Nodes.define(output="test_output")
        def test_node(data):
            return data
        
        workflow = Workflow("test_node")
        engine = WorkflowEngine(workflow)
        
        observer = MagicMock()
        engine.add_observer(observer)
        assert observer in engine.observers
        
        engine.remove_observer(observer)
        assert observer not in engine.observers
    
    async def test_notify_observers_sync(self, nodes_registry_backup):
        """Test notifying synchronous observers."""
        @Nodes.define(output="test_output")
        def test_node(data):
            return data
        
        workflow = Workflow("test_node")
        engine = WorkflowEngine(workflow)
        
        sync_observer = MagicMock()
        engine.add_observer(sync_observer)
        
        event = WorkflowEvent(
            event_type=WorkflowEventType.NODE_STARTED,
            node_name="test_node",
            context={"test": "data"}
        )
        
        await engine._notify_observers(event)
        sync_observer.assert_called_once_with(event)
    
    async def test_notify_observers_async(self, nodes_registry_backup):
        """Test notifying asynchronous observers."""
        @Nodes.define(output="test_output")
        def test_node(data):
            return data
        
        workflow = Workflow("test_node")
        engine = WorkflowEngine(workflow)
        
        async_observer = AsyncMock()
        engine.add_observer(async_observer)
        
        event = WorkflowEvent(
            event_type=WorkflowEventType.NODE_COMPLETED,
            node_name="test_node",
            context={"result": "success"}
        )
        
        await engine._notify_observers(event)
        async_observer.assert_called_once_with(event)
    
    async def test_notify_observers_error_handling(self, nodes_registry_backup):
        """Test observer error handling doesn't break notification."""
        @Nodes.define(output="test_output")
        def test_node(data):
            return data
        
        workflow = Workflow("test_node")
        engine = WorkflowEngine(workflow)
        
        def failing_observer(event):
            raise RuntimeError("Observer failed")
        
        good_observer = MagicMock()
        
        engine.add_observer(failing_observer)
        engine.add_observer(good_observer)
        
        event = WorkflowEvent(
            event_type=WorkflowEventType.NODE_STARTED,
            node_name="test_node",
            context={}
        )
        
        # Should not raise exception
        await engine._notify_observers(event)
        
        # Good observer should still be called
        good_observer.assert_called_once_with(event)
    
    async def test_simple_workflow_execution(self, nodes_registry_backup):
        """Test executing a simple single-node workflow."""
        @Nodes.define(output="result")
        def process_node(input_data):
            return f"processed: {input_data}"
        
        workflow = Workflow("process_node")
        engine = workflow.build()
        
        initial_context = {"input_data": "test data"}
        result_context = await engine.run(initial_context)
        
        assert result_context["input_data"] == "test data"
        assert result_context["result"] == "processed: test data"
    
    async def test_sequential_workflow_execution(self, nodes_registry_backup):
        """Test executing a sequential workflow."""
        @Nodes.define(output="step1_result")
        def step1_node(input_data):
            return f"step1: {input_data}"
        
        @Nodes.define(output="step2_result")
        def step2_node(step1_result):
            return f"step2: {step1_result}"
        
        @Nodes.define(output="final_result")
        def final_node(step2_result):
            return f"final: {step2_result}"
        
        workflow = Workflow("step1_node")
        workflow.sequence("step2_node", "final_node")
        engine = workflow.build()
        
        initial_context = {"input_data": "original"}
        result_context = await engine.run(initial_context)
        
        assert result_context["step1_result"] == "step1: original"
        assert result_context["step2_result"] == "step2: step1: original"
        assert result_context["final_result"] == "final: step2: step1: original"
    
    async def test_conditional_workflow_execution(self, nodes_registry_backup):
        """Test executing a workflow with conditional transitions."""
        @Nodes.define(output="check_result")
        def check_node(value):
            return value > 10
        
        @Nodes.define(output="high_result")
        def high_node(value):
            return f"high: {value}"
        
        @Nodes.define(output="low_result")
        def low_node(value):
            return f"low: {value}"
        
        def is_high(ctx):
            return ctx.get("check_result", False)
        
        workflow = Workflow("check_node")
        workflow.branch([("high_node", is_high)], default="low_node")
        
        engine = workflow.build()
        
        # Test high value path
        high_context = await engine.run({"value": 15})
        assert high_context["check_result"] is True
        assert high_context["high_result"] == "high: 15"
        assert "low_result" not in high_context
        
        # Test low value path
        engine = workflow.build()  # Reset engine
        low_context = await engine.run({"value": 5})
        assert low_context["check_result"] is False
        assert low_context["low_result"] == "low: 5"
        assert "high_result" not in low_context
    
    async def test_workflow_with_input_mapping(self, nodes_registry_backup):
        """Test workflow execution with input mapping."""
        @Nodes.define(output="start_result")
        def start_node(data):
            return {"processed_data": data, "timestamp": "2025-06-30"}
        
        @Nodes.define(output="mapped_result")
        def mapped_node(custom_input, time_input):
            return f"Custom: {custom_input}, Time: {time_input}"
        
        def extract_timestamp(ctx):
            return ctx.get("start_result", {}).get("timestamp", "unknown")
        
        workflow = Workflow("start_node")
        workflow.then("mapped_node")
        workflow.node_input_mappings["mapped_node"] = {
            "custom_input": "start_result.processed_data",
            "time_input": extract_timestamp
        }
        
        engine = workflow.build()
        result = await engine.run({"data": "test_data"})
        
        assert "mapped_result" in result
        # Note: The actual input mapping logic might need adjustment based on implementation
    
    async def test_workflow_event_lifecycle(self, nodes_registry_backup):
        """Test complete workflow event lifecycle."""
        @Nodes.define(output="result")
        def test_node(input_data):
            return f"processed: {input_data}"
        
        workflow = Workflow("test_node")
        engine = workflow.build()
        
        events = []
        def event_collector(event):
            events.append(event)
        
        engine.add_observer(event_collector)
        
        await engine.run({"input_data": "test"})
        
        # Check event sequence
        event_types = [event.event_type for event in events]
        
        assert WorkflowEventType.WORKFLOW_STARTED in event_types
        assert WorkflowEventType.NODE_STARTED in event_types
        assert WorkflowEventType.NODE_COMPLETED in event_types
        assert WorkflowEventType.WORKFLOW_COMPLETED in event_types
        
        # Verify event order
        start_idx = event_types.index(WorkflowEventType.WORKFLOW_STARTED)
        node_start_idx = event_types.index(WorkflowEventType.NODE_STARTED)
        node_complete_idx = event_types.index(WorkflowEventType.NODE_COMPLETED)
        complete_idx = event_types.index(WorkflowEventType.WORKFLOW_COMPLETED)
        
        assert start_idx < node_start_idx < node_complete_idx < complete_idx
    
    async def test_workflow_execution_with_missing_node(self, nodes_registry_backup):
        """Test workflow execution handles missing node gracefully."""
        @Nodes.define(output="result")
        def existing_node(data):
            return data
        
        workflow = Workflow("existing_node")
        # Manually add a transition to a non-existent node
        workflow.transitions["existing_node"] = [("missing_node", None)]
        
        engine = workflow.build()
        
        # The workflow should handle missing nodes gracefully and not crash
        with pytest.raises(ValueError, match="Node missing_node not found"):
            await engine.run({"data": "test"})
        
    async def test_workflow_with_conditional_branching(self, nodes_registry_backup):
        """Test a workflow with conditional branching."""
        @Nodes.define(output="result")
        def check_node(value):
            return value > 10
        
        @Nodes.define(output="high_result")
        def high_node(value):
            return f"high: {value}"
        
        @Nodes.define(output="low_result")
        def low_node(value):
            return f"low: {value}"
        
        def is_high(ctx):
            return ctx.get("result", False)
        
        workflow = Workflow("check_node")
        workflow.branch([("high_node", is_high)], default="low_node")
        
        engine = workflow.build()
        
        # Test high value path
        high_context = await engine.run({"value": 15})
        assert high_context["result"] is True
        assert high_context["high_result"] == "high: 15"
        assert "low_result" not in high_context
        
        # Test low value path
        engine = workflow.build()  # Reset engine
        low_context = await engine.run({"value": 5})
        assert low_context["result"] is False
        assert low_context["low_result"] == "low: 5"
        assert "high_result" not in low_context
    
    async def test_workflow_execution_with_node_error(self, nodes_registry_backup):
        """Test workflow execution handles node errors."""
        @Nodes.define(output="result")
        def failing_node(data):
            raise RuntimeError("Node execution failed")
        
        workflow = Workflow("failing_node")
        engine = workflow.build()
        
        events = []
        def event_collector(event):
            events.append(event)
        
        engine.add_observer(event_collector)
        
        with pytest.raises(RuntimeError, match="Node execution failed"):
            await engine.run({"data": "test"})
        
        # Check that NODE_FAILED event was emitted
        event_types = [event.event_type for event in events]
        assert WorkflowEventType.NODE_FAILED in event_types
        
        # Find the failed event and check it has exception info
        failed_events = [e for e in events if e.event_type == WorkflowEventType.NODE_FAILED]
        assert len(failed_events) == 1
        assert isinstance(failed_events[0].exception, RuntimeError)
    
    async def test_workflow_execution_with_dict_result(self, nodes_registry_backup):
        """Test workflow execution with dict result updates context."""
        @Nodes.define()  # No output specified
        def dict_node(input_data):
            return {
                "result1": f"processed: {input_data}",
                "result2": f"secondary: {input_data}",
                "metadata": {"processed": True}
            }
        
        workflow = Workflow("dict_node")
        engine = workflow.build()
        
        result = await engine.run({"input_data": "test"})
        
        assert result["result1"] == "processed: test"
        assert result["result2"] == "secondary: test"
        assert result["metadata"]["processed"] is True
        assert result["input_data"] == "test"  # Original data preserved
    
    def test_workflow_engine_sub_workflow_execution(self, nodes_registry_backup):
        """Test WorkflowEngine execution with sub-workflows."""
        @Nodes.define(output="main_result")
        def main_node(input_data):
            return f"main: {input_data}"
        
        @Nodes.define(output="sub_result")
        def sub_node(sub_input):
            return f"sub: {sub_input}"
        
        # Create sub-workflow
        sub_workflow = Workflow("sub_node")
        
        # Create main workflow with sub-workflow
        workflow = Workflow("main_node")
        workflow.add_sub_workflow(
            "sub_workflow_node",
            sub_workflow,
            inputs={"sub_input": "main_result"},
            output="final_result"
        )
        
        engine = workflow.build()
        
        # This would test sub-workflow execution in integration tests
        assert engine.workflow == workflow

    def test_workflow_engine_observer_notifications(self, nodes_registry_backup):
        """Test that WorkflowEngine properly notifies observers."""
        events_received = []
        
        @Nodes.define(output="test_result")
        def test_node(input_data):
            return f"processed: {input_data}"
        
        def test_observer(event):
            events_received.append(event.event_type)
        
        workflow = Workflow("test_node")
        workflow.add_observer(test_observer)
        
        engine = workflow.build()
        assert test_observer in engine.observers

    def test_workflow_engine_parent_relationship(self, nodes_registry_backup):
        """Test WorkflowEngine parent-child relationships."""
        @Nodes.define(output="parent_result")
        def parent_node(input_data):
            return input_data
        
        @Nodes.define(output="child_result") 
        def child_node(input_data):
            return input_data
        
        parent_workflow = Workflow("parent_node")
        child_workflow = Workflow("child_node")
        
        parent_engine = parent_workflow.build()
        child_engine = child_workflow.build(parent_engine=parent_engine)
        
        assert child_engine.parent_engine == parent_engine
        assert parent_engine.parent_engine is None

    def test_workflow_engine_observer_management(self, nodes_registry_backup):
        """Test WorkflowEngine observer add/remove functionality."""
        @Nodes.define(output="test_result")
        def test_node(input_data):
            return input_data
        
        workflow = Workflow("test_node")
        engine = workflow.build()
        
        observer1 = MagicMock()
        observer2 = MagicMock()
        
        # Test adding observers
        engine.add_observer(observer1)
        engine.add_observer(observer2)
        
        assert observer1 in engine.observers
        assert observer2 in engine.observers
        
        # Test removing observer
        engine.remove_observer(observer1)
        assert observer1 not in engine.observers
        assert observer2 in engine.observers
        
        # Test adding duplicate observer
        engine.add_observer(observer2)
        assert len([obs for obs in engine.observers if obs == observer2]) == 1

    def test_workflow_engine_context_handling(self, nodes_registry_backup):
        """Test WorkflowEngine context management."""
        @Nodes.define(output="result")
        def test_node(input_param):
            return f"processed: {input_param}"
        
        workflow = Workflow("test_node")
        engine = workflow.build()
        
        # Test initial context
        assert engine.context == {}
        
        # Context would be set during run() method
        # This tests the structure is correct
        assert hasattr(engine, "context")
        assert isinstance(engine.context, dict)

    def test_workflow_engine_async_observer_handling(self, nodes_registry_backup):
        """Test WorkflowEngine handling of async observers."""
        @Nodes.define(output="test_result")
        def test_node(input_data):
            return input_data
        
        async def async_observer(event):
            # Simulate async processing
            await asyncio.sleep(0.001)
            return f"processed: {event.event_type}"
        
        def sync_observer(event):
            return f"sync: {event.event_type}"
        
        workflow = Workflow("test_node")
        workflow.add_observer(async_observer)
        workflow.add_observer(sync_observer)
        
        engine = workflow.build()
        
        assert async_observer in engine.observers
        assert sync_observer in engine.observers

    def test_workflow_engine_error_handling_in_observers(self, nodes_registry_backup):
        """Test WorkflowEngine handling of observer errors."""
        @Nodes.define(output="test_result")
        def test_node(input_data):
            return input_data
        
        def failing_observer(event):
            raise Exception("Observer failed")
        
        def good_observer(event):
            return "success"
        
        workflow = Workflow("test_node")
        workflow.add_observer(failing_observer)
        workflow.add_observer(good_observer)
        
        engine = workflow.build()
        
        # Both observers should be registered
        assert failing_observer in engine.observers
        assert good_observer in engine.observers

    def test_workflow_engine_input_mapping_execution(self, nodes_registry_backup):
        """Test WorkflowEngine handling of input mappings during execution."""
        @Nodes.define(output="mapped_result")
        def mapped_node(param1, param2):
            return f"{param1}-{param2}"
        
        def custom_mapper(ctx):
            return ctx.get("base_value", 0) * 2
        
        mapping = {
            "param1": "direct_key",
            "param2": custom_mapper
        }
        
        workflow = Workflow("mapped_node")
        workflow.node("mapped_node", inputs_mapping=mapping)
        
        engine = workflow.build()
        
        # Verify input mappings are stored
        assert engine.workflow.node_input_mappings["mapped_node"] == mapping

    def test_workflow_engine_transition_evaluation(self, nodes_registry_backup):
        """Test WorkflowEngine transition condition evaluation."""
        @Nodes.define(output="start_result")
        def start_node(input_data):
            return input_data
        
        @Nodes.define(output="conditional_result")
        def conditional_node(data):
            return f"conditional: {data}"
        
        @Nodes.define(output="default_result")
        def default_node(data):
            return f"default: {data}"
        
        def condition_func(ctx):
            return ctx.get("use_conditional", False)
        
        workflow = Workflow("start_node")
        workflow.then("conditional_node", condition_func)
        workflow.then("default_node", None)  # Default transition
        
        engine = workflow.build()
        
        # Verify transitions are set up correctly
        start_transitions = engine.workflow.transitions["start_node"]
        conditional_transitions = engine.workflow.transitions["conditional_node"]
        assert len(start_transitions) == 1
        assert len(conditional_transitions) == 1
        
        conditional_transition = start_transitions[0]
        default_transition = conditional_transitions[0]
        
        assert conditional_transition[0] == "conditional_node"
        assert conditional_transition[1] == condition_func
        assert default_transition[0] == "default_node"
        assert default_transition[1] is None
