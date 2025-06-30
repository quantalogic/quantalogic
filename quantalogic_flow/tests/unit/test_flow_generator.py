"""Unit tests for flow_generator module."""

import tempfile
from pathlib import Path

import pytest

from quantalogic_flow.flow.flow_generator import generate_executable_script
from quantalogic_flow.flow.flow_manager_schema import (
    FunctionDefinition,
    NodeDefinition,
    TransitionDefinition,
    WorkflowDefinition,
    WorkflowStructure,
)


class TestFlowGenerator:
    """Test flow generator functionality."""

    def setup_method(self):
        """Set up test data."""
        self.workflow_def = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="start_node",
                nodes=["start_node", "end_node"]
            ),
            nodes={
                "start_node": NodeDefinition(
                    name="start_node",
                    function="start_func",
                    output="start_result"
                ),
                "end_node": NodeDefinition(
                    name="end_node", 
                    function="end_func",
                    output="end_result"
                )
            },
            functions={
                "start_func": FunctionDefinition(
                    name="start_func",
                    type="embedded",
                    code="def start_func(input_data):\n    return input_data",
                    is_async=False
                ),
                "end_func": FunctionDefinition(
                    name="end_func",
                    type="embedded", 
                    code="def end_func(data):\n    return f'processed: {data}'",
                    is_async=False
                )
            },
            transitions=[
                TransitionDefinition(
                    from_node="start_node",
                    to_node="end_node",
                    condition=None
                )
            ]
        )
        self.global_vars = {
            "DEFAULT_MODEL": "gpt-4",
            "TEMPERATURE": 0.7
        }

    def test_generate_executable_script_basic(self):
        """Test basic script generation."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            output_file = f.name
        
        try:
            generate_executable_script(
                workflow_def=self.workflow_def,
                global_vars=self.global_vars,
                output_file=output_file
            )
            
            # Check that file was created
            assert Path(output_file).exists()
            
            # Read and verify content
            with open(output_file) as f:
                content = f.read()
                
            # Check for shebang
            assert content.startswith('#!/usr/bin/env')
            
            # Check for dependencies
            assert 'requires-python' in content
            assert 'loguru' in content
            assert 'litellm' in content
            
            # Check for global variables
            assert 'DEFAULT_MODEL = "gpt-4"' in content
            assert 'TEMPERATURE = 0.7' in content
            
            # Check for function definitions
            assert 'def start_func(input_data):' in content
            assert 'def end_func(data):' in content
            
            # Check for workflow construction
            assert 'workflow = Workflow("start_node")' in content
            assert 'workflow.sequence("end_node")' in content
            
        finally:
            # Clean up
            Path(output_file).unlink(missing_ok=True)

    def test_generate_executable_script_with_custom_context(self):
        """Test script generation with custom initial context."""
        initial_context = {"custom_input": "test_value"}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            output_file = f.name
        
        try:
            generate_executable_script(
                workflow_def=self.workflow_def,
                global_vars=self.global_vars,
                output_file=output_file,
                initial_context=initial_context
            )
            
            with open(output_file) as f:
                content = f.read()
                
            # Check for custom context
            assert 'custom_input' in content
            assert 'test_value' in content
            
        finally:
            Path(output_file).unlink(missing_ok=True)

    def test_generate_executable_script_with_llm_nodes(self):
        """Test script generation with LLM nodes."""
        llm_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="llm_node",
                nodes=["llm_node"]
            ),
            nodes={
                "llm_node": NodeDefinition(
                    name="llm_node",
                    function="llm_func",
                    output="llm_result",
                    node_type="llm",
                    llm_params={"model": "gpt-4", "temperature": 0.5}
                )
            },
            functions={
                "llm_func": FunctionDefinition(
                    name="llm_func",
                    type="embedded",
                    code="def llm_func(query):\n    return query",
                    is_async=False
                )
            },
            transitions=[]
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            output_file = f.name
        
        try:
            generate_executable_script(
                workflow_def=llm_workflow,
                global_vars=self.global_vars,
                output_file=output_file
            )
            
            with open(output_file) as f:
                content = f.read()
                
            # Check for LLM node decorator
            assert '@Nodes.llm_node' in content
            assert 'model' in content
            assert 'temperature' in content
            
        finally:
            Path(output_file).unlink(missing_ok=True)

    def test_generate_executable_script_with_template_nodes(self):
        """Test script generation with template nodes."""
        template_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="template_node",
                nodes=["template_node"]
            ),
            nodes={
                "template_node": NodeDefinition(
                    name="template_node",
                    function="template_func",
                    output="template_result",
                    node_type="template",
                    template_config={
                        "template": "test_template.jinja2",
                        "variables": ["var1", "var2"]
                    }
                )
            },
            functions={
                "template_func": FunctionDefinition(
                    name="template_func",
                    type="embedded",
                    code="def template_func(data):\n    return data",
                    is_async=False
                )
            },
            transitions=[]
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            output_file = f.name
        
        try:
            generate_executable_script(
                workflow_def=template_workflow,
                global_vars=self.global_vars,
                output_file=output_file
            )
            
            with open(output_file) as f:
                content = f.read()
                
            # Check for template node decorator
            assert '@Nodes.template_node' in content
            assert 'test_template.jinja2' in content
            
        finally:
            Path(output_file).unlink(missing_ok=True)

    def test_generate_executable_script_with_async_functions(self):
        """Test script generation with async functions."""
        async_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="async_node",
                nodes=["async_node"]
            ),
            nodes={
                "async_node": NodeDefinition(
                    name="async_node",
                    function="async_func",
                    output="async_result"
                )
            },
            functions={
                "async_func": FunctionDefinition(
                    name="async_func",
                    type="embedded",
                    code="async def async_func(data):\n    return data",
                    is_async=True
                )
            },
            transitions=[]
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            output_file = f.name
        
        try:
            generate_executable_script(
                workflow_def=async_workflow,
                global_vars=self.global_vars,
                output_file=output_file
            )
            
            with open(output_file) as f:
                content = f.read()
                
            # Check for async function
            assert 'async def async_func' in content
            
        finally:
            Path(output_file).unlink(missing_ok=True)

    def test_generate_executable_script_with_branches(self):
        """Test script generation with branch transitions."""
        branch_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="start_node",
                nodes=["start_node", "branch1", "branch2", "default_node"]
            ),
            nodes={
                "start_node": NodeDefinition(
                    name="start_node",
                    function="start_func",
                    output="start_result"
                ),
                "branch1": NodeDefinition(
                    name="branch1",
                    function="branch1_func", 
                    output="branch1_result"
                ),
                "branch2": NodeDefinition(
                    name="branch2",
                    function="branch2_func",
                    output="branch2_result"
                ),
                "default_node": NodeDefinition(
                    name="default_node",
                    function="default_func",
                    output="default_result"
                )
            },
            functions={
                "start_func": FunctionDefinition(
                    name="start_func",
                    type="embedded",
                    code="def start_func():\n    return 'start'",
                    is_async=False
                ),
                "branch1_func": FunctionDefinition(
                    name="branch1_func",
                    type="embedded",
                    code="def branch1_func():\n    return 'branch1'",
                    is_async=False
                ),
                "branch2_func": FunctionDefinition(
                    name="branch2_func",
                    type="embedded",
                    code="def branch2_func():\n    return 'branch2'",
                    is_async=False
                ),
                "default_func": FunctionDefinition(
                    name="default_func",
                    type="embedded",
                    code="def default_func():\n    return 'default'",
                    is_async=False
                )
            },
            transitions=[
                TransitionDefinition(
                    from_node="start_node",
                    to_node="branch1",
                    condition="lambda ctx: ctx.get('use_branch1', False)"
                ),
                TransitionDefinition(
                    from_node="start_node",
                    to_node="branch2",
                    condition="lambda ctx: ctx.get('use_branch2', False)"
                ),
                TransitionDefinition(
                    from_node="start_node",
                    to_node="default_node",
                    condition=None
                )
            ]
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            output_file = f.name
        
        try:
            generate_executable_script(
                workflow_def=branch_workflow,
                global_vars=self.global_vars,
                output_file=output_file
            )
            
            with open(output_file) as f:
                content = f.read()
                
            # Check for branch construction
            assert 'workflow.branch' in content
            assert 'use_branch1' in content
            assert 'use_branch2' in content
            assert 'default=' in content
            
        finally:
            Path(output_file).unlink(missing_ok=True)

    def test_generate_executable_script_with_input_mappings(self):
        """Test script generation with input mappings."""
        mapping_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="mapped_node",
                nodes=["mapped_node"]
            ),
            nodes={
                "mapped_node": NodeDefinition(
                    name="mapped_node",
                    function="mapped_func",
                    output="mapped_result",
                    inputs_mapping={
                        "param1": "context_key1",
                        "param2": "lambda ctx: ctx.get('value') * 2"
                    }
                )
            },
            functions={
                "mapped_func": FunctionDefinition(
                    name="mapped_func",
                    type="embedded",
                    code="def mapped_func(param1, param2):\n    return param1 + param2",
                    is_async=False
                )
            },
            transitions=[]
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            output_file = f.name
        
        try:
            generate_executable_script(
                workflow_def=mapping_workflow,
                global_vars=self.global_vars,
                output_file=output_file
            )
            
            with open(output_file) as f:
                content = f.read()
                
            # Check for input mappings
            assert 'inputs_mapping=' in content
            assert 'context_key1' in content
            assert 'lambda ctx: ctx.get' in content
            
        finally:
            Path(output_file).unlink(missing_ok=True)

    def test_generate_executable_script_empty_workflow(self):
        """Test script generation with empty workflow."""
        empty_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="empty_node",
                nodes=["empty_node"]
            ),
            nodes={
                "empty_node": NodeDefinition(
                    name="empty_node",
                    function="empty_func",
                    output="empty_result"
                )
            },
            functions={
                "empty_func": FunctionDefinition(
                    name="empty_func",
                    type="embedded",
                    code="def empty_func():\n    return 'empty'",
                    is_async=False
                )
            },
            transitions=[]
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            output_file = f.name
        
        try:
            generate_executable_script(
                workflow_def=empty_workflow,
                global_vars={},
                output_file=output_file
            )
            
            # Should not raise an exception
            assert Path(output_file).exists()
            
        finally:
            Path(output_file).unlink(missing_ok=True)

    def test_generate_executable_script_invalid_output_path(self):
        """Test script generation with invalid output path."""
        invalid_path = "/invalid/path/that/does/not/exist/script.py"
        
        with pytest.raises(Exception):
            generate_executable_script(
                workflow_def=self.workflow_def,
                global_vars=self.global_vars,
                output_file=invalid_path
            )
