"""Unit tests for WorkflowExtractor class."""

import ast
from unittest.mock import patch

import pytest

from quantalogic_flow.flow.flow_extractor import WorkflowExtractor
from quantalogic_flow.flow.flow_manager_schema import (
    FunctionDefinition,
    NodeDefinition,
    TransitionDefinition,
    WorkflowDefinition,
)


class TestWorkflowExtractor:
    """Test WorkflowExtractor functionality."""

    def test_init(self):
        """Test WorkflowExtractor initialization."""
        extractor = WorkflowExtractor()
        
        assert extractor.nodes == {}
        assert extractor.functions == {}
        assert extractor.transitions == []
        assert extractor.start_node is None
        assert extractor.global_vars == {}
        assert extractor.observers == []
        assert extractor.convergence_nodes == []
        assert extractor.in_loop is False
        assert extractor.loop_nodes == []
        assert extractor.loop_entry_node is None

    def test_visit_module(self):
        """Test module visiting."""
        extractor = WorkflowExtractor()
        code = """
def test_func():
    return "test"

async def async_func():
    return "async"
"""
        tree = ast.parse(code)
        extractor.visit_Module(tree)
        
        # Should have processed function definitions
        assert len(extractor.functions) == 2
        assert "test_func" in extractor.functions
        assert "async_func" in extractor.functions

    def test_visit_function_def_with_nodes_decorator(self):
        """Test function definition with Nodes decorator."""
        extractor = WorkflowExtractor()
        code = """
@Nodes.define(output="result")
def test_node(input_param):
    return input_param
"""
        tree = ast.parse(code)
        func_def = tree.body[0]
        extractor.visit_FunctionDef(func_def)
        
        assert "test_node" in extractor.nodes
        node = extractor.nodes["test_node"]
        assert node.name == "test_node"
        assert node.output == "result"
        assert node.function == "test_node"

    def test_visit_function_def_with_llm_node_decorator(self):
        """Test function definition with LLM node decorator."""
        extractor = WorkflowExtractor()
        code = """
@Nodes.llm_node(output="llm_result", llm_params={"model": "gpt-4"})
def llm_node(query):
    return query
"""
        tree = ast.parse(code)
        func_def = tree.body[0]
        extractor.visit_FunctionDef(func_def)
        
        assert "llm_node" in extractor.nodes
        node = extractor.nodes["llm_node"]
        assert node.name == "llm_node"
        assert node.output == "llm_result"
        assert node.node_type == "llm"

    def test_visit_function_def_with_template_decorator(self):
        """Test function definition with template decorator."""
        extractor = WorkflowExtractor()
        code = """
@Nodes.template_node(output="template_result", template="test.jinja2")
def template_node(data):
    return data
"""
        tree = ast.parse(code)
        func_def = tree.body[0]
        extractor.visit_FunctionDef(func_def)
        
        assert "template_node" in extractor.nodes
        node = extractor.nodes["template_node"]
        assert node.name == "template_node"
        assert node.output == "template_result"
        assert node.node_type == "template"

    def test_visit_function_def_with_validate_decorator(self):
        """Test function definition with validate decorator."""
        extractor = WorkflowExtractor()
        code = """
@Nodes.validate_node(output="validation_result")
def validate_node(input_data):
    return "valid" if input_data else "invalid"
"""
        tree = ast.parse(code)
        func_def = tree.body[0]
        extractor.visit_FunctionDef(func_def)
        
        assert "validate_node" in extractor.nodes
        node = extractor.nodes["validate_node"]
        assert node.name == "validate_node"
        assert node.output == "validation_result"
        assert node.node_type == "validate"

    def test_visit_async_function_def(self):
        """Test async function definition."""
        extractor = WorkflowExtractor()
        code = """
@Nodes.define(output="async_result")
async def async_node(input_param):
    return input_param
"""
        tree = ast.parse(code)
        func_def = tree.body[0]
        extractor.visit_AsyncFunctionDef(func_def)
        
        assert "async_node" in extractor.nodes
        assert "async_node" in extractor.functions
        func = extractor.functions["async_node"]
        assert func.is_async is True

    def test_visit_assign_global_vars(self):
        """Test assignment to global variables."""
        extractor = WorkflowExtractor()
        code = """
DEFAULT_LLM_PARAMS = {"model": "gpt-4", "temperature": 0.7}
"""
        tree = ast.parse(code)
        assign_node = tree.body[0]
        extractor.visit_Assign(assign_node)
        
        assert "DEFAULT_LLM_PARAMS" in extractor.global_vars

    def test_visit_workflow_creation(self):
        """Test workflow creation parsing."""
        extractor = WorkflowExtractor()
        code = """
workflow = Workflow("start_node")
"""
        tree = ast.parse(code)
        assign_node = tree.body[0]
        extractor.visit_Assign(assign_node)
        
        assert extractor.start_node == "start_node"

    def test_visit_call_sequence(self):
        """Test sequence method call."""
        extractor = WorkflowExtractor()
        extractor.start_node = "start_node"
        code = """
workflow.sequence("node1", "node2", "node3")
"""
        tree = ast.parse(code)
        expr_node = tree.body[0]
        extractor.visit_Expr(expr_node)
        
        # Should have transitions between nodes
        transitions = [t for t in extractor.transitions if t.condition is None]
        assert len(transitions) >= 2

    def test_visit_call_then(self):
        """Test then method call."""
        extractor = WorkflowExtractor()
        extractor.start_node = "start_node"
        code = """
workflow.then("next_node", lambda ctx: ctx.get("proceed", True))
"""
        tree = ast.parse(code)
        expr_node = tree.body[0]
        extractor.visit_Expr(expr_node)
        
        # Should have a conditional transition
        transitions = [t for t in extractor.transitions if t.condition is not None]
        assert len(transitions) >= 1

    def test_visit_call_branch(self):
        """Test branch method call."""
        extractor = WorkflowExtractor()
        extractor.start_node = "start_node"
        code = """
workflow.branch([
    ("branch1", lambda ctx: ctx.get("use_branch1", False)),
    ("branch2", lambda ctx: ctx.get("use_branch2", False))
], default="default_node")
"""
        tree = ast.parse(code)
        expr_node = tree.body[0]
        extractor.visit_Expr(expr_node)
        
        # Should have branch transitions
        assert len(extractor.transitions) >= 2

    def test_visit_call_converge(self):
        """Test converge method call."""
        extractor = WorkflowExtractor()
        extractor.start_node = "start_node"
        code = """
workflow.converge("convergence_node")
"""
        tree = ast.parse(code)
        expr_node = tree.body[0]
        extractor.visit_Expr(expr_node)
        
        assert "convergence_node" in extractor.convergence_nodes

    def test_visit_call_parallel(self):
        """Test parallel method call."""
        extractor = WorkflowExtractor()
        extractor.start_node = "start_node"
        code = """
workflow.parallel("parallel1", "parallel2", "parallel3")
"""
        tree = ast.parse(code)
        expr_node = tree.body[0]
        extractor.visit_Expr(expr_node)
        
        # Should have parallel transitions
        assert len(extractor.transitions) >= 3

    def test_visit_call_add_observer(self):
        """Test add_observer method call."""
        extractor = WorkflowExtractor()
        code = """
workflow.add_observer(observer_func)
"""
        tree = ast.parse(code)
        expr_node = tree.body[0]
        extractor.visit_Expr(expr_node)
        
        assert "observer_func" in extractor.observers

    def test_visit_call_start_loop(self):
        """Test start_loop method call."""
        extractor = WorkflowExtractor()
        extractor.start_node = "start_node"
        code = """
workflow.start_loop()
"""
        tree = ast.parse(code)
        expr_node = tree.body[0]
        extractor.visit_Expr(expr_node)
        
        assert extractor.in_loop is True
        assert extractor.loop_entry_node == "start_node"

    def test_visit_call_end_loop(self):
        """Test end_loop method call."""
        extractor = WorkflowExtractor()
        extractor.in_loop = True
        extractor.loop_nodes = ["loop_node1", "loop_node2"]
        extractor.loop_entry_node = "entry_node"
        
        code = """
workflow.end_loop(lambda ctx: ctx.get("counter") > 5, "exit_node")
"""
        tree = ast.parse(code)
        expr_node = tree.body[0]
        extractor.visit_Expr(expr_node)
        
        assert extractor.in_loop is False
        assert extractor.loop_nodes == []
        assert extractor.loop_entry_node is None

    def test_visit_call_node_with_inputs_mapping(self):
        """Test node method call with inputs mapping."""
        extractor = WorkflowExtractor()
        code = """
workflow.node("mapped_node", inputs_mapping={"param1": "context_key", "param2": lambda ctx: ctx.get("value") * 2})
"""
        tree = ast.parse(code)
        expr_node = tree.body[0]
        extractor.visit_Expr(expr_node)
        
        assert "mapped_node" in extractor.nodes
        node = extractor.nodes["mapped_node"]
        assert node.inputs_mapping is not None

    def test_ast_to_code_conversion(self):
        """Test AST to code conversion."""
        extractor = WorkflowExtractor()
        code = """lambda ctx: ctx.get("test", True)"""
        tree = ast.parse(code, mode="eval")
        result = extractor.ast_to_code(tree.body)
        
        assert "ctx.get" in result
        assert "test" in result

    def test_extract_workflow_definition(self):
        """Test complete workflow definition extraction."""
        extractor = WorkflowExtractor()
        
        # Mock some data
        extractor.start_node = "start_node"
        extractor.nodes = {
            "start_node": NodeDefinition(
                name="start_node",
                function="start_func",
                output="start_output"
            )
        }
        extractor.functions = {
            "start_func": FunctionDefinition(
                name="start_func",
                type="embedded",
                code="def start_func(): return 'start'"
            )
        }
        extractor.transitions = [
            TransitionDefinition(
                from_node="start_node",
                to_node="end_node",
                condition=None
            )
        ]
        
        definition = extractor.extract_workflow_definition()
        
        assert isinstance(definition, WorkflowDefinition)
        assert definition.workflow.start == "start_node"
        assert len(definition.nodes) == 1
        assert len(definition.functions) == 1
        assert len(definition.transitions) == 1

    def test_extract_from_file_success(self):
        """Test successful file extraction."""
        sample_code = '''
@Nodes.define(output="result")
def test_node(input_param):
    return input_param

workflow = Workflow("test_node")
'''
        
        with patch("builtins.open", mock_open(sample_code)):
            with patch("os.path.exists", return_value=True):
                definition = WorkflowExtractor.extract_from_file("test.py")
                
                assert isinstance(definition, WorkflowDefinition)
                assert definition.workflow.start == "test_node"

    def test_extract_from_file_not_found(self):
        """Test file not found error."""
        with patch("os.path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                WorkflowExtractor.extract_from_file("nonexistent.py")

    def test_extract_from_string(self):
        """Test extraction from string."""
        sample_code = '''
@Nodes.define(output="result")
def test_node(input_param):
    return input_param

workflow = Workflow("test_node")
'''
        
        definition = WorkflowExtractor.extract_from_string(sample_code)
        
        assert isinstance(definition, WorkflowDefinition)
        assert definition.workflow.start == "test_node"
        assert len(definition.nodes) == 1


def mock_open(content):
    """Mock open function to return specific content."""
    from unittest.mock import mock_open as mock_open_func
    return mock_open_func(read_data=content)
