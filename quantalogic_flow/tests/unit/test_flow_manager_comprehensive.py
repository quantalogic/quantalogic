"""Comprehensive tests for flow_manager.py error handling and edge cases."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from quantalogic_flow.flow.flow_manager import WorkflowEngine, WorkflowManager
from quantalogic_flow.flow.flow_manager_schema import (
    BranchCondition,
    FunctionDefinition,
    LLMConfig,
    NodeDefinition,
    TemplateConfig,
    TransitionDefinition,
    WorkflowDefinition,
    WorkflowStructure,
)


class TestWorkflowManagerErrorHandling:
    """Test error handling and edge cases in WorkflowManager."""

    def setup_method(self):
        """Set up test data."""
        self.manager = WorkflowManager()
        self.basic_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="start_node",
                transitions=[
                    TransitionDefinition(from_node="start_node", to_node="end_node")
                ]
            ),
            nodes={
                "start_node": NodeDefinition(function="start_func"),
                "end_node": NodeDefinition(function="end_func")
            },
            functions={
                "start_func": FunctionDefinition(type="embedded", code="def start_func(): return 'start'"),
                "end_func": FunctionDefinition(type="embedded", code="def end_func(): return 'end'")
            }
        )

    def test_ensure_dependencies_with_invalid_package(self):
        """Test dependency installation with invalid package."""
        workflow = WorkflowDefinition(dependencies=["nonexistent-package-12345"])
        
        with patch('subprocess.check_call', side_effect=subprocess.CalledProcessError(1, 'pip')):
            with pytest.raises(ValueError, match="Failed to install dependency"):
                WorkflowManager(workflow)

    def test_ensure_dependencies_with_url(self):
        """Test dependency handling with URL."""
        workflow = WorkflowDefinition(dependencies=["https://example.com/package.tar.gz"])
        
        # Should not raise an error for URLs
        manager = WorkflowManager(workflow)
        assert manager.workflow.dependencies == ["https://example.com/package.tar.gz"]

    def test_ensure_dependencies_with_local_file(self):
        """Test dependency handling with local file."""
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
            local_file = f.name
        
        try:
            workflow = WorkflowDefinition(dependencies=[local_file])
            manager = WorkflowManager(workflow)
            assert local_file in manager.workflow.dependencies
        finally:
            Path(local_file).unlink(missing_ok=True)

    def test_add_node_with_lambda_in_inputs_mapping(self):
        """Test adding node with lambda function in inputs mapping."""
        # Create a lambda function
        def test_lambda(ctx):
            return ctx.get('test_value', 'default')
        
        with patch('inspect.getsource', return_value="lambda ctx: ctx.get('test_value', 'default')"):
            self.manager.add_node(
                name="test_node",
                function="test_func",
                inputs_mapping={"input1": test_lambda}
            )
        
        node = self.manager.workflow.nodes["test_node"]
        assert "input1" in node.inputs_mapping
        # The function name should be stored when inspection succeeds
        assert node.inputs_mapping["input1"] == "test_lambda"

    def test_add_node_with_lambda_inspection_error(self):
        """Test adding node with lambda that fails inspection."""
        def test_lambda(ctx):
            return ctx.get('test_value', 'default')
        
        with patch('inspect.getsource', side_effect=Exception("Inspection failed")):
            self.manager.add_node(
                name="test_node",
                function="test_func",
                inputs_mapping={"input1": test_lambda}
            )
        
        node = self.manager.workflow.nodes["test_node"]
        assert "input1" in node.inputs_mapping
        # Should fallback to function name
        assert node.inputs_mapping["input1"] == "test_lambda"

    def test_remove_node_nonexistent(self):
        """Test removing non-existent node."""
        with pytest.raises(ValueError, match="Node 'nonexistent' does not exist"):
            self.manager.remove_node("nonexistent")

    def test_remove_node_with_complex_transitions(self):
        """Test removing node that has complex transitions."""
        # Add nodes and complex transitions
        self.manager.add_node("node1", function="func1")
        self.manager.add_node("node2", function="func2")
        self.manager.add_node("node3", function="func3")
        
        # Add branch condition
        branch_condition = BranchCondition(to_node="node3", condition="ctx.branch == 'yes'")
        self.manager.add_transition("node1", [branch_condition, "node2"])
        
        # Set start node and convergence
        self.manager.set_start_node("node1")
        self.manager.add_convergence_node("node2")
        
        # Remove node2
        self.manager.remove_node("node2")
        
        assert "node2" not in self.manager.workflow.nodes
        assert "node2" not in self.manager.workflow.workflow.convergence_nodes

    def test_update_node_nonexistent(self):
        """Test updating non-existent node."""
        with pytest.raises(ValueError, match="Node 'nonexistent' does not exist"):
            self.manager.update_node("nonexistent", function="new_func")

    def test_update_node_with_all_parameters(self):
        """Test updating node with all possible parameters."""
        self.manager.add_node("update_test", function="old_func")
        
        def test_lambda(ctx):
            return "updated"
            
        with patch('inspect.getsource', return_value="lambda ctx: 'updated'"):
            self.manager.update_node(
                "update_test",
                function="new_func",
                template_config={"template": "Updated: {{value}}"},
                inputs_mapping={"input1": test_lambda},
                output="updated_output",
                retries=5,
                delay=2.0,
                timeout=30.0,
                parallel=True
            )
        
        node = self.manager.workflow.nodes["update_test"]
        assert node.function == "new_func"
        assert node.template_config.template == "Updated: {{value}}"
        assert node.output == "updated_output"
        assert node.retries == 5
        assert node.delay == 2.0
        assert node.timeout == 30.0
        assert node.parallel is True

    def test_add_transition_with_strict_validation_failure(self):
        """Test adding transition with strict validation that fails."""
        with pytest.raises(ValueError, match="Source node 'nonexistent_from' does not exist"):
            self.manager.add_transition("nonexistent_from", "nonexistent_to", strict=True)

    def test_add_transition_with_branch_condition_validation_failure(self):
        """Test adding transition with branch condition to non-existent node."""
        self.manager.add_node("source", function="func1")
        
        branch_condition = BranchCondition(to_node="nonexistent", condition="True")
        
        with pytest.raises(ValueError, match="Target node 'nonexistent' does not exist"):
            self.manager.add_transition("source", [branch_condition], strict=True)

    def test_add_loop_empty_nodes(self):
        """Test adding loop with empty node list."""
        with pytest.raises(ValueError, match="Loop must contain at least one node"):
            self.manager.add_loop([], "ctx.counter < 10", "exit_node")

    def test_add_loop_with_nonexistent_nodes(self):
        """Test adding loop with non-existent nodes."""
        with pytest.raises(ValueError, match="Node 'nonexistent' does not exist"):
            self.manager.add_loop(["nonexistent"], "ctx.counter < 10", "exit_node")

    def test_add_loop_with_nonexistent_exit_node(self):
        """Test adding loop with non-existent exit node."""
        self.manager.add_node("loop_node", function="func1")
        
        with pytest.raises(ValueError, match="Node 'nonexistent_exit' does not exist"):
            self.manager.add_loop(["loop_node"], "ctx.counter < 10", "nonexistent_exit")

    def test_add_loop_successful(self):
        """Test successful loop addition."""
        self.manager.add_node("loop_start", function="func1")
        self.manager.add_node("loop_middle", function="func2")
        self.manager.add_node("loop_exit", function="func3")
        
        self.manager.add_loop(["loop_start", "loop_middle"], "ctx.counter < 10", "loop_exit")
        
        # Verify transitions were added
        transitions = self.manager.workflow.workflow.transitions
        assert len(transitions) >= 3  # Internal + loop-back + exit

    def test_set_start_node_nonexistent(self):
        """Test setting non-existent start node."""
        with pytest.raises(ValueError, match="Node 'nonexistent' does not exist"):
            self.manager.set_start_node("nonexistent")

    def test_add_convergence_node_nonexistent(self):
        """Test adding non-existent convergence node."""
        with pytest.raises(ValueError, match="Node 'nonexistent' does not exist"):
            self.manager.add_convergence_node("nonexistent")

    def test_add_convergence_node_duplicate(self):
        """Test adding duplicate convergence node."""
        self.manager.add_node("conv_node", function="func1")
        
        self.manager.add_convergence_node("conv_node")
        self.manager.add_convergence_node("conv_node")  # Should not duplicate
        
        convergence_nodes = self.manager.workflow.workflow.convergence_nodes
        assert convergence_nodes.count("conv_node") == 1

    def test_add_observer_nonexistent_function(self):
        """Test adding observer for non-existent function."""
        with pytest.raises(ValueError, match="Observer function 'nonexistent' not defined"):
            self.manager.add_observer("nonexistent")

    def test_add_observer_successful(self):
        """Test successful observer addition."""
        self.manager.add_function("observer_func", "embedded", "def observer_func(): pass")
        self.manager.add_observer("observer_func")
        
        assert "observer_func" in self.manager.workflow.observers

    def test_resolve_model_invalid_format(self):
        """Test resolving model with invalid format."""
        with pytest.raises(ValueError, match="Failed to resolve response_model"):
            self.manager._resolve_model("invalid_format")

    def test_resolve_model_nonexistent_module(self):
        """Test resolving model with non-existent module."""
        with pytest.raises(ValueError, match="Failed to resolve response_model"):
            self.manager._resolve_model("nonexistent_module:Model")

    def test_resolve_model_nonexistent_class(self):
        """Test resolving model with non-existent class."""
        with pytest.raises(ValueError, match="Failed to resolve response_model"):
            self.manager._resolve_model("os:NonexistentClass")

    @patch('pydantic.BaseModel')
    def test_resolve_model_not_basemodel(self, mock_basemodel):
        """Test resolving model that's not a BaseModel."""
        with patch('importlib.import_module') as mock_import:
            mock_module = Mock()
            mock_module.NotBaseModel = str  # Not a BaseModel
            mock_import.return_value = mock_module
            
            with pytest.raises(ValueError, match="is not a Pydantic model"):
                self.manager._resolve_model("test_module:NotBaseModel")

    def test_import_module_from_url_success(self):
        """Test importing module from URL successfully."""
        mock_response = Mock()
        mock_response.read.return_value = b"def test_func(): pass"
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        
        with patch('urllib.request.urlopen', return_value=mock_response), \
             patch('tempfile.NamedTemporaryFile') as mock_temp:
            
            mock_file = Mock()
            mock_file.name = "/tmp/test.py"
            mock_file.write = Mock()
            mock_temp.return_value.__enter__.return_value = mock_file
            
            with patch('importlib.util.spec_from_file_location') as mock_spec, \
                 patch('importlib.util.module_from_spec') as mock_module, \
                 patch('os.remove'), \
                 patch('sys.modules', {}):
                
                mock_spec_obj = Mock()
                mock_spec_obj.loader = Mock()
                mock_spec_obj.loader.exec_module = Mock()
                mock_spec.return_value = mock_spec_obj
                
                mock_module_obj = Mock()
                mock_module.return_value = mock_module_obj
                
                result = self.manager.import_module_from_source("https://example.com/module.py")
                assert result == mock_module_obj

    def test_import_module_from_url_failure(self):
        """Test importing module from URL with failure."""
        with patch('urllib.request.urlopen', side_effect=Exception("Network error")):
            with pytest.raises(ValueError, match="Failed to import module from URL"):
                self.manager.import_module_from_source("https://example.com/module.py")

    def test_import_module_from_local_file_success(self):
        """Test importing module from local file successfully."""
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
            f.write(b"def test_func(): pass")
            temp_file = f.name
        
        try:
            with patch('importlib.util.spec_from_file_location') as mock_spec, \
                 patch('importlib.util.module_from_spec') as mock_module:
                
                mock_spec.return_value.loader.exec_module = Mock()
                mock_module.return_value = Mock()
                
                result = self.manager.import_module_from_source(temp_file)
                assert result is not None
                
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_import_module_from_local_file_failure(self):
        """Test importing module from local file with failure."""
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
            temp_file = f.name
        
        try:
            with patch('importlib.util.spec_from_file_location', return_value=None):
                with pytest.raises(ValueError, match="Failed to create module spec"):
                    self.manager.import_module_from_source(temp_file)
                    
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_import_module_standard_import_failure(self):
        """Test importing standard module with failure."""
        with patch('importlib.import_module', side_effect=ImportError("Module not found")):
            with pytest.raises(ValueError, match="Failed to import module"):
                self.manager.import_module_from_source("nonexistent_module")


class TestWorkflowManagerInstantiation:
    """Test workflow instantiation with various edge cases."""

    def setup_method(self):
        """Set up test data."""
        self.manager = WorkflowManager()

    def test_instantiate_workflow_no_start_node(self):
        """Test instantiation with no start node."""
        workflow = WorkflowDefinition(
            nodes={"node1": NodeDefinition(function="func1")},
            functions={"func1": FunctionDefinition(type="embedded", code="def func1(): pass")}
        )
        self.manager.workflow = workflow
        
        with pytest.raises(ValueError, match="Start node not set"):
            self.manager.instantiate_workflow()

    def test_instantiate_workflow_embedded_function_no_code(self):
        """Test that validation prevents embedded function without code."""
        # This should fail at the schema validation level
        with pytest.raises(Exception):  # ValidationError
            WorkflowDefinition(
                workflow=WorkflowStructure(start="node1"),
                nodes={"node1": NodeDefinition(function="func1")},
                functions={"func1": FunctionDefinition(type="embedded")}  # No code - should fail validation
            )

    def test_instantiate_workflow_embedded_function_not_defined(self):
        """Test instantiation with embedded function not defined in code."""
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(start="node1"),
            nodes={"node1": NodeDefinition(function="func1")},
            functions={"func1": FunctionDefinition(type="embedded", code="def other_func(): pass")}  # Wrong function
        )
        self.manager.workflow = workflow
        
        with pytest.raises(ValueError, match="Embedded function 'func1' not defined in code"):
            self.manager.instantiate_workflow()

    def test_instantiate_workflow_external_function_no_module(self):
        """Test that validation prevents external function without module."""
        # This should fail at the schema validation level
        with pytest.raises(Exception):  # ValidationError
            WorkflowDefinition(
                workflow=WorkflowStructure(start="node1"),
                nodes={"node1": NodeDefinition(function="func1")},
                functions={"func1": FunctionDefinition(type="external")}  # No module - should fail validation
            )

    def test_instantiate_workflow_external_function_no_function_name(self):
        """Test that validation prevents external function without function name."""
        # This should fail at the schema validation level
        with pytest.raises(Exception):  # ValidationError
            WorkflowDefinition(
                workflow=WorkflowStructure(start="node1"),
                nodes={"node1": NodeDefinition(function="func1")},
                functions={"func1": FunctionDefinition(type="external", module="os")}  # No function name - should fail validation
            )

    def test_instantiate_workflow_function_not_found_in_node(self):
        """Test instantiation when node references non-existent function."""
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(start="node1"),
            nodes={"node1": NodeDefinition(function="nonexistent_func")},
            functions={"func1": FunctionDefinition(type="embedded", code="def func1(): pass")}
        )
        self.manager.workflow = workflow
        
        with pytest.raises(ValueError, match="Function 'nonexistent_func' for node 'node1' not found"):
            self.manager.instantiate_workflow()

    def test_instantiate_workflow_with_llm_config_and_response_model(self):
        """Test instantiation with LLM config and response model."""
        from pydantic import BaseModel
        
        class TestModel(BaseModel):
            result: str
        
        # Mock the _resolve_model method to return our test model
        with patch.object(self.manager, '_resolve_model', return_value=TestModel):
            workflow = WorkflowDefinition(
                workflow=WorkflowStructure(start="llm_node"),
                nodes={"llm_node": NodeDefinition(
                    llm_config=LLMConfig(
                        model="gpt-3.5-turbo",
                        prompt_template="Process: {{input}}",
                        response_model="test_module:TestModel"
                    )
                )}
            )
            self.manager.workflow = workflow
            
            result = self.manager.instantiate_workflow()
            assert result is not None

    def test_instantiate_workflow_with_template_config(self):
        """Test instantiation with template configuration."""
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(start="template_node"),
            nodes={"template_node": NodeDefinition(
                template_config=TemplateConfig(
                    template="Hello {{name}}!"
                )
            )}
        )
        self.manager.workflow = workflow
        
        result = self.manager.instantiate_workflow()
        assert result is not None

    def test_instantiate_workflow_with_sub_workflow(self):
        """Test instantiation with sub-workflow."""
        sub_structure = WorkflowStructure(
            start="sub_start",
            transitions=[TransitionDefinition(from_node="sub_start", to_node="sub_end")]
        )
        
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(start="main_node"),
            nodes={"main_node": NodeDefinition(sub_workflow=sub_structure)}
        )
        self.manager.workflow = workflow
        
        # Mock the necessary components to avoid node registration issues
        with patch('quantalogic_flow.flow.flow_manager.Nodes') as mock_nodes:
            mock_nodes.NODE_REGISTRY = {"main_node": (Mock(), [], "output")}
            with patch('quantalogic_flow.flow.flow_manager.Workflow') as mock_workflow:
                mock_wf = Mock()
                mock_workflow.return_value = mock_wf
                
                result = self.manager.instantiate_workflow()
                assert result == mock_wf

    def test_instantiate_workflow_observer_not_found(self):
        """Test instantiation when observer function not found."""
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(start="node1"),
            nodes={"node1": NodeDefinition(function="func1")},
            functions={"func1": FunctionDefinition(type="embedded", code="def func1(): pass")},
            observers=["nonexistent_observer"]
        )
        self.manager.workflow = workflow
        
        with pytest.raises(ValueError, match="Observer 'nonexistent_observer' not found"):
            self.manager.instantiate_workflow()


class TestWorkflowManagerYAMLHandling:
    """Test YAML loading and saving edge cases."""

    def setup_method(self):
        """Set up test data."""
        self.manager = WorkflowManager()

    def test_load_from_yaml_file_not_found(self):
        """Test loading from non-existent YAML file."""
        with pytest.raises(FileNotFoundError, match="YAML file .* not found"):
            self.manager.load_from_yaml("nonexistent.yaml")

    def test_load_from_yaml_invalid_yaml(self):
        """Test loading invalid YAML content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            yaml_file = f.name
        
        try:
            with pytest.raises(Exception):  # YAML parsing error
                self.manager.load_from_yaml(yaml_file)
        finally:
            Path(yaml_file).unlink(missing_ok=True)

    def test_load_from_yaml_validation_error(self):
        """Test loading YAML with validation errors."""
        invalid_workflow = {
            "workflow": {"start": "node1"},
            "nodes": {"node1": {"invalid_field": "value"}},  # Invalid field
            "functions": {}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump(invalid_workflow, f)
            yaml_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Invalid workflow YAML"):
                self.manager.load_from_yaml(yaml_file)
        finally:
            Path(yaml_file).unlink(missing_ok=True)

    def test_save_to_yaml_with_multiline_strings(self):
        """Test saving YAML with multi-line strings."""
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(start="node1"),
            nodes={"node1": NodeDefinition(function="func1")},
            functions={"func1": FunctionDefinition(
                type="embedded", 
                code="def func1():\n    print('Hello')\n    return 'world'"
            )}
        )
        self.manager.workflow = workflow
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_file = f.name
        
        try:
            self.manager.save_to_yaml(yaml_file)
            
            with open(yaml_file) as f:
                content = f.read()
            
            assert "|-" in content or "|" in content  # Multi-line block scalar
            
        finally:
            Path(yaml_file).unlink(missing_ok=True)


class TestWorkflowEngine:
    """Test WorkflowEngine functionality."""

    def test_workflow_engine_init(self):
        """Test WorkflowEngine initialization."""
        workflow_def = WorkflowDefinition(
            workflow=WorkflowStructure(start="start_node"),
            nodes={"start_node": NodeDefinition(function="func1")},
            functions={"func1": FunctionDefinition(type="embedded", code="def func1(): return 'result'")}
        )
        
        engine = WorkflowEngine(workflow_def)
        assert engine.workflow_def == workflow_def

    async def test_workflow_engine_run(self):
        """Test WorkflowEngine run method."""
        workflow_def = WorkflowDefinition(
            workflow=WorkflowStructure(start="start_node"),
            nodes={"start_node": NodeDefinition(function="func1")},
            functions={"func1": FunctionDefinition(type="embedded", code="def func1(): return 'result'")}
        )
        
        engine = WorkflowEngine(workflow_def)
        
        # Mock the workflow instantiation and execution
        with patch('quantalogic_flow.flow.flow_manager.WorkflowManager.instantiate_workflow') as mock_instantiate:
            mock_workflow = Mock()
            mock_engine = Mock()
            
            # Create a proper coroutine for mocking
            async def mock_run(context):
                return "test_result"
            
            mock_engine.run = mock_run
            mock_workflow.build.return_value = mock_engine
            mock_instantiate.return_value = mock_workflow
            
            result = await engine.run({"initial": "context"})
            assert result == "test_result"


class TestWorkflowManagerExecuteWorkflow:
    """Test execute_workflow method with various scenarios."""

    def setup_method(self):
        """Set up test data."""
        self.manager = WorkflowManager()
        self.workflow_def = WorkflowDefinition(
            workflow=WorkflowStructure(start="start_node"),
            nodes={"start_node": NodeDefinition(function="func1")},
            functions={"func1": FunctionDefinition(type="embedded", code="def func1(): return 'result'")}
        )

    def test_execute_workflow_sync_result(self):
        """Test execute_workflow with synchronous result."""
        with patch('quantalogic_flow.flow.flow_manager.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine.run.return_value = "sync_result"  # Not a coroutine
            mock_engine_class.return_value = mock_engine
            
            result = self.manager.execute_workflow(self.workflow_def, {"input": "test"})
            assert result == "sync_result"

    def test_execute_workflow_async_result_with_loop(self):
        """Test execute_workflow with async result and existing event loop."""
        async def mock_coroutine():
            return "async_result"
        
        with patch('quantalogic_flow.flow.flow_manager.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine.run.return_value = mock_coroutine()
            mock_engine_class.return_value = mock_engine
            
            with patch('asyncio.get_event_loop') as mock_get_loop:
                mock_loop = Mock()
                mock_loop.run_until_complete.return_value = "async_result"
                mock_get_loop.return_value = mock_loop
                
                result = self.manager.execute_workflow(self.workflow_def, {"input": "test"})
                assert result == "async_result"

    def test_execute_workflow_async_result_no_loop(self):
        """Test execute_workflow with async result and no event loop."""
        async def mock_coroutine():
            return "async_result"
        
        with patch('quantalogic_flow.flow.flow_manager.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine.run.return_value = mock_coroutine()
            mock_engine_class.return_value = mock_engine
            
            with patch('asyncio.get_event_loop', side_effect=RuntimeError("No event loop")):
                with patch('asyncio.new_event_loop') as mock_new_loop:
                    with patch('asyncio.set_event_loop'):
                        mock_loop = Mock()
                        mock_loop.run_until_complete.return_value = "async_result"
                        mock_new_loop.return_value = mock_loop
                        
                        result = self.manager.execute_workflow(self.workflow_def, {"input": "test"})
                        assert result == "async_result"

    def test_execute_workflow_async_result_running_loop(self):
        """Test execute_workflow with async result and running event loop."""
        async def mock_coroutine():
            return "async_result"
        
        with patch('quantalogic_flow.flow.flow_manager.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine.run.return_value = mock_coroutine()
            mock_engine_class.return_value = mock_engine
            
            with patch('asyncio.get_event_loop') as mock_get_loop:
                mock_loop = Mock()
                mock_loop.run_until_complete.side_effect = RuntimeError("Event loop already running")
                mock_get_loop.return_value = mock_loop
                
                with patch('concurrent.futures.ThreadPoolExecutor') as mock_executor:
                    mock_future = Mock()
                    mock_future.result.return_value = "async_result"
                    mock_executor.return_value.__enter__.return_value.submit.return_value = mock_future
                    
                    with patch('asyncio.run', return_value="async_result"):
                        result = self.manager.execute_workflow(self.workflow_def, {"input": "test"})
                        assert result == "async_result"
