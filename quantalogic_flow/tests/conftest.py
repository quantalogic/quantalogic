"""Test configuration and shared fixtures for quantalogic_flow tests."""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

from quantalogic_flow.flow.flow import (
    Nodes,
    Workflow,
    WorkflowEngine,
    WorkflowEvent,
    WorkflowEventType,
)


@pytest.fixture
def sample_context():
    """Provide a basic context for testing."""
    return {
        "input_text": "Hello, world!",
        "temperature": 0.7,
        "max_tokens": 100,
        "user_name": "TestUser",
        "items": ["apple", "banana", "cherry"],
        "count": 42,
    }


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Mocked LLM response content"
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 20
    mock_response.usage.total_tokens = 30
    return mock_response


@pytest.fixture
def mock_structured_llm_response():
    """Mock structured LLM response for testing."""
    from pydantic import BaseModel
    
    class MockResponse(BaseModel):
        answer: str = "Mocked structured answer"
        confidence: float = 0.95
    
    return MockResponse()


@pytest.fixture
def event_collector():
    """Fixture to collect workflow events for testing."""
    events = []
    
    def collect_event(event: WorkflowEvent):
        events.append(event)
    
    collect_event.events = events
    return collect_event


@pytest.fixture 
def simple_workflow():
    """Create a simple workflow for testing."""
    workflow = Workflow("start")
    return workflow


@pytest.fixture
def nodes_registry_backup():
    """Backup and restore the global node registry."""
    backup = Nodes.NODE_REGISTRY.copy()
    yield backup
    Nodes.NODE_REGISTRY.clear()
    Nodes.NODE_REGISTRY.update(backup)


@pytest.fixture
async def workflow_engine(simple_workflow):
    """Create a workflow engine for testing."""
    engine = simple_workflow.build()
    return engine


# Test data factories
class TestDataFactory:
    """Factory for creating test data objects."""
    
    @staticmethod
    def create_workflow_event(
        event_type: WorkflowEventType = WorkflowEventType.NODE_STARTED,
        node_name: str = "test_node",
        context: Dict[str, Any] | None = None,
        **kwargs
    ) -> WorkflowEvent:
        """Create a workflow event for testing."""
        if context is None:
            context = {"test": "data"}
        
        return WorkflowEvent(
            event_type=event_type,
            node_name=node_name,
            context=context,
            **kwargs
        )
    
    @staticmethod
    def create_complex_context() -> Dict[str, Any]:
        """Create a complex context for testing."""
        return {
            "text": "Sample text for processing",
            "numbers": [1, 2, 3, 4, 5],
            "config": {
                "temperature": 0.8,
                "max_tokens": 200,
                "model": "gpt-3.5-turbo"
            },
            "metadata": {
                "timestamp": "2025-06-30T12:00:00Z",
                "user_id": "test_user_123",
                "session_id": "session_456"
            }
        }


# Async utilities for testing
class AsyncTestHelpers:
    """Helper utilities for async testing."""
    
    @staticmethod
    async def run_workflow_with_timeout(engine: WorkflowEngine, context: Dict[str, Any], timeout: float = 5.0):
        """Run a workflow with a timeout to prevent hanging tests."""
        return await asyncio.wait_for(engine.run(context), timeout=timeout)
    
    @staticmethod
    def create_async_mock(return_value=None):
        """Create an async mock with a specified return value."""
        mock = AsyncMock()
        if return_value is not None:
            mock.return_value = return_value
        return mock


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Add custom markers
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "examples: Example validation tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on file location."""
    for item in items:
        # Add markers based on test file location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "examples" in str(item.fspath):
            item.add_marker(pytest.mark.examples)
