"""Comprehensive tests for flow_extractor.py error handling and edge cases."""

import tempfile
from pathlib import Path

import pytest

from quantalogic_flow.flow.flow_extractor import extract_workflow_from_file
from quantalogic_flow.flow.flow_manager_schema import WorkflowDefinition


class TestFlowExtractorErrorHandling:
    """Test flow extractor error handling and edge cases."""

    def test_extract_from_nonexistent_file(self):
        """Test extraction from non-existent file."""
        with pytest.raises(FileNotFoundError):
            extract_workflow_from_file("nonexistent_file.py")

    def test_extract_from_empty_file(self):
        """Test extraction from empty file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Write nothing to create empty file
            temp_file = f.name
        
        try:
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            # Should return basic workflow structure even for empty files
            assert isinstance(workflow_def, WorkflowDefinition)
            assert extracted_code == ""
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_from_invalid_python_syntax(self):
        """Test extraction from file with invalid Python syntax."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("invalid python syntax ++ -- @@")
            temp_file = f.name
        
        try:
            with pytest.raises(SyntaxError):
                extract_workflow_from_file(temp_file)
                
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_no_workflow_definition(self):
        """Test extraction from file with no workflow definition."""
        code = '''
def some_function():
    return "no workflow here"

x = 42
print("Hello world")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            # Should return basic workflow structure
            assert isinstance(workflow_def, WorkflowDefinition)
            assert "some_function" in extracted_code
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_complex_nested_expressions(self):
        """Test extraction with complex nested expressions."""
        code = '''
from quantalogic_flow.flow.flow import Workflow, Nodes

@Nodes.define(output="result1")
def complex_node(data):
    # Complex nested operations
    result = [
        {
            "key": [x for x in range(10) if x % 2 == 0],
            "nested": {
                "deep": lambda y: y * 2 if y > 5 else y + 1
            }
        } for i in range(3)
    ]
    return result

workflow = (Workflow("complex_node")
    .then("other_node")
    .branch([
        ("path1", lambda ctx: ctx.get("condition", False)),
        ("path2", lambda ctx: not ctx.get("condition", False))
    ])
    .converge("final_node"))
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            assert "complex_node" in workflow_def.nodes
            assert len(workflow_def.workflow.transitions) > 0
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_malformed_decorators(self):
        """Test extraction with malformed decorators."""
        code = '''
from quantalogic_flow.flow.flow import Workflow, Nodes

@Nodes.define()  # Missing required parameters
def malformed_node():
    return "test"

@Nodes.invalid_decorator  # Non-existent decorator
def another_node():
    return "test"

workflow = Workflow("malformed_node")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            # Should handle malformed decorators gracefully
            assert isinstance(workflow_def, WorkflowDefinition)
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_dynamic_workflow_construction(self):
        """Test extraction with dynamically constructed workflows."""
        code = '''
from quantalogic_flow.flow.flow import Workflow, Nodes

@Nodes.define(output="result")
def dynamic_node(input_data):
    return input_data * 2

# Dynamic workflow construction
workflow_name = "dynamic_node"
workflow = Workflow(workflow_name)

# Dynamic method calls
method_chain = ["then", "branch", "converge"]
for method in method_chain:
    if method == "then":
        workflow = workflow.then("next_node")
    elif method == "branch":
        workflow = workflow.branch([("path1", lambda ctx: True)])
    elif method == "converge":
        workflow = workflow.converge("final_node")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            assert "dynamic_node" in workflow_def.nodes
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_imports_and_complex_dependencies(self):
        """Test extraction with complex imports and dependencies."""
        code = '''
import os
import sys
from pathlib import Path
from typing import Dict, List, Any
from quantalogic_flow.flow.flow import Workflow, Nodes

# Complex imports
from some.complex.module import ComplexClass
import third_party_lib as tpl

@Nodes.define(output="processed_data")
def processor_node(data: Dict[str, Any]) -> List[Dict]:
    """Complex node with type hints and documentation."""
    processor = ComplexClass()
    result = tpl.process(data)
    return [{"processed": item} for item in result]

@Nodes.llm_node(
    model="gpt-4",
    prompt_template="Process this data: {{data}}",
    output="llm_result"
)
def llm_processor(data):
    pass

workflow = (Workflow("processor_node")
    .then("llm_processor")
    .start_loop()
    .then("loop_body")
    .end_loop(condition=lambda ctx: ctx.counter < 10, next_node="final_step")
    .then("final_step"))
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            assert "processor_node" in workflow_def.nodes
            assert "llm_processor" in workflow_def.nodes
            assert len(workflow_def.workflow.loops) > 0
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_deeply_nested_loops(self):
        """Test extraction with deeply nested loop structures."""
        code = '''
from quantalogic_flow.flow.flow import Workflow, Nodes

@Nodes.define(output="result")
def outer_loop_node(data):
    return data

@Nodes.define(output="middle_result")
def middle_loop_node(data):
    return data * 2

@Nodes.define(output="inner_result")
def inner_loop_node(data):
    return data + 1

workflow = (Workflow("outer_loop_node")
    .start_loop()  # Outer loop
        .then("middle_loop_node")
        .start_loop()  # Middle loop
            .then("inner_loop_node")
            .start_loop()  # Inner loop
                .then("deepest_node")
            .end_loop(condition=lambda ctx: ctx.inner_counter < 3, next_node="inner_exit")
            .then("inner_exit")
        .end_loop(condition=lambda ctx: ctx.middle_counter < 5, next_node="middle_exit")
        .then("middle_exit")
    .end_loop(condition=lambda ctx: ctx.outer_counter < 10, next_node="final_node")
    .then("final_node"))
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            assert len(workflow_def.workflow.loops) > 0
            
            # Check for nested loops
            outer_loop = workflow_def.workflow.loops[0]
            assert len(outer_loop.nested_loops) > 0
            
            middle_loop = outer_loop.nested_loops[0]
            assert len(middle_loop.nested_loops) > 0
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_complex_branch_conditions(self):
        """Test extraction with complex branching conditions."""
        code = '''
from quantalogic_flow.flow.flow import Workflow, Nodes

@Nodes.define(output="decision")
def decision_node(data):
    return {"score": data.get("value", 0) * 1.5}

def complex_condition(ctx):
    """Complex condition function."""
    return (ctx.get("score", 0) > 10 and 
            ctx.get("user_type") == "premium" and
            len(ctx.get("history", [])) > 5)

def another_condition(ctx):
    return ctx.get("fallback", False) or ctx.get("emergency", False)

workflow = (Workflow("decision_node")
    .branch([
        ("premium_path", complex_condition),
        ("standard_path", lambda ctx: ctx.get("user_type") == "standard"),
        ("fallback_path", another_condition)
    ])
    .converge("merge_point")
    .branch([
        ("final_path_a", lambda ctx: ctx.get("final_decision") == "A"),
        ("final_path_b", lambda ctx: ctx.get("final_decision") == "B"),
        ("final_path_c", lambda ctx: True)  # Default case
    ])
    .converge("final_result"))
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            assert "decision_node" in workflow_def.nodes
            assert len(workflow_def.workflow.convergence_nodes) >= 2
            
            # Check that branch conditions are properly extracted
            transitions = workflow_def.workflow.transitions
            branch_transitions = [t for t in transitions if isinstance(t.to_node, list)]
            assert len(branch_transitions) >= 2
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_mixed_node_types(self):
        """Test extraction with various node types mixed together."""
        code = '''
from quantalogic_flow.flow.flow import Workflow, Nodes

@Nodes.define(output="basic_result")
def basic_node(input_data):
    return input_data.upper()

@Nodes.llm_node(
    model="gpt-3.5-turbo",
    prompt_template="Analyze: {{data}}",
    system_prompt="You are a data analyst",
    output="analysis"
)
def analysis_node(data):
    pass

@Nodes.structured_llm_node(
    model="gpt-4",
    prompt_template="Extract info from: {{text}}",
    response_model="MyModel",
    output="structured_data"
)
def extraction_node(text):
    pass

@Nodes.template_node(
    template="Result: {{value}} - Status: {{status}}",
    output="formatted_result"
)
def formatting_node(rendered_content, value, status):
    return rendered_content

workflow = (Workflow("basic_node")
    .then("analysis_node")
    .parallel("extraction_node", "formatting_node")
    .converge("final_processing")
    .start_loop()
        .then("loop_processing")
    .end_loop(condition=lambda ctx: ctx.iterations < 3, next_node="completion")
    .then("completion"))
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            
            # Check different node types are present
            nodes = workflow_def.nodes
            assert "basic_node" in nodes
            assert "analysis_node" in nodes
            assert "extraction_node" in nodes
            assert "formatting_node" in nodes
            
            # Check that different configurations are preserved
            analysis_node = nodes["analysis_node"]
            assert analysis_node.llm_config is not None
            assert analysis_node.llm_config.model == "gpt-3.5-turbo"
            
            extraction_node = nodes["extraction_node"]
            assert extraction_node.llm_config is not None
            assert extraction_node.llm_config.response_model == "MyModel"
            
            formatting_node = nodes["formatting_node"]
            assert formatting_node.template_config is not None
            assert "Result:" in formatting_node.template_config.template
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_error_in_lambda_expression(self):
        """Test extraction with errors in lambda expressions."""
        code = '''
from quantalogic_flow.flow.flow import Workflow, Nodes

@Nodes.define(output="result")
def test_node(data):
    return data

# Lambda with syntax error - should be handled gracefully
workflow = (Workflow("test_node")
    .branch([
        ("path1", lambda ctx: ctx.invalid_syntax ++ error),  # Invalid syntax
        ("path2", lambda ctx: ctx.get("valid", True))
    ])
    .converge("final"))
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # Should not crash even with invalid lambda syntax
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            assert "test_node" in workflow_def.nodes
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_unicode_and_special_characters(self):
        """Test extraction with Unicode characters and special symbols."""
        code = '''
# -*- coding: utf-8 -*-
from quantalogic_flow.flow.flow import Workflow, Nodes

@Nodes.define(output="résultat")  # Unicode in parameter
def nœud_spécial(données):  # Unicode in function name and parameter
    """Traitement avec caractères spéciaux: àáâãäåæçèéêë"""
    return f"Processed: {données} with special chars: ñáéíóú"

@Nodes.llm_node(
    model="gpt-4",
    prompt_template="Analysez ces données: {{données}} 🔍📊",  # Emojis
    output="analyse_unicode"
)
def analyseur_unicode(données):
    pass

workflow = (Workflow("nœud_spécial")
    .then("analyseur_unicode")
    .branch([
        ("chemin_ñ", lambda ctx: "ñ" in str(ctx.get("data", ""))),
        ("chemin_默认", lambda ctx: True)  # Chinese characters
    ])
    .converge("final_ñódé"))
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name
        
        try:
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            # Should handle Unicode in node names
            assert any("nœud" in name or "special" in name for name in workflow_def.nodes.keys())
            
        finally:
            Path(temp_file).unlink(missing_ok=True)
