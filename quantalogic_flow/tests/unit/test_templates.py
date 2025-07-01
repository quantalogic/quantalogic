"""Unit tests for template functionality."""

import tempfile
from pathlib import Path

import pytest

from quantalogic_flow.flow.flow import Nodes


class TestTemplateRendering:
    """Test template rendering functionality."""
    
    def test_render_simple_template(self):
        """Test rendering a simple Jinja2 template."""
        template = "Hello {{ name }}!"
        context = {"name": "World"}
        
        result = Nodes._render_template(template, None, context)
        assert result == "Hello World!"
    
    def test_render_complex_template(self):
        """Test rendering a complex template with loops and conditions."""
        template = """
        User: {{ user }}
        {% if items %}
        Items:
        {% for item in items %}
        - {{ item }}
        {% endfor %}
        {% else %}
        No items available.
        {% endif %}
        """.strip()
        
        context = {
            "user": "Alice",
            "items": ["apple", "banana", "cherry"]
        }
        
        result = Nodes._render_template(template, None, context)
        
        assert "User: Alice" in result
        assert "- apple" in result
        assert "- banana" in result
        assert "- cherry" in result
        assert "No items available" not in result
    
    def test_render_template_empty_items(self):
        """Test template rendering with empty items list."""
        template = """
        {% if items %}
        Items: {{ items|length }}
        {% else %}
        No items found.
        {% endif %}
        """
        
        context = {"items": []}
        result = Nodes._render_template(template, None, context)
        assert "No items found" in result
    
    def test_render_template_with_filters(self):
        """Test template rendering with Jinja2 filters."""
        template = "{{ message|upper }} - {{ count|default('N/A') }}"
        context = {"message": "hello world"}
        
        result = Nodes._render_template(template, None, context)
        assert result == "HELLO WORLD - N/A"
    
    def test_render_template_missing_variable(self):
        """Test template rendering with missing variables."""
        template = "Hello {{ name }}! You have {{ count }} items."
        context = {"name": "User"}  # Missing 'count'
        
        # Jinja2 should handle missing variables gracefully
        result = Nodes._render_template(template, None, context)
        assert "Hello User!" in result
    
    def test_load_template_from_file(self):
        """Test loading and rendering template from file."""
        template_content = """
# Processing Report

User: {{ user_name }}
Date: {{ date }}
Status: {{ status|default('unknown') }}

{% if results %}
Results:
{% for result in results %}
- {{ result.name }}: {{ result.value }}
{% endfor %}
{% endif %}
        """.strip()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            template_file = Path(temp_dir) / "test_template.j2"
            template_file.write_text(template_content)
            
            context = {
                "user_name": "TestUser",
                "date": "2025-06-30",
                "status": "completed",
                "results": [
                    {"name": "test1", "value": "success"},
                    {"name": "test2", "value": "failure"}
                ]
            }
            
            result = Nodes._load_prompt_from_file(str(template_file), context)
            
            assert "User: TestUser" in result
            assert "Date: 2025-06-30" in result
            assert "Status: completed" in result
            assert "- test1: success" in result
            assert "- test2: failure" in result
    
    def test_load_template_file_not_found(self):
        """Test loading template from non-existent file."""
        with pytest.raises(ValueError, match="Prompt file .* not found"):
            Nodes._load_prompt_from_file("nonexistent_template.j2", {})
    
    def test_render_template_file_priority(self):
        """Test that template_file takes priority over template string."""
        template_content = "File template: {{ message }}"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            template_file = Path(temp_dir) / "priority_test.j2"
            template_file.write_text(template_content)
            
            context = {"message": "from file"}
            
            result = Nodes._render_template(
                template="String template: {{ message }}",
                template_file=str(template_file),
                context=context
            )
            
            assert result == "File template: from file"
    
    async def test_template_node_basic(self, nodes_registry_backup):
        """Test basic template node functionality."""
        @Nodes.template_node(
            output="greeting",
            template="Hello {{ name }}, welcome to {{ place }}!"
        )
        def greeting_node(rendered_content, name, place):
            return rendered_content
        
        func, inputs, output = Nodes.NODE_REGISTRY["greeting_node"]
        assert "rendered_content" in inputs
        assert "name" in inputs  
        assert "place" in inputs
        assert output == "greeting"
        
        result = await func(name="Alice", place="Wonderland")
        assert result == "Hello Alice, welcome to Wonderland!"
    
    async def test_template_node_with_file(self, nodes_registry_backup):
        """Test template node with external template file."""
        template_content = "Report for {{ user }}: {{ summary }}"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            template_file = Path(temp_dir) / "report_template.j2"
            template_file.write_text(template_content)
            
            @Nodes.template_node(
                output="report",
                template_file=str(template_file)
            )
            def report_node(rendered_content, user, summary):
                return rendered_content
            
            func, _, _ = Nodes.NODE_REGISTRY["report_node"]
            result = await func(user="TestUser", summary="All tests passed")
            
            assert result == "Report for TestUser: All tests passed"
    
    async def test_template_node_complex_data(self, nodes_registry_backup):
        """Test template node with complex nested data."""
        template = """
# Analysis Report

Analyst: {{ analyst.name }}
Department: {{ analyst.department }}

## Findings
{% for finding in findings %}
### {{ finding.title }}
- Impact: {{ finding.impact }}
- Recommendation: {{ finding.recommendation }}
{% endfor %}

## Summary
Total findings: {{ findings|length }}
Critical issues: {{ findings|selectattr('impact', 'equalto', 'critical')|list|length }}
        """.strip()
        
        @Nodes.template_node(
            output="analysis_report",
            template=template
        )
        def analysis_node(rendered_content, analyst, findings):
            return rendered_content
        
        func, _, _ = Nodes.NODE_REGISTRY["analysis_node"]
        
        context_data = {
            "analyst": {
                "name": "Dr. Smith",
                "department": "Data Science"
            },
            "findings": [
                {
                    "title": "Data Quality Issue",
                    "impact": "critical",
                    "recommendation": "Implement validation"
                },
                {
                    "title": "Performance Bottleneck",
                    "impact": "medium",
                    "recommendation": "Optimize queries"
                }
            ]
        }
        
        result = await func(**context_data)
        
        assert "Analyst: Dr. Smith" in result
        assert "Department: Data Science" in result
        assert "Data Quality Issue" in result
        assert "Performance Bottleneck" in result
        assert "Total findings: 2" in result
        assert "Critical issues: 1" in result
    
    def test_template_error_handling(self):
        """Test template error handling for malformed templates."""
        malformed_template = "Hello {{ name"  # Missing closing brace
        context = {"name": "Test"}
        
        with pytest.raises(Exception):  # Jinja2 will raise a template syntax error
            Nodes._render_template(malformed_template, None, context)
    
    async def test_template_node_with_missing_context(self, nodes_registry_backup):
        """Test template node behavior with missing context variables."""
        @Nodes.template_node(
            output="incomplete_template",
            template="Hello {{ name }}, you have {{ missing_var }} items."
        )
        def incomplete_node(rendered_content, name):
            return rendered_content
        
        func, _, _ = Nodes.NODE_REGISTRY["incomplete_node"]
        
        # Should not fail, but missing_var will be empty
        result = await func(name="TestUser")
        assert "Hello TestUser" in result
        assert "you have  items" in result  # Empty missing_var
    
    def test_template_with_custom_filters(self):
        """Test template rendering behavior with Jinja2 built-in filters."""
        template = """
        Name: {{ name|title }}
        Items: {{ items|join(', ') }}
        Count: {{ items|length }}
        First: {{ items|first|default('None') }}
        Last: {{ items|last|default('None') }}
        """
        
        context = {
            "name": "john doe",
            "items": ["apple", "banana", "cherry"]
        }
        
        result = Nodes._render_template(template, None, context)
        
        assert "Name: John Doe" in result
        assert "Items: apple, banana, cherry" in result
        assert "Count: 3" in result
        assert "First: apple" in result
        assert "Last: cherry" in result
