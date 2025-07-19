"""Unit tests for workflow events and event types."""

from quantalogic_flow.flow.flow import WorkflowEvent, WorkflowEventType


class TestWorkflowEventType:
    """Test WorkflowEventType enum."""
    
    def test_all_event_types_exist(self):
        """Test that all expected event types are defined."""
        expected_types = [
            "NODE_STARTED",
            "NODE_COMPLETED", 
            "NODE_FAILED",
            "TRANSITION_EVALUATED",
            "WORKFLOW_STARTED",
            "WORKFLOW_COMPLETED",
            "SUB_WORKFLOW_ENTERED",
            "SUB_WORKFLOW_EXITED",
        ]
        
        for event_type in expected_types:
            assert hasattr(WorkflowEventType, event_type)
            assert isinstance(getattr(WorkflowEventType, event_type), WorkflowEventType)
    
    def test_event_type_values(self):
        """Test that event type values are correct."""
        assert WorkflowEventType.NODE_STARTED.value == "NODE_STARTED"
        assert WorkflowEventType.NODE_COMPLETED.value == "NODE_COMPLETED"
        assert WorkflowEventType.NODE_FAILED.value == "NODE_FAILED"
        assert WorkflowEventType.TRANSITION_EVALUATED.value == "TRANSITION_EVALUATED"
        assert WorkflowEventType.WORKFLOW_STARTED.value == "WORKFLOW_STARTED"
        assert WorkflowEventType.WORKFLOW_COMPLETED.value == "WORKFLOW_COMPLETED"
        assert WorkflowEventType.SUB_WORKFLOW_ENTERED.value == "SUB_WORKFLOW_ENTERED"
        assert WorkflowEventType.SUB_WORKFLOW_EXITED.value == "SUB_WORKFLOW_EXITED"


class TestWorkflowEvent:
    """Test WorkflowEvent dataclass."""
    
    def test_basic_event_creation(self):
        """Test creating a basic workflow event."""
        context = {"test": "data"}
        event = WorkflowEvent(
            event_type=WorkflowEventType.NODE_STARTED,
            node_name="test_node",
            context=context
        )
        
        assert event.event_type == WorkflowEventType.NODE_STARTED
        assert event.node_name == "test_node"
        assert event.context == context
        assert event.result is None
        assert event.exception is None
        assert event.transition_from is None
        assert event.transition_to is None
        assert event.sub_workflow_name is None
        assert event.usage is None
    
    def test_event_with_all_fields(self):
        """Test creating an event with all optional fields."""
        context = {"step": "processing"}
        result = {"output": "processed"}
        exception = ValueError("test error")
        usage = {"tokens": 100}
        
        event = WorkflowEvent(
            event_type=WorkflowEventType.NODE_COMPLETED,
            node_name="process_node",
            context=context,
            result=result,
            exception=exception,
            transition_from="start",
            transition_to="end",
            sub_workflow_name="sub_flow",
            usage=usage
        )
        
        assert event.event_type == WorkflowEventType.NODE_COMPLETED
        assert event.node_name == "process_node"
        assert event.context == context
        assert event.result == result
        assert event.exception == exception
        assert event.transition_from == "start"
        assert event.transition_to == "end"
        assert event.sub_workflow_name == "sub_flow"
        assert event.usage == usage
    
    def test_node_failed_event(self):
        """Test creating a node failed event with exception."""
        context = {"state": "error"}
        exception = RuntimeError("Node execution failed")
        
        event = WorkflowEvent(
            event_type=WorkflowEventType.NODE_FAILED,
            node_name="failing_node",
            context=context,
            exception=exception
        )
        
        assert event.event_type == WorkflowEventType.NODE_FAILED
        assert event.node_name == "failing_node"
        assert event.exception == exception
        assert isinstance(event.exception, RuntimeError)
        assert str(event.exception) == "Node execution failed"
    
    def test_transition_event(self):
        """Test creating a transition evaluation event."""
        context = {"condition_met": True}
        
        event = WorkflowEvent(
            event_type=WorkflowEventType.TRANSITION_EVALUATED,
            node_name=None,
            context=context,
            transition_from="start_node",
            transition_to="end_node"
        )
        
        assert event.event_type == WorkflowEventType.TRANSITION_EVALUATED
        assert event.node_name is None
        assert event.transition_from == "start_node"
        assert event.transition_to == "end_node"
    
    def test_sub_workflow_events(self):
        """Test creating sub-workflow events."""
        context = {"parent_data": "value"}
        
        enter_event = WorkflowEvent(
            event_type=WorkflowEventType.SUB_WORKFLOW_ENTERED,
            node_name="sub_node",
            context=context,
            sub_workflow_name="child_workflow"
        )
        
        exit_event = WorkflowEvent(
            event_type=WorkflowEventType.SUB_WORKFLOW_EXITED,
            node_name="sub_node",
            context=context,
            sub_workflow_name="child_workflow",
            result={"sub_result": "completed"}
        )
        
        assert enter_event.event_type == WorkflowEventType.SUB_WORKFLOW_ENTERED
        assert enter_event.sub_workflow_name == "child_workflow"
        
        assert exit_event.event_type == WorkflowEventType.SUB_WORKFLOW_EXITED
        assert exit_event.sub_workflow_name == "child_workflow"
        assert exit_event.result == {"sub_result": "completed"}
    
    def test_workflow_lifecycle_events(self):
        """Test workflow start and completion events."""
        initial_context = {"input": "data"}
        final_context = {"input": "data", "output": "result"}
        
        start_event = WorkflowEvent(
            event_type=WorkflowEventType.WORKFLOW_STARTED,
            node_name=None,
            context=initial_context
        )
        
        complete_event = WorkflowEvent(
            event_type=WorkflowEventType.WORKFLOW_COMPLETED,
            node_name=None,
            context=final_context
        )
        
        assert start_event.event_type == WorkflowEventType.WORKFLOW_STARTED
        assert start_event.node_name is None
        assert start_event.context == initial_context
        
        assert complete_event.event_type == WorkflowEventType.WORKFLOW_COMPLETED
        assert complete_event.node_name is None
        assert complete_event.context == final_context
    
    def test_event_with_usage_data(self):
        """Test event with LLM usage information."""
        usage_data = {
            "prompt_tokens": 50,
            "completion_tokens": 25,
            "total_tokens": 75,
            "cost": 0.002
        }
        
        event = WorkflowEvent(
            event_type=WorkflowEventType.NODE_COMPLETED,
            node_name="llm_node",
            context={"processed": True},
            usage=usage_data
        )
        
        assert event.usage == usage_data
        assert event.usage["total_tokens"] == 75
        assert event.usage["cost"] == 0.002
