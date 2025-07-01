"""Integration tests for workflow execution."""

from unittest.mock import patch

import pytest

from quantalogic_flow.flow.flow import Nodes, Workflow, WorkflowEventType
from tests.mocks import MockLLMResponse


class TestWorkflowIntegration:
    """Integration tests for complete workflow execution."""
    
    @pytest.mark.integration
    async def test_simple_data_processing_workflow(self, nodes_registry_backup):
        """Test a simple data processing workflow."""
        @Nodes.define(output="cleaned_data")
        def clean_data(raw_data):
            return raw_data.strip().lower()
        
        @Nodes.define(output="processed_data")
        def process_data(cleaned_data):
            return f"processed: {cleaned_data}"
        
        @Nodes.define(output="final_result")
        def finalize_data(processed_data):
            return f"final: {processed_data}"
        
        # Build workflow
        workflow = Workflow("clean_data")
        workflow.sequence("process_data", "finalize_data")
        
        engine = workflow.build()
        result = await engine.run({"raw_data": "  HELLO WORLD  "})
        
        assert result["cleaned_data"] == "hello world"
        assert result["processed_data"] == "processed: hello world"
        assert result["final_result"] == "final: processed: hello world"
    
    @pytest.mark.integration
    async def test_conditional_branching_workflow(self, nodes_registry_backup):
        """Test workflow with conditional branching."""
        @Nodes.define(output="analysis_result")
        def analyze_data(input_value):
            return {
                "value": input_value,
                "is_positive": input_value > 0,
                "magnitude": abs(input_value)
            }
        
        @Nodes.define(output="positive_processing")
        def process_positive(analysis_result):
            return f"positive processing: {analysis_result['magnitude']}"
        
        @Nodes.define(output="negative_processing")
        def process_negative(analysis_result):
            return f"negative processing: {analysis_result['magnitude']}"
        
        @Nodes.define(output="zero_processing")
        def process_zero(analysis_result):
            return "zero processing: neutral value"
        
        def is_positive(ctx):
            return ctx.get("analysis_result", {}).get("is_positive", False)
        
        def is_zero(ctx):
            return ctx.get("analysis_result", {}).get("value", 1) == 0
        
        # Build branching workflow
        workflow = Workflow("analyze_data")
        workflow.branch([
            ("process_positive", is_positive),
            ("process_zero", is_zero)
        ], default="process_negative")
        
        # Test positive value
        engine = workflow.build()
        result = await engine.run({"input_value": 42})
        assert "positive_processing" in result
        assert result["positive_processing"] == "positive processing: 42"
        
        # Test negative value
        engine = workflow.build()
        result = await engine.run({"input_value": -15})
        assert "negative_processing" in result
        assert result["negative_processing"] == "negative processing: 15"
        
        # Test zero value
        engine = workflow.build()
        result = await engine.run({"input_value": 0})
        assert "zero_processing" in result
        assert result["zero_processing"] == "zero processing: neutral value"
    
    @pytest.mark.integration
    @patch("quantalogic_flow.flow.flow.acompletion")
    async def test_llm_workflow_integration(self, mock_acompletion, nodes_registry_backup):
        """Test workflow integration with LLM nodes."""
        # Setup LLM mocks
        mock_acompletion.side_effect = [
            MockLLMResponse("Summarized: Important information extracted"),
            MockLLMResponse("Validated: The summary is accurate and complete")
        ]
        
        @Nodes.define(output="prepared_text")
        def prepare_text(raw_text):
            return f"Prepared: {raw_text.strip()}"
        
        @Nodes.llm_node(
            system_prompt="You are a text summarizer",
            prompt_template="Summarize this text: {{ prepared_text }}",
            output="summary",
            model="gpt-3.5-turbo"
        )
        def summarize_text(prepared_text):
            pass
        
        @Nodes.llm_node(
            system_prompt="You are a quality validator",
            prompt_template="Validate this summary: {{ summary }}",
            output="validation",
            model="gpt-3.5-turbo"
        )
        def validate_summary(summary):
            pass
        
        @Nodes.define(output="final_output")
        def format_output(summary, validation):
            return {
                "summary": summary,
                "validation": validation,
                "status": "completed"
            }
        
        # Build LLM workflow
        workflow = Workflow("prepare_text")
        workflow.sequence("summarize_text", "validate_summary", "format_output")
        
        engine = workflow.build()
        result = await engine.run({"raw_text": "  This is a long document...  "})
        
        assert result["prepared_text"] == "Prepared: This is a long document..."
        assert result["summary"] == "Summarized: Important information extracted"
        assert result["validation"] == "Validated: The summary is accurate and complete"
        assert result["final_output"]["status"] == "completed"
        
        # Verify LLM was called correctly
        assert mock_acompletion.call_count == 2
    
    @pytest.mark.integration
    async def test_template_workflow_integration(self, nodes_registry_backup):
        """Test workflow integration with template nodes."""
        @Nodes.define(output="user_data")
        def fetch_user_data(user_id):
            return {
                "id": user_id,
                "name": "John Doe",
                "email": "john@example.com",
                "preferences": ["email", "sms"]
            }
        
        @Nodes.template_node(
            output="email_content",
            template="""
Subject: Welcome {{ user_data.name }}!

Dear {{ user_data.name }},

Thank you for registering with user ID: {{ user_data.id }}
Your email: {{ user_data.email }}

Preferences:
{% for pref in user_data.preferences %}
- {{ pref }}
{% endfor %}

Best regards,
The Team
            """.strip()
        )
        def generate_email(rendered_content, user_data):
            return rendered_content
        
        @Nodes.define(output="email_sent")
        def send_email(email_content, user_data):
            return {
                "sent_to": user_data["email"],
                "subject": "Welcome notification",
                "status": "delivered",
                "content_length": len(email_content)
            }
        
        # Build template workflow
        workflow = Workflow("fetch_user_data")
        workflow.sequence("generate_email", "send_email")
        
        engine = workflow.build()
        result = await engine.run({"user_id": "user_123"})
        
        assert "John Doe" in result["email_content"]
        assert "user_123" in result["email_content"]
        assert "john@example.com" in result["email_content"]
        assert "- email" in result["email_content"]
        assert "- sms" in result["email_content"]
        
        assert result["email_sent"]["sent_to"] == "john@example.com"
        assert result["email_sent"]["status"] == "delivered"
    
    @pytest.mark.integration
    async def test_observer_integration(self, nodes_registry_backup):
        """Test workflow execution with event observers."""
        @Nodes.define(output="step1")
        def step1_node(input_data):
            return f"step1: {input_data}"
        
        @Nodes.define(output="step2")
        def step2_node(step1):
            return f"step2: {step1}"
        
        @Nodes.define(output="final")
        def final_node(step2):
            return f"final: {step2}"
        
        # Build workflow with observers
        workflow = Workflow("step1_node")
        workflow.sequence("step2_node", "final_node")
        
        events = []
        def event_collector(event):
            events.append(event)
        
        engine = workflow.build()
        engine.add_observer(event_collector)
        
        result = await engine.run({"input_data": "test"})
        
        # Verify workflow execution
        assert result["final"] == "final: step2: step1: test"
        
        # Verify events were collected
        assert len(events) > 0
        
        event_types = [e.event_type for e in events]
        assert WorkflowEventType.WORKFLOW_STARTED in event_types
        assert WorkflowEventType.WORKFLOW_COMPLETED in event_types
        
        # Count node events
        node_started_events = [e for e in events if e.event_type == WorkflowEventType.NODE_STARTED]
        node_completed_events = [e for e in events if e.event_type == WorkflowEventType.NODE_COMPLETED]
        
        assert len(node_started_events) == 3  # Three nodes
        assert len(node_completed_events) == 3  # Three nodes
        
        # Verify event data
        for event in node_completed_events:
            assert event.result is not None
            assert event.node_name in ["step1_node", "step2_node", "final_node"]
    
    @pytest.mark.integration
    async def test_error_recovery_workflow(self, nodes_registry_backup):
        """Test workflow error handling and recovery."""
        @Nodes.define(output="input_validation")
        def validate_input(data):
            if not data or len(data) < 3:
                raise ValueError("Input data too short")
            return f"validated: {data}"
        
        @Nodes.define(output="error_handled")
        def handle_error(error_info):
            return f"error handled: {error_info}"
        
        @Nodes.define(output="success_processed")
        def process_success(input_validation):
            return f"success: {input_validation}"
        
        # Test error case
        workflow = Workflow("validate_input")
        engine = workflow.build()
        
        events = []
        def event_collector(event):
            events.append(event)
        
        engine.add_observer(event_collector)
        
        with pytest.raises(ValueError, match="Input data too short"):
            await engine.run({"data": "hi"})
        
        # Verify error event was generated
        error_events = [e for e in events if e.event_type == WorkflowEventType.NODE_FAILED]
        assert len(error_events) == 1
        assert isinstance(error_events[0].exception, ValueError)
        
        # Test success case
        workflow_success = Workflow("validate_input")
        workflow_success.then("process_success")
        engine_success = workflow_success.build()
        
        result = await engine_success.run({"data": "valid input"})
        assert result["success_processed"] == "success: validated: valid input"
    
    @pytest.mark.integration
    async def test_complex_workflow_with_multiple_patterns(self, nodes_registry_backup):
        """Test complex workflow combining multiple patterns."""
        @Nodes.define(output="preprocessed")
        def preprocess_data(raw_input):
            return {
                "text": raw_input.strip().lower(),
                "length": len(raw_input.strip()),
                "words": len(raw_input.strip().split())
            }
        
        @Nodes.define(output="analysis")
        def analyze_data(preprocessed):
            return {
                "is_long": preprocessed["length"] > 20,
                "word_count": preprocessed["words"],
                "complexity": "high" if preprocessed["words"] > 10 else "low"
            }
        
        @Nodes.template_node(
            output="short_report",
            template="Short text analysis: {{ analysis.word_count }} words, {{ analysis.complexity }} complexity"
        )
        def generate_short_report(rendered_content, analysis):
            return rendered_content
        
        @Nodes.template_node(
            output="long_report",
            template="""
Long Text Analysis Report
=======================
Word Count: {{ analysis.word_count }}
Complexity: {{ analysis.complexity }}
Original Length: {{ preprocessed.length }} characters

Text Preview: {{ preprocessed.text[:50] }}...
            """.strip()
        )
        def generate_long_report(rendered_content, analysis, preprocessed):
            return rendered_content
        
        @Nodes.define(output="final_summary")
        def create_summary(short_report=None, long_report=None, analysis=None):
            report = long_report if long_report else short_report
            return {
                "report": report,
                "metadata": {
                    "report_type": "long" if long_report else "short",
                    "analysis": analysis
                }
            }
        
        def is_long_text(ctx):
            return ctx.get("analysis", {}).get("is_long", False)
        
        # Build complex workflow
        workflow = Workflow("preprocess_data")
        workflow.sequence("analyze_data")
        workflow.branch([
            ("generate_long_report", is_long_text)
        ], default="generate_short_report")
        workflow.converge("create_summary")
        
        # Test short text
        engine = workflow.build()
        short_result = await engine.run({"raw_input": "  Short Text  "})
        
        assert short_result["final_summary"]["metadata"]["report_type"] == "short"
        assert "Short text analysis" in short_result["final_summary"]["report"]
        
        # Test long text
        engine = workflow.build()
        long_input = "This is a very long piece of text with many words to trigger the long report generation"
        long_result = await engine.run({"raw_input": long_input})
        
        assert long_result["final_summary"]["metadata"]["report_type"] == "long"
        assert "Long Text Analysis Report" in long_result["final_summary"]["report"]
