"""Unit tests for Nodes class and decorators."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from quantalogic_flow.flow.flow import Nodes


class TestNodes:
    """Test Nodes class and decorators."""

    def test_nodes_registry_initialization(self):
        """Test that the NODE_REGISTRY is properly initialized."""
        assert isinstance(Nodes.NODE_REGISTRY, dict)
    
    def test_define_decorator_basic(self, nodes_registry_backup):
        """Test basic @Nodes.define decorator."""
        @Nodes.define(output="test_output")
        def simple_node(input_param):
            return f"processed: {input_param}"
        
        # Check node is registered
        assert "simple_node" in Nodes.NODE_REGISTRY
        func, inputs, output = Nodes.NODE_REGISTRY["simple_node"]
        
        assert inputs == ["input_param"]
        assert output == "test_output"
        assert callable(func)
    
    def test_define_decorator_no_output(self, nodes_registry_backup):
        """Test @Nodes.define decorator without output specification."""
        @Nodes.define()
        def no_output_node(param1, param2):
            return {"result": param1 + param2}
        
        assert "no_output_node" in Nodes.NODE_REGISTRY
        func, inputs, output = Nodes.NODE_REGISTRY["no_output_node"]
        
        assert inputs == ["param1", "param2"]
        assert output is None
    
    def test_define_decorator_multiple_params(self, nodes_registry_backup):
        """Test @Nodes.define decorator with multiple parameters."""
        @Nodes.define(output="multi_output")
        def multi_param_node(param1, param2, param3):
            return f"{param1}-{param2}-{param3}"
        
        func, inputs, output = Nodes.NODE_REGISTRY["multi_param_node"]
        assert inputs == ["param1", "param2", "param3"]
        assert output == "multi_output"
    
    async def test_define_decorator_async_function(self, nodes_registry_backup):
        """Test @Nodes.define decorator with async function."""
        @Nodes.define(output="async_output")
        async def async_node(input_data):
            return f"async processed: {input_data}"
        
        func, inputs, output = Nodes.NODE_REGISTRY["async_node"]
        assert inputs == ["input_data"]
        assert output == "async_output"
        
        # Test execution
        result = await func(input_data="test")
        assert result == "async processed: test"
    
    async def test_define_decorator_sync_function(self, nodes_registry_backup):
        """Test @Nodes.define decorator with sync function."""
        @Nodes.define(output="sync_output")
        def sync_node(input_data):
            return f"sync processed: {input_data}"
        
        func, inputs, output = Nodes.NODE_REGISTRY["sync_node"]
        
        # Test execution of wrapped async function
        result = await func(input_data="test")
        assert result == "sync processed: test"
    
    def test_validate_node_decorator(self, nodes_registry_backup):
        """Test @Nodes.validate_node decorator."""
        @Nodes.validate_node(output="validation_result")
        def validator_node(data_to_validate):
            if data_to_validate:
                return "valid"
            return "invalid"
        
        func, inputs, output = Nodes.NODE_REGISTRY["validator_node"]
        assert inputs == ["data_to_validate"]
        assert output == "validation_result"
    
    async def test_validate_node_string_return(self, nodes_registry_backup):
        """Test validate_node ensures string return."""
        @Nodes.validate_node(output="validation_result")
        def string_validator(data):
            return "validation passed"
        
        func, _, _ = Nodes.NODE_REGISTRY["string_validator"]
        result = await func(data="test")
        assert result == "validation passed"
    
    async def test_validate_node_non_string_return_fails(self, nodes_registry_backup):
        """Test validate_node fails with non-string return."""
        @Nodes.validate_node(output="validation_result")
        def bad_validator(data):
            return 123  # Not a string
        
        func, _, _ = Nodes.NODE_REGISTRY["bad_validator"]
        with pytest.raises(ValueError, match="must return a string"):
            await func(data="test")
    
    def test_transform_node_decorator(self, nodes_registry_backup):
        """Test @Nodes.transform_node decorator."""
        def uppercase_transformer(value):
            return value.upper()
        
        @Nodes.transform_node(output="transformed_output", transformer=uppercase_transformer)
        def transform_node(text_input):
            return f"transformed: {text_input}"
        
        func, inputs, output = Nodes.NODE_REGISTRY["transform_node"]
        assert inputs == ["text_input"]
        assert output == "transformed_output"
    
    async def test_transform_node_execution(self, nodes_registry_backup):
        """Test transform_node decorator execution."""
        def double_transformer(value):
            return value * 2
        
        @Nodes.transform_node(output="doubled_output", transformer=double_transformer)
        def doubler_node(number_input):
            return f"result: {number_input}"
        
        func, _, _ = Nodes.NODE_REGISTRY["doubler_node"]
        result = await func(number_input=5)
        assert result == "result: 10"  # 5 * 2 = 10
    
    @patch("quantalogic_react.quantalogic.quantlitellm.acompletion")
    async def test_llm_node_decorator_basic(self, mock_acompletion, nodes_registry_backup):
        """Test basic @Nodes.llm_node decorator."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "LLM generated response"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        mock_acompletion.return_value = mock_response
        
        @Nodes.llm_node(
            system_prompt="You are a helpful assistant",
            prompt_template="Process this: {{ input_text }}",
            output="llm_output",
            model="gpt-3.5-turbo"
        )
        def llm_test_node(input_text):
            pass  # LLM decorator handles the logic
        
        func, inputs, output = Nodes.NODE_REGISTRY["llm_test_node"]
        assert inputs == ["input_text"]
        assert output == "llm_output"
        
        # Test execution
        result = await func(input_text="Hello world")
        assert result == "LLM generated response"
        
        # Verify LLM was called correctly
        mock_acompletion.assert_called_once()
        call_args = mock_acompletion.call_args
        assert call_args[1]["model"] == "gpt-3.5-turbo"
        assert len(call_args[1]["messages"]) == 2
        assert call_args[1]["messages"][0]["role"] == "system"
        assert call_args[1]["messages"][1]["role"] == "user"
    
    @patch("quantalogic_react.quantalogic.quantlitellm.acompletion")
    async def test_llm_node_with_callable_model(self, mock_acompletion, nodes_registry_backup):
        """Test LLM node with callable model parameter."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Dynamic model response"
        mock_response.usage.prompt_tokens = 15
        mock_response.usage.completion_tokens = 25
        mock_response.usage.total_tokens = 40
        mock_acompletion.return_value = mock_response
        
        def dynamic_model(ctx):
            return "gpt-4" if ctx.get("use_gpt4") else "gpt-3.5-turbo"
        
        @Nodes.llm_node(
            prompt_template="Dynamic prompt: {{ query }}",
            output="dynamic_output",
            model=dynamic_model
        )
        def dynamic_llm_node(query, use_gpt4=False):
            pass
        
        func, _, _ = Nodes.NODE_REGISTRY["dynamic_llm_node"]
        
        # Test with gpt-3.5-turbo
        await func(query="test", use_gpt4=False)
        assert mock_acompletion.call_args[1]["model"] == "gpt-3.5-turbo"
        
        # Test with gpt-4
        await func(query="test", use_gpt4=True)
        assert mock_acompletion.call_args[1]["model"] == "gpt-4"
    
    @patch("quantalogic_flow.flow.nodes.instructor.from_litellm")
    async def test_structured_llm_node(self, mock_instructor, nodes_registry_backup):
        """Test @Nodes.structured_llm_node decorator."""
        
        class TestResponse(BaseModel):
            answer: str
            confidence: float
        
        # Setup mocks
        mock_client = MagicMock()
        mock_instructor.return_value = mock_client
        
        structured_response = TestResponse(answer="Structured answer", confidence=0.95)
        mock_raw_response = MagicMock()
        mock_raw_response.usage.prompt_tokens = 12
        mock_raw_response.usage.completion_tokens = 18
        mock_raw_response.usage.total_tokens = 30
        
        mock_client.chat.completions.create_with_completion = AsyncMock(
            return_value=(structured_response, mock_raw_response)
        )
        
        @Nodes.structured_llm_node(
            prompt_template="Analyze: {{ data }}",
            response_model=TestResponse,
            output="structured_output"
        )
        def structured_node(data):
            pass
        
        func, inputs, output = Nodes.NODE_REGISTRY["structured_node"]
        assert inputs == ["data"]
        assert output == "structured_output"
        
        # Test execution
        result = await func(data="test data")
        assert isinstance(result, TestResponse)
        assert result.answer == "Structured answer"
        assert result.confidence == 0.95
    
    def test_template_node_decorator(self, nodes_registry_backup):
        """Test @Nodes.template_node decorator."""
        @Nodes.template_node(
            output="template_output",
            template="Hello {{ name }}, you have {{ count }} items."
        )
        def template_test_node(rendered_content, name, count):
            return rendered_content
        
        func, inputs, output = Nodes.NODE_REGISTRY["template_test_node"]
        assert "rendered_content" in inputs
        assert "name" in inputs
        assert "count" in inputs
        assert output == "template_output"
    
    async def test_template_node_execution(self, nodes_registry_backup):
        """Test template_node execution with Jinja2 rendering."""
        @Nodes.template_node(
            output="rendered_output",
            template="User: {{ user }}, Items: {% for item in items %}{{ item }}{% if not loop.last %}, {% endif %}{% endfor %}"
        )
        def complex_template_node(rendered_content, user, items):
            return rendered_content
        
        func, _, _ = Nodes.NODE_REGISTRY["complex_template_node"]
        result = await func(user="Alice", items=["apple", "banana", "cherry"])
        assert "User: Alice" in result
        assert "apple, banana, cherry" in result
    
    def test_node_registration_persistence(self, nodes_registry_backup):
        """Test that node registration persists across multiple decorators."""
        @Nodes.define(output="output1")
        def node1(param1):
            return param1
        
        @Nodes.define(output="output2")
        def node2(param2):
            return param2
        
        assert "node1" in Nodes.NODE_REGISTRY
        assert "node2" in Nodes.NODE_REGISTRY
        assert len(Nodes.NODE_REGISTRY) >= 2
    
    async def test_node_error_handling(self, nodes_registry_backup):
        """Test error handling in node execution."""
        @Nodes.define(output="error_output")
        def error_node(data):
            raise ValueError("Test error")
        
        func, _, _ = Nodes.NODE_REGISTRY["error_node"]
        
        with pytest.raises(ValueError, match="Test error"):
            await func(data="test")

    @patch("quantalogic_react.quantalogic.quantlitellm.acompletion")
    async def test_poe_provider_integration(self, mock_acompletion, nodes_registry_backup):
        """Test POE provider integration through LLM nodes."""
        # Setup mock response for POE model
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "POE API response"
        mock_response.usage.prompt_tokens = 12
        mock_response.usage.completion_tokens = 18
        mock_response.usage.total_tokens = 30
        mock_acompletion.return_value = mock_response

        @Nodes.llm_node(
            system_prompt="You are Claude via POE API",
            prompt_template="Analyze: {{ text }}",
            output="poe_analysis",
            model="poe/Claude-Sonnet-4"
        )
        def poe_analysis_node(text):
            pass  # LLM decorator handles the logic

        func, inputs, output = Nodes.NODE_REGISTRY["poe_analysis_node"]
        assert inputs == ["text"]
        assert output == "poe_analysis"

        # Test execution with POE model
        result = await func(text="test input")
        assert result == "POE API response"

        # Verify the model was passed correctly
        mock_acompletion.assert_called_once()
        call_args = mock_acompletion.call_args
        assert call_args[1]["model"] == "poe/Claude-Sonnet-4"
        assert len(call_args[1]["messages"]) == 2
        assert call_args[1]["messages"][0]["content"] == "You are Claude via POE API"
        assert "Analyze: test input" in call_args[1]["messages"][1]["content"]
