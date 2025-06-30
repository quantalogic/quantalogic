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
            # extracted_code is a dict of constants/variables extracted from the file
            assert isinstance(extracted_code, dict)
            
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
            # Check if extracted_code contains the constant x
            assert isinstance(extracted_code, dict)
            assert "x" in extracted_code and extracted_code["x"] == 42
            
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

# Dynamic workflow construction with literal string
workflow = Workflow("dynamic_node")

# Static method calls for extractability
workflow = workflow.then("next_node")
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

    def test_extract_with_invalid_unicode_encoding(self):
        """Test extraction with invalid Unicode encoding."""
        # Create file with invalid encoding
        invalid_content = b"def test_node():\n    return '\xff\xfe invalid unicode'"
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.py', delete=False) as f:
            f.write(invalid_content)
            temp_file = f.name
        
        try:
            # Should handle encoding errors gracefully
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            # May have empty or partial code due to encoding issues
            
        except UnicodeDecodeError:
            # Acceptable if encoding error is raised
            pass
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_deeply_nested_imports(self):
        """Test extraction with deeply nested import structures."""
        code = '''
from quantalogic_flow.flow.flow import Workflow, Nodes
from some.deeply.nested.module.levels import ComplexClass
from another.complex.path import (
    MultipleImports,
    WithParentheses,
    SpanningMultipleLines
)
import yet.another.module as alias

try:
    from conditional.imports import ConditionalClass
except ImportError:
    ConditionalClass = None

@Nodes.define(output="result")
def complex_import_node():
    if ConditionalClass:
        return ComplexClass().process()
    return "fallback"

workflow = Workflow("complex_import_node")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            assert "complex_import_node" in workflow_def.nodes
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_metaclass_and_decorators(self):
        """Test extraction with complex metaclass and decorator patterns."""
        code = '''
from quantalogic_flow.flow.flow import Workflow, Nodes
from abc import ABCMeta, abstractmethod

class MetaNode(type):
    def __new__(cls, name, bases, attrs):
        return super().__new__(cls, name, bases, attrs)

class AbstractNode(metaclass=MetaNode):
    @abstractmethod
    def process(self):
        pass

@Nodes.define(output="meta_result")
class ConcreteNode(AbstractNode):
    def process(self):
        return "processed"

def concrete_node_wrapper():
    node = ConcreteNode()
    return node.process()

workflow = Workflow("concrete_node_wrapper")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            # Should handle complex class structures
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_async_generators_and_context_managers(self):
        """Test extraction with async generators and context managers."""
        code = '''
from quantalogic_flow.flow.flow import Workflow, Nodes
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def async_context():
    print("entering")
    try:
        yield "context_value"
    finally:
        print("exiting")

async def async_generator():
    for i in range(3):
        yield f"item_{i}"
        await asyncio.sleep(0.1)

@Nodes.define(output="async_result")
async def async_complex_node():
    async with async_context() as context:
        results = []
        async for item in async_generator():
            results.append(f"{context}_{item}")
        return results

workflow = Workflow("async_complex_node")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            assert "async_complex_node" in workflow_def.nodes
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_lambda_and_functional_programming(self):
        """Test extraction with lambda functions and functional programming constructs."""
        code = '''
from quantalogic_flow.flow.flow import Workflow, Nodes
from functools import reduce, partial
from operator import add

# Complex lambda expressions
transform_data = lambda x: list(map(lambda item: item * 2, filter(lambda n: n > 0, x)))
reduce_data = partial(reduce, add)

@Nodes.define(output="functional_result")
def functional_node(data):
    # Nested lambda and functional operations
    processed = transform_data(data)
    aggregated = reduce_data(processed, 0)
    
    # Lambda with complex conditions
    complex_lambda = lambda ctx: (
        ctx.get("value", 0) > 10 and
        any(isinstance(item, (int, float)) for item in ctx.get("items", [])) and
        all(key in ctx for key in ["required_key1", "required_key2"])
    )
    
    return {
        "processed": processed,
        "aggregated": aggregated,
        "condition_result": complex_lambda({"value": 15, "items": [1, 2, 3], "required_key1": True, "required_key2": True})
    }

workflow = (Workflow("functional_node")
    .branch([
        ("high_value", lambda ctx: ctx.get("functional_result", {}).get("aggregated", 0) > 100),
        ("low_value", lambda ctx: ctx.get("functional_result", {}).get("aggregated", 0) <= 100)
    ]))
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            assert "functional_node" in workflow_def.nodes
            assert len(workflow_def.workflow.transitions) > 0
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_exception_handling_patterns(self):
        """Test extraction with complex exception handling patterns."""
        code = '''
from quantalogic_flow.flow.flow import Workflow, Nodes
import logging

class CustomException(Exception):
    pass

class AnotherCustomException(CustomException):
    pass

@Nodes.define(output="exception_result")
def exception_handling_node(data):
    try:
        if data.get("trigger_error"):
            raise CustomException("Triggered error")
        elif data.get("trigger_nested_error"):
            try:
                raise AnotherCustomException("Nested error")
            except AnotherCustomException as e:
                logging.error(f"Nested exception: {e}")
                raise
        else:
            return "success"
    except CustomException as e:
        logging.warning(f"Custom exception: {e}")
        return "handled_error"
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return "unexpected_error"
    finally:
        logging.info("Cleanup completed")

workflow = (Workflow("exception_handling_node")
    .branch([
        ("success_path", lambda ctx: ctx.get("exception_result") == "success"),
        ("error_path", lambda ctx: "error" in ctx.get("exception_result", ""))
    ])
    .converge("final_node"))
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            assert "exception_handling_node" in workflow_def.nodes
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_file_permission_error(self):
        """Test extraction when file permissions cause read errors."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def test(): pass")
            temp_file = f.name
        
        try:
            # Make file unreadable
            import os
            os.chmod(temp_file, 0o000)
            
            with pytest.raises(PermissionError):
                extract_workflow_from_file(temp_file)
                
        finally:
            # Restore permissions and cleanup
            import os
            os.chmod(temp_file, 0o666)
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_circular_imports(self):
        """Test extraction with code that has circular import references."""
        # Create two temporary files that import each other
        with tempfile.TemporaryDirectory() as temp_dir:
            file1_path = Path(temp_dir) / "module1.py"
            file2_path = Path(temp_dir) / "module2.py"
            
            file1_content = '''
from quantalogic_flow.flow.flow import Workflow, Nodes
# This would normally cause circular import in real execution
# from module2 import helper_function

@Nodes.define(output="result1")
def node1():
    return "from_node1"

workflow = Workflow("node1")
'''
            
            file2_content = '''
from quantalogic_flow.flow.flow import Workflow, Nodes
# This would normally cause circular import in real execution  
# from module1 import node1

def helper_function():
    return "helper"

@Nodes.define(output="result2")
def node2():
    return helper_function()

workflow = Workflow("node2")
'''
            
            file1_path.write_text(file1_content, encoding='utf-8')
            file2_path.write_text(file2_content, encoding='utf-8')
            
            # Should handle both files without circular import issues during extraction
            workflow_def1, _ = extract_workflow_from_file(str(file1_path))
            workflow_def2, _ = extract_workflow_from_file(str(file2_path))
            
            assert isinstance(workflow_def1, WorkflowDefinition)
            assert isinstance(workflow_def2, WorkflowDefinition)
            assert "node1" in workflow_def1.nodes
            assert "node2" in workflow_def2.nodes

    def test_extract_with_memory_intensive_code(self):
        """Test extraction with memory-intensive code patterns."""
        code = '''
from quantalogic_flow.flow.flow import Workflow, Nodes

# Large data structures that might cause memory issues
LARGE_DICT = {f"key_{i}": f"value_{i}" for i in range(10000)}
LARGE_LIST = [i * j for i in range(1000) for j in range(10)]

@Nodes.define(output="memory_result")
def memory_intensive_node():
    # Simulate memory-intensive operations
    result = []
    for i in range(1000):
        temp_data = {
            "id": i,
            "data": [x for x in range(100)],
            "processed": sum(range(i)) if i < 100 else 0
        }
        result.append(temp_data)
    
    return {"processed_count": len(result), "sample": result[:5]}

workflow = Workflow("memory_intensive_node")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # Should handle memory-intensive code during parsing
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            assert "memory_intensive_node" in workflow_def.nodes
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_with_dynamic_imports_and_exec(self):
        """Test extraction with dynamic imports and exec statements."""
        code = '''
from quantalogic_flow.flow.flow import Workflow, Nodes
import importlib

# Dynamic import patterns
def dynamic_import(module_name):
    return importlib.import_module(module_name)

@Nodes.define(output="dynamic_result")
def dynamic_node():
    # Dynamic code execution (normally dangerous)
    dynamic_code = "result = 'dynamically_generated'"
    local_vars = {}
    exec(dynamic_code, {}, local_vars)
    
    # Dynamic module import
    try:
        os_module = dynamic_import('os')
        return {
            "dynamic_result": local_vars.get('result'),
            "os_available": hasattr(os_module, 'path')
        }
    except ImportError:
        return {"dynamic_result": local_vars.get('result'), "os_available": False}

workflow = Workflow("dynamic_node")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # Should handle dynamic code patterns during extraction
            workflow_def, extracted_code = extract_workflow_from_file(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            assert "dynamic_node" in workflow_def.nodes
            
        finally:
            Path(temp_file).unlink(missing_ok=True)
