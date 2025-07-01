"""Mock utilities for LLM responses and external dependencies."""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

from pydantic import BaseModel


class MockLLMResponse:
    """Mock LLM response for testing."""
    
    def __init__(
        self, 
        content: str = "Mock LLM response",
        prompt_tokens: int = 10,
        completion_tokens: int = 20,
        cost: float = 0.001
    ):
        self.choices = [MagicMock()]
        self.choices[0].message.content = content
        self.usage = MagicMock()
        self.usage.prompt_tokens = prompt_tokens
        self.usage.completion_tokens = completion_tokens
        self.usage.total_tokens = prompt_tokens + completion_tokens
        self.cost = cost


class MockStructuredResponse(BaseModel):
    """Example structured response for testing."""
    answer: str = "Mock structured answer"
    confidence: float = 0.95
    category: str = "test"


class LLMMockFactory:
    """Factory for creating various LLM mocks."""
    
    @staticmethod
    def create_acompletion_mock(responses: list[str] | str | None = None) -> AsyncMock:
        """Create a mock for litellm.acompletion function."""
        mock = AsyncMock()
        
        if responses is None:
            responses = ["Default mock response"]
        elif isinstance(responses, str):
            responses = [responses]
            
        # Setup side_effect to cycle through responses
        def side_effect(*args, **kwargs):
            content = responses[mock.call_count % len(responses)] if responses else "Mock response"
            return MockLLMResponse(content=content)
        
        mock.side_effect = side_effect
        return mock
    
    @staticmethod
    def create_instructor_mock(structured_responses: list[BaseModel] | None = None) -> AsyncMock:
        """Create a mock for instructor client."""
        mock_client = MagicMock()
        mock_completion = AsyncMock()
        
        if structured_responses is None:
            structured_responses = [MockStructuredResponse()]
            
        def side_effect(*args, **kwargs):
            response_idx = mock_completion.call_count % len(structured_responses)
            structured_response = structured_responses[response_idx]
            raw_response = MockLLMResponse()
            return structured_response, raw_response
        
        mock_completion.create_with_completion.side_effect = side_effect
        mock_client.chat.completions = mock_completion
        return mock_client
    
    @staticmethod
    def create_template_mock() -> MagicMock:
        """Create a mock for Jinja2 template."""
        mock_template = MagicMock()
        mock_template.render.return_value = "Rendered template content"
        return mock_template


class TestPrompts:
    """Collection of test prompts and templates."""
    
    SIMPLE_PROMPT = "Process this text: {{ text }}"
    COMPLEX_PROMPT = """
    System: You are a helpful assistant.
    
    User: {{ user_input }}
    Context: {{ context }}
    Temperature: {{ temperature }}
    """
    
    SYSTEM_PROMPT = "You are a test assistant. Be helpful and concise."
    
    @staticmethod
    def get_test_template_content() -> str:
        """Get content for test template files."""
        return """
# Test Template

Input: {{ input_text }}
User: {{ user_name }}
Count: {{ count }}

{% if items %}
Items:
{% for item in items %}
- {{ item }}
{% endfor %}
{% endif %}
        """.strip()


class ContextFactory:
    """Factory for creating test contexts."""
    
    @staticmethod
    def simple() -> Dict[str, Any]:
        """Create a simple test context."""
        return {
            "text": "Hello, world!",
            "user_input": "Test input",
            "temperature": 0.7,
        }
    
    @staticmethod
    def complex() -> Dict[str, Any]:
        """Create a complex test context."""
        return {
            "input_text": "Complex test input with multiple parameters",
            "user_name": "TestUser",
            "temperature": 0.8,
            "max_tokens": 150,
            "model": "gpt-3.5-turbo",
            "items": ["item1", "item2", "item3"],
            "count": 42,
            "nested": {
                "level1": {
                    "level2": "deep value"
                }
            },
            "config": {
                "enabled": True,
                "retries": 3,
                "timeout": 30.0
            }
        }
    
    @staticmethod
    def workflow_context() -> Dict[str, Any]:
        """Create a context suitable for workflow testing."""
        return {
            "start_data": "Initial workflow data",
            "step1_result": None,
            "step2_result": None,
            "final_result": None,
            "metadata": {
                "workflow_id": "test_workflow_123",
                "timestamp": "2025-06-30T12:00:00Z"
            }
        }
