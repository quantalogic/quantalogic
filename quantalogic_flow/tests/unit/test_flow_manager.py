"""Unit tests for WorkflowManager class."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quantalogic_flow.flow.flow_manager import WorkflowManager
from quantalogic_flow.flow.flow_manager_schema import (
    FunctionDefinition,
    NodeDefinition,
    TransitionDefinition,
    WorkflowDefinition,
    WorkflowStructure,
)


class TestWorkflowManager:
    """Test WorkflowManager functionality."""

    def setup_method(self):
        """Set up test data."""
        self.manager = WorkflowManager()
        self.sample_workflow = WorkflowDefinition(
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
                    code="def start_func(): return 'start'"
                ),
                "end_func": FunctionDefinition(
                    name="end_func",
                    type="embedded",
                    code="def end_func(): return 'end'"
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

    def test_workflow_manager_init(self):
        """Test WorkflowManager initialization."""
        manager = WorkflowManager()
        
        assert manager is not None
        assert hasattr(manager, "workflows")
        assert hasattr(manager, "load_workflow")
        assert hasattr(manager, "save_workflow")

    def test_load_workflow_from_file(self):
        """Test loading workflow from file."""
        sample_code = '''
@Nodes.define(output="result")
def test_node(input_param):
    return input_param

workflow = Workflow("test_node")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(sample_code)
            temp_file = f.name
        
        try:
            workflow_def = self.manager.load_workflow(temp_file)
            
            assert isinstance(workflow_def, WorkflowDefinition)
            assert workflow_def.workflow.start == "test_node"
            assert len(workflow_def.nodes) >= 1
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_load_workflow_from_nonexistent_file(self):
        """Test loading workflow from nonexistent file."""
        with pytest.raises(FileNotFoundError):
            self.manager.load_workflow("nonexistent_file.py")

    def test_save_workflow_to_file(self):
        """Test saving workflow to file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            output_file = f.name
        
        try:
            self.manager.save_workflow(
                workflow_def=self.sample_workflow,
                output_file=output_file,
                global_vars={"TEST_VAR": "test_value"}
            )
            
            assert Path(output_file).exists()
            
            # Verify content
            with open(output_file) as f:
                content = f.read()
                
            assert "def start_func" in content
            assert "def end_func" in content
            assert "TEST_VAR" in content
            
        finally:
            Path(output_file).unlink(missing_ok=True)

    def test_validate_workflow(self):
        """Test workflow validation."""
        result = self.manager.validate_workflow(self.sample_workflow)
        
        # Should return validation result
        assert hasattr(result, "is_valid")
        assert hasattr(result, "errors")
        assert hasattr(result, "warnings")

    def test_execute_workflow(self):
        """Test workflow execution."""
        # Mock the execution engine
        with patch('quantalogic_flow.flow.flow_manager.WorkflowEngine') as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine.run.return_value = {"result": "success"}
            mock_engine_class.return_value = mock_engine
            
            result = self.manager.execute_workflow(
                workflow_def=self.sample_workflow,
                initial_context={"input": "test"}
            )
            
            assert result == {"result": "success"}
            mock_engine.run.assert_called_once()

    def test_get_workflow_dependencies(self):
        """Test getting workflow dependencies."""
        dependencies = self.manager.get_workflow_dependencies(self.sample_workflow)
        
        assert isinstance(dependencies, list)
        # Should include standard dependencies
        expected_deps = ["loguru", "litellm", "pydantic", "anyio", "jinja2", "instructor"]
        for dep in expected_deps:
            assert any(dep in d for d in dependencies)

    def test_get_workflow_dependencies_with_additional(self):
        """Test getting workflow dependencies with additional requirements."""
        workflow_with_deps = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="node1",
                nodes=["node1"]
            ),
            nodes={
                "node1": NodeDefinition(
                    name="node1",
                    function="func1",
                    requirements=["numpy>=1.21.0", "pandas>=1.3.0"]
                )
            },
            functions={
                "func1": FunctionDefinition(
                    name="func1",
                    type="embedded",
                    code="import numpy as np\ndef func1(): pass"
                )
            },
            transitions=[]
        )
        
        dependencies = self.manager.get_workflow_dependencies(workflow_with_deps)
        
        assert isinstance(dependencies, list)
        assert any("numpy" in dep for dep in dependencies)
        assert any("pandas" in dep for dep in dependencies)

    def test_generate_mermaid_diagram(self):
        """Test mermaid diagram generation."""
        diagram = self.manager.generate_mermaid_diagram(self.sample_workflow)
        
        assert isinstance(diagram, str)
        assert "flowchart" in diagram.lower()
        assert "start_node" in diagram
        assert "end_node" in diagram

    def test_list_workflows(self):
        """Test listing workflows."""
        # Add some workflows to the manager
        self.manager.workflows["workflow1"] = self.sample_workflow
        self.manager.workflows["workflow2"] = self.sample_workflow
        
        workflows = self.manager.list_workflows()
        
        assert isinstance(workflows, list)
        assert "workflow1" in workflows
        assert "workflow2" in workflows

    def test_get_workflow(self):
        """Test getting specific workflow."""
        self.manager.workflows["test_workflow"] = self.sample_workflow
        
        workflow = self.manager.get_workflow("test_workflow")
        
        assert workflow == self.sample_workflow

    def test_get_nonexistent_workflow(self):
        """Test getting nonexistent workflow."""
        workflow = self.manager.get_workflow("nonexistent")
        
        assert workflow is None

    def test_add_workflow(self):
        """Test adding workflow to manager."""
        self.manager.add_workflow("new_workflow", self.sample_workflow)
        
        assert "new_workflow" in self.manager.workflows
        assert self.manager.workflows["new_workflow"] == self.sample_workflow

    def test_remove_workflow(self):
        """Test removing workflow from manager."""
        self.manager.workflows["to_remove"] = self.sample_workflow
        
        removed = self.manager.remove_workflow("to_remove")
        
        assert removed == self.sample_workflow
        assert "to_remove" not in self.manager.workflows

    def test_remove_nonexistent_workflow(self):
        """Test removing nonexistent workflow."""
        result = self.manager.remove_workflow("nonexistent")
        
        assert result is None

    def test_clear_workflows(self):
        """Test clearing all workflows."""
        self.manager.workflows["workflow1"] = self.sample_workflow
        self.manager.workflows["workflow2"] = self.sample_workflow
        
        self.manager.clear_workflows()
        
        assert len(self.manager.workflows) == 0

    def test_workflow_exists(self):
        """Test checking if workflow exists."""
        self.manager.workflows["existing"] = self.sample_workflow
        
        assert self.manager.workflow_exists("existing") is True
        assert self.manager.workflow_exists("nonexistent") is False

    def test_get_workflow_info(self):
        """Test getting workflow information."""
        info = self.manager.get_workflow_info(self.sample_workflow)
        
        assert isinstance(info, dict)
        assert "nodes" in info
        assert "transitions" in info
        assert "functions" in info
        assert info["nodes"] >= 2
        assert info["transitions"] >= 1

    def test_clone_workflow(self):
        """Test cloning workflow."""
        cloned = self.manager.clone_workflow(self.sample_workflow)
        
        assert isinstance(cloned, WorkflowDefinition)
        assert cloned is not self.sample_workflow  # Different instance
        assert cloned.workflow.start == self.sample_workflow.workflow.start
        assert len(cloned.nodes) == len(self.sample_workflow.nodes)

    def test_merge_workflows(self):
        """Test merging workflows."""
        workflow2 = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="other_start",
                nodes=["other_start", "other_end"]
            ),
            nodes={
                "other_start": NodeDefinition(
                    name="other_start",
                    function="other_start_func"
                ),
                "other_end": NodeDefinition(
                    name="other_end",
                    function="other_end_func"
                )
            },
            functions={
                "other_start_func": FunctionDefinition(
                    name="other_start_func",
                    type="embedded",
                    code="def other_start_func(): pass"
                ),
                "other_end_func": FunctionDefinition(
                    name="other_end_func",
                    type="embedded",
                    code="def other_end_func(): pass"
                )
            },
            transitions=[]
        )
        
        merged = self.manager.merge_workflows(self.sample_workflow, workflow2)
        
        assert isinstance(merged, WorkflowDefinition)
        assert len(merged.nodes) >= len(self.sample_workflow.nodes)
        assert len(merged.functions) >= len(self.sample_workflow.functions)

    def test_optimize_workflow(self):
        """Test workflow optimization."""
        optimized = self.manager.optimize_workflow(self.sample_workflow)
        
        assert isinstance(optimized, WorkflowDefinition)
        # Should return same or optimized workflow
        assert optimized.workflow.start is not None

    def test_workflow_to_dict(self):
        """Test converting workflow to dictionary."""
        workflow_dict = self.manager.workflow_to_dict(self.sample_workflow)
        
        assert isinstance(workflow_dict, dict)
        assert "workflow" in workflow_dict
        assert "nodes" in workflow_dict
        assert "functions" in workflow_dict
        assert "transitions" in workflow_dict

    def test_workflow_from_dict(self):
        """Test creating workflow from dictionary."""
        workflow_dict = {
            "workflow": {
                "start": "start_node",
                "nodes": ["start_node"]
            },
            "nodes": {
                "start_node": {
                    "name": "start_node",
                    "function": "start_func"
                }
            },
            "functions": {
                "start_func": {
                    "name": "start_func",
                    "type": "embedded",
                    "code": "def start_func(): pass"
                }
            },
            "transitions": []
        }
        
        workflow = self.manager.workflow_from_dict(workflow_dict)
        
        assert isinstance(workflow, WorkflowDefinition)
        assert workflow.workflow.start == "start_node"

    def test_export_workflow_json(self):
        """Test exporting workflow to JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_file = f.name
        
        try:
            self.manager.export_workflow_json(self.sample_workflow, json_file)
            
            assert Path(json_file).exists()
            
            # Verify it's valid JSON
            import json
            with open(json_file) as f:
                data = json.load(f)
                
            assert isinstance(data, dict)
            assert "workflow" in data
            
        finally:
            Path(json_file).unlink(missing_ok=True)

    def test_import_workflow_json(self):
        """Test importing workflow from JSON."""
        # First export a workflow
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_file = f.name
        
        try:
            self.manager.export_workflow_json(self.sample_workflow, json_file)
            
            # Now import it back
            imported = self.manager.import_workflow_json(json_file)
            
            assert isinstance(imported, WorkflowDefinition)
            assert imported.workflow.start == self.sample_workflow.workflow.start
            
        finally:
            Path(json_file).unlink(missing_ok=True)

    def test_backup_workflows(self):
        """Test backing up workflows."""
        self.manager.workflows["backup_test"] = self.sample_workflow
        
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_file = Path(temp_dir) / "backup.json"
            
            self.manager.backup_workflows(str(backup_file))
            
            assert backup_file.exists()

    def test_restore_workflows(self):
        """Test restoring workflows from backup."""
        # Create a backup first
        self.manager.workflows["restore_test"] = self.sample_workflow
        
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_file = Path(temp_dir) / "backup.json"
            
            self.manager.backup_workflows(str(backup_file))
            
            # Clear workflows and restore
            self.manager.clear_workflows()
            assert len(self.manager.workflows) == 0
            
            self.manager.restore_workflows(str(backup_file))
            
            assert "restore_test" in self.manager.workflows
