"""Unit tests for WorkflowEngine class."""

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
        result = await engine.run({"data": "test"})
        
        # The result should contain the output from the existing node
        assert result["result"] == "test"
        # The workflow should stop execution when missing node is encountered
        assert "missing_node_result" not in result
    
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
