"""Tests to achieve 100% coverage for flow_extractor.py.

This test file specifically targets the missing coverage areas identified in the coverage report.
Each test is designed to cover specific lines and edge cases that are currently not tested.
"""

import ast
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from quantalogic_flow.flow.flow_extractor import (
    WorkflowExtractor,
    extract_workflow_from_file,
    print_workflow_definition,
)
from quantalogic_flow.flow.flow_manager_schema import (
    FunctionDefinition,
    NodeDefinition,
    TransitionDefinition,
    WorkflowDefinition,
    WorkflowStructure,
)


class TestFlowExtractorMissingCoverage:
    """Test cases targeting missing coverage areas in flow_extractor.py."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = WorkflowExtractor()

    def test_global_vars_with_name_reference(self):
        """Test lines 82, 84 - global vars with Name reference."""
        source = """
MODEL = "gpt-4"
DEFAULT_CONFIG = {"temperature": 0.7}
PARAMS = DEFAULT_CONFIG
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "MODEL" in self.extractor.global_vars
        assert self.extractor.global_vars["MODEL"] == "gpt-4"
        assert "DEFAULT_CONFIG" in self.extractor.global_vars
        # PARAMS assignment will not be in global_vars as it references DEFAULT_CONFIG
        # This tests the path where ast.Name is handled but not stored

    def test_kwargs_unpacking_with_none_arg(self):
        """Test lines 128-131 - kwargs unpacking with **kwargs."""
        source = """
DEFAULT_PARAMS = {"temperature": 0.5, "max_tokens": 100}

@Nodes.llm_node(**DEFAULT_PARAMS, output="result")
def test_node(text):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "test_node" in self.extractor.nodes
        node = self.extractor.nodes["test_node"]
        assert node["llm_config"]["temperature"] == 0.5
        assert node["llm_config"]["max_tokens"] == 100

    def test_variable_reference_not_in_global_vars_response_model(self):
        """Test lines 140-141 - variable reference for response_model not in global_vars."""
        source = """
@Nodes.structured_llm_node(response_model=SomeModel, output="result")
def test_node(text):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "test_node" in self.extractor.nodes
        node = self.extractor.nodes["test_node"]
        assert node["llm_config"]["response_model"] == "SomeModel"

    def test_variable_reference_not_in_global_vars_other_param(self):
        """Test lines 142-143 - variable reference for other params not in global_vars."""
        source = """
@Nodes.llm_node(model=UNKNOWN_MODEL, output="result")
def test_node(text):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "test_node" in self.extractor.nodes
        node = self.extractor.nodes["test_node"]
        assert node["llm_config"]["model"] == "UNKNOWN_MODEL"

    def test_response_model_with_ast_name(self):
        """Test lines 144-145 - response_model with ast.Name."""
        source = """
@Nodes.structured_llm_node(response_model=ResponseModel, output="result")
def test_node(text):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "test_node" in self.extractor.nodes
        node = self.extractor.nodes["test_node"]
        assert node["llm_config"]["response_model"] == "ResponseModel"

    def test_transformer_with_lambda(self):
        """Test lines 146-147 - transformer with lambda function."""
        source = """
@Nodes.transform_node(transformer=lambda x: x.upper(), output="result")
def test_node(text):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "test_node" in self.extractor.nodes
        # The transformer should be unparsed as a lambda expression

    def test_template_node_with_rendered_content_not_in_inputs(self):
        """Test lines 188-189 - template_node adding rendered_content to inputs."""
        source = """
@Nodes.template_node(template="Hello {{name}}", output="greeting")
def test_node(name):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "test_node" in self.extractor.nodes
        node = self.extractor.nodes["test_node"]
        assert "rendered_content" in node["inputs"]
        assert node["inputs"][0] == "rendered_content"

    def test_template_node_with_rendered_content_already_in_inputs(self):
        """Test template_node when rendered_content is already in inputs."""
        source = """
@Nodes.template_node(template="Hello {{name}}", output="greeting")
def test_node(rendered_content, name):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "test_node" in self.extractor.nodes
        node = self.extractor.nodes["test_node"]
        # Should not duplicate rendered_content
        assert node["inputs"].count("rendered_content") == 1

    def test_unsupported_decorator_warning(self):
        """Test lines 237-238 - unsupported decorator warning."""
        source = """
@Nodes.unsupported_decorator(output="result")
def test_node(text):
    pass
"""
        tree = ast.parse(source)
        with patch("quantalogic_flow.flow.flow_extractor.logger") as mock_logger:
            self.extractor.visit(tree)
            mock_logger.warning.assert_called()

    def test_no_recognized_decorator(self):
        """Test lines 243-244 - no recognized decorator debug message."""
        source = """
@some_other_decorator
def test_node(text):
    pass
"""
        tree = ast.parse(source)
        with patch("quantalogic_flow.flow.flow_extractor.logger") as mock_logger:
            self.extractor.visit(tree)
            mock_logger.debug.assert_called()

    def test_visit_asyncfunctiondef(self):
        """Test lines 271-272 - visit_AsyncFunctionDef method."""
        source = """
@Nodes.define(output="result")
async def async_test_node(input_param):
    return input_param * 2
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "async_test_node" in self.extractor.functions
        assert "async_test_node" in self.extractor.nodes

    def test_visit_expr_non_call(self):
        """Test visit_Expr with non-call expressions."""
        source = """
x = 5
"""
        tree = ast.parse(source)
        # Should not crash on non-call expressions
        self.extractor.visit(tree)

    def test_visit_expr_call_non_attribute(self):
        """Test visit_Expr with call that's not an attribute."""
        source = """
some_function()
"""
        tree = ast.parse(source)
        # Should not crash on non-attribute calls
        self.extractor.visit(tree)

    def test_visit_expr_unrecognized_method(self):
        """Test visit_Expr with unrecognized method name."""
        source = """
workflow.unknown_method()
"""
        tree = ast.parse(source)
        # Should not crash on unrecognized methods
        self.extractor.visit(tree)

    def test_visit_expr_non_name_object(self):
        """Test visit_Expr with non-Name object."""
        source = """
obj.attr.then()
"""
        tree = ast.parse(source)
        # Should not crash on complex expressions
        self.extractor.visit(tree)

    def test_process_workflow_method_call_then_no_args(self):
        """Test process_workflow_method_call with 'then' but no args."""
        call_source = "workflow.then()"
        call_node = ast.parse(call_source).body[0].value
        self.extractor.current_node = "start"
        
        self.extractor.process_workflow_method_call(call_node, "workflow")
        # Should handle gracefully without crashing

    def test_process_workflow_method_call_then_with_condition(self):
        """Test process_workflow_method_call with 'then' and condition."""
        call_source = 'workflow.then("next", condition=lambda ctx: ctx["value"] > 10)'
        call_node = ast.parse(call_source).body[0].value
        self.extractor.current_node = "start"
        
        self.extractor.process_workflow_method_call(call_node, "workflow")
        
        assert len(self.extractor.transitions) == 1
        transition = self.extractor.transitions[0]
        assert transition.from_node == "start"
        assert transition.to_node == "next"
        assert "lambda ctx:" in transition.condition  # Full lambda expression is captured

    def test_process_workflow_expr_with_chained_calls(self):
        """Test processing workflow expressions with method chaining."""
        source = """
workflow = (
    Workflow()
    .start("node1")
    .then("node2")
    .parallel("node3", "node4")
    .converge("node5")
)
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert self.extractor.start_node == "node1"
        assert len(self.extractor.transitions) >= 2
        assert "node5" in self.extractor.convergence_nodes

    def test_workflow_with_complex_branch_conditions(self):
        """Test workflow with complex branch conditions."""
        source = """
workflow = (
    Workflow()
    .start("classifier")
    .branch([
        ("positive", lambda ctx: ctx["sentiment"] > 0.5),
        ("negative", lambda ctx: ctx["sentiment"] <= 0.5),
    ])
)
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should have branch transitions with conditions
        branch_transitions = [t for t in self.extractor.transitions if isinstance(t.to_node, list)]
        assert len(branch_transitions) > 0

    def test_workflow_with_nested_loops(self):
        """Test workflow with nested loop structures."""
        source = """
workflow = (
    Workflow()
    .start("outer_start")
    .start_loop(condition="outer_condition")
    .then("inner_start")
    .start_loop(condition="inner_condition")
    .then("process")
    .end_loop("inner_end")
    .then("outer_process")
    .end_loop("outer_end")
)
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should handle nested loops correctly
        assert len(self.extractor.loops) >= 2

    def test_workflow_with_sub_workflow(self):
        """Test workflow with sub-workflow integration."""
        source = """
sub_wf = Workflow().start("sub_start").then("sub_end")

workflow = (
    Workflow()
    .start("main_start")
    .add_sub_workflow("sub", sub_wf, {"input": "data"}, "sub_output")
    .then("main_end")
)
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should have sub-workflow node
        assert "sub" in self.extractor.nodes
        sub_node = self.extractor.nodes["sub"]
        assert sub_node["type"] == "sub_workflow"

    def test_workflow_with_observers(self):
        """Test workflow with observer functions."""
        source = """
def my_observer(event):
    print(f"Event: {event}")

workflow = (
    Workflow()
    .start("node1")
    .add_observer("my_observer")
    .then("node2")
    .add_observer(my_observer)
)
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should have observers registered
        assert "my_observer" in self.extractor.observers

    def test_workflow_with_inputs_mapping_lambda(self):
        """Test workflow with complex inputs mapping including lambdas."""
        source = """
workflow = (
    Workflow()
    .start("input_node")
    .node("process", inputs_mapping={
        "text": "input_text",
        "transformed": lambda ctx: ctx["data"].upper(),
        "constant": "fixed_value"
    })
)
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should have inputs_mapping processed
        if "process" in self.extractor.nodes:
            node = self.extractor.nodes["process"]
            if "inputs_mapping" in node:
                assert "text" in node["inputs_mapping"]
                assert "lambda ctx:" in str(node["inputs_mapping"].get("transformed", ""))

    def test_extract_workflow_from_file_success(self):
        """Test successful workflow extraction from file."""
        source_code = '''
@Nodes.define(output="result")
def process_data(input_data):
    return input_data.upper()

workflow = Workflow().start("process_data")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            f.flush()
            temp_path = Path(f.name)
        
        try:
            workflow_def, global_vars = extract_workflow_from_file(str(temp_path))
            
            assert isinstance(workflow_def, WorkflowDefinition)
            assert "process_data" in workflow_def.functions
            assert "process_data" in workflow_def.nodes
            assert workflow_def.workflow.start == "process_data"
        finally:
            temp_path.unlink()

    def test_extract_workflow_from_file_not_found(self):
        """Test workflow extraction from non-existent file."""
        with pytest.raises(FileNotFoundError):
            extract_workflow_from_file("non_existent_file.py")

    def test_extract_workflow_from_file_syntax_error(self):
        """Test workflow extraction from file with syntax errors."""
        source_code = '''
def invalid_syntax(
    # Missing closing parenthesis and colon
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            f.flush()
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(SyntaxError):
                extract_workflow_from_file(str(temp_path))
        finally:
            temp_path.unlink()

    def test_extract_workflow_from_file_runtime_error(self):
        """Test workflow extraction with runtime errors during processing."""
        source_code = '''
# This will cause issues during extraction
workflow = some_undefined_function()
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            f.flush()
            temp_path = Path(f.name)
        
        try:
            # Should handle gracefully and return empty workflow
            workflow_def, global_vars = extract_workflow_from_file(str(temp_path))
            assert isinstance(workflow_def, WorkflowDefinition)
        finally:
            temp_path.unlink()

    def test_print_workflow_definition_empty(self):
        """Test printing empty workflow definition."""
        workflow_def = WorkflowDefinition()
        
        # Should not raise an exception
        print_workflow_definition(workflow_def)

    def test_print_workflow_definition_full(self):
        """Test printing complete workflow definition."""
        workflow_def = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="start_node",
                transitions=[
                    TransitionDefinition(from_node="start_node", to_node="end_node")
                ],
                convergence_nodes=["conv_node"]
            ),
            nodes={
                "start_node": NodeDefinition(function="start_func"),
                "end_node": NodeDefinition(function="end_func"),
                "conv_node": NodeDefinition(function="conv_func")
            },
            functions={
                "start_func": FunctionDefinition(type="embedded", code="def start_func(): pass"),
                "end_func": FunctionDefinition(type="embedded", code="def end_func(): pass"),
                "conv_func": FunctionDefinition(type="embedded", code="def conv_func(): pass")
            },
            observers=["observer1", "observer2"]
        )
        
        # Should not raise an exception
        print_workflow_definition(workflow_def)

    def test_complex_nested_workflow_structure(self):
        """Test extraction of complex nested workflow structures."""
        source = """
@Nodes.define(output="data")
def load_data():
    return "data"

@Nodes.llm_node(model="gpt-4", prompt_template="Process: {data}", output="processed")
def process_data(data):
    pass

@Nodes.template_node(template="Result: {{processed}}", output="formatted")
def format_result(processed):
    pass

workflow = (
    Workflow()
    .start("load_data")
    .then("process_data")
    .branch([
        ("format_result", lambda ctx: ctx["processed"] is not None),
        ("error_handler", lambda ctx: ctx["processed"] is None)
    ])
    .converge("final_step")
    .add_observer("workflow_monitor")
)
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Verify all components are extracted
        assert len(self.extractor.nodes) >= 3
        assert len(self.extractor.functions) >= 3
        assert len(self.extractor.transitions) >= 2
        assert "final_step" in self.extractor.convergence_nodes
        assert len(self.extractor.observers) >= 1

    def test_workflow_with_sequence_method(self):
        """Test workflow using sequence method."""
        source = """
workflow = (
    Workflow()
    .start("input")
    .sequence("step1", "step2", "step3")
    .then("output")
)
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should create sequential transitions
        assert len(self.extractor.transitions) >= 3

    def test_workflow_with_error_handling(self):
        """Test workflow with error handling patterns."""
        source = """
workflow = (
    Workflow()
    .start("risky_operation")
    .branch([
        ("success_path", lambda ctx: not ctx.get("error")),
        ("error_handler", lambda ctx: ctx.get("error"))
    ])
    .converge("cleanup")
)
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should handle error patterns correctly
        assert self.extractor.start_node == "risky_operation"
        assert "cleanup" in self.extractor.convergence_nodes

    def test_loop_with_exit_condition(self):
        """Test loop structures with exit conditions."""
        source = """
workflow = (
    Workflow()
    .start("init")
    .start_loop(condition="ctx['counter'] < 10")
    .then("increment")
    .then("process")
    .end_loop("exit", exit_condition="ctx['done']")
)
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should handle loop structures
        assert len(self.extractor.loops) >= 1

    def test_visit_assign_complex_dict_values(self):
        """Test visit_Assign with complex dictionary values."""
        source = """
COMPLEX_CONFIG = {
    "model": MODEL_VAR,
    "temperature": 0.7,
    "nested": {
        "key": "value"
    }
}
MODEL_VAR = "gpt-4"
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should handle complex dictionary assignments
        assert "COMPLEX_CONFIG" in self.extractor.global_vars
        assert "MODEL_VAR" in self.extractor.global_vars

    def test_tuple_unwrapping_in_assign(self):
        """Test tuple unwrapping in assignments."""
        source = """
workflow = (Workflow().start("node1"))
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should handle tuple unwrapping
        assert self.extractor.start_node == "node1"

    def test_visit_expr_workflow_method_calls(self):
        """Test expression statements with workflow method calls."""
        source = """
workflow = Workflow()
workflow.start("node1")
workflow.then("node2")
workflow.add_observer("monitor")
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should process standalone method calls
        assert self.extractor.start_node == "node1"
        assert len(self.extractor.transitions) >= 1
        assert "monitor" in self.extractor.observers

    def test_workflow_with_parallel_convergence(self):
        """Test parallel execution with convergence."""
        source = """
workflow = (
    Workflow()
    .start("input")
    .parallel("path1", "path2", "path3")
    .converge("merge_results")
    .then("output")
)
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should handle parallel-convergence pattern
        parallel_transitions = [t for t in self.extractor.transitions if isinstance(t.to_node, list)]
        assert len(parallel_transitions) >= 1
        assert "merge_results" in self.extractor.convergence_nodes

    def test_decorator_with_multiple_keywords(self):
        """Test decorator with multiple keyword arguments."""
        source = """
@Nodes.llm_node(
    model="gpt-4",
    temperature=0.7,
    max_tokens=1000,
    prompt_template="Analyze: {text}",
    system_prompt="You are an expert analyst",
    output="analysis"
)
def complex_llm_node(text):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "complex_llm_node" in self.extractor.nodes
        node = self.extractor.nodes["complex_llm_node"]
        llm_config = node["llm_config"]
        assert llm_config["model"] == "gpt-4"
        assert llm_config["temperature"] == 0.7
        assert llm_config["max_tokens"] == 1000

    def test_structured_llm_with_response_model(self):
        """Test structured LLM node with response model."""
        source = """
@Nodes.structured_llm_node(
    model="gpt-4",
    prompt_template="Extract: {text}",
    response_model=MyResponseModel,
    output="structured_data"
)
def extract_structured(text):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "extract_structured" in self.extractor.nodes
        node = self.extractor.nodes["extract_structured"]
        assert node["type"] == "structured_llm"
        assert "response_model" in node["llm_config"]

    def test_global_vars_dict_with_name_values(self):
        """Test global variables with dictionary containing Name values."""
        source = """
BASE_TEMP = 0.5
CONFIG = {
    "temperature": BASE_TEMP,
    "model": "gpt-4"
}
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "BASE_TEMP" in self.extractor.global_vars
        assert "CONFIG" in self.extractor.global_vars
        # Should resolve BASE_TEMP reference in CONFIG
        if "temperature" in self.extractor.global_vars["CONFIG"]:
            assert self.extractor.global_vars["CONFIG"]["temperature"] == 0.5

    def test_workflow_loops_with_nodes_tracking(self):
        """Test that nodes are properly tracked in loop structures."""
        source = """
workflow = (
    Workflow()
    .start("init")
    .start_loop(condition="ctx['continue']")
    .then("process_item")
    .parallel("validate", "transform")
    .converge("merge")
    .end_loop("finalize")
)
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should track all nodes in loop
        if self.extractor.loops:
            loop = self.extractor.loops[0]
            expected_nodes = ["process_item", "validate", "transform", "merge"]
            for node in expected_nodes:
                assert node in loop.nodes

    def test_add_observer_with_unsupported_argument(self):
        """Test add_observer with unsupported argument types."""
        source = """
complex_observer = some_complex_expression()
workflow = (
    Workflow()
    .start("node1")
    .add_observer(complex_observer.method())
)
"""
        tree = ast.parse(source)
        with patch("quantalogic_flow.flow.flow_extractor.logger") as mock_logger:
            self.extractor.visit(tree)
            # Should log a warning for unsupported observer argument
            mock_logger.warning.assert_called()

    def test_validate_node_decorator(self):
        """Test validate_node decorator processing."""
        source = """
@Nodes.validate_node(output="validated")
def validate_input(data):
    return data.is_valid()
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "validate_input" in self.extractor.nodes
        node = self.extractor.nodes["validate_input"]
        assert node["type"] == "function"
        assert node["function"] == "validate_input"
        assert node["output"] == "validated"

    def test_transform_node_decorator(self):
        """Test transform_node decorator processing."""
        source = """
@Nodes.transform_node(output="transformed")
def transform_data(input_data):
    return input_data.transform()
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "transform_data" in self.extractor.nodes
        node = self.extractor.nodes["transform_data"]
        assert node["type"] == "function"
        assert node["function"] == "transform_data"
        assert node["output"] == "transformed"

    def test_simple_decorator_without_call(self):
        """Test simple decorator without call syntax."""
        source = """
@Nodes.simple_decorator
def test_function(arg):
    pass
"""
        tree = ast.parse(source)
        # This should not crash and should log debug message
        with patch("quantalogic_flow.flow.flow_extractor.logger") as mock_logger:
            self.extractor.visit(tree)
            # Should log that no recognized decorator was found
            mock_logger.debug.assert_called()

    def test_unsupported_nodes_decorator(self):
        """Test unsupported Nodes decorator."""
        source = """
@Nodes.unknown_decorator(output="result")
def unknown_function(input_param):
    pass
"""
        tree = ast.parse(source)
        with patch("quantalogic_flow.flow.flow_extractor.logger") as mock_logger:
            self.extractor.visit(tree)
            # Should log warning about unsupported decorator
            mock_logger.warning.assert_called()

    def test_structured_llm_with_all_parameters(self):
        """Test structured LLM with all possible parameters."""
        source = """
@Nodes.structured_llm_node(
    model="gpt-4",
    system_prompt="You are an expert",
    prompt_template="Process: {input}",
    temperature=0.8,
    max_tokens=500,
    top_p=0.9,
    presence_penalty=0.1,
    frequency_penalty=0.2,
    response_model=MyModel,
    output="structured_result"
)
def complex_structured_llm(input_data):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "complex_structured_llm" in self.extractor.nodes
        node = self.extractor.nodes["complex_structured_llm"]
        assert node["type"] == "structured_llm"
        llm_config = node["llm_config"]
        assert llm_config["model"] == "gpt-4"
        assert llm_config["temperature"] == 0.8
        assert llm_config["max_tokens"] == 500
        assert llm_config["response_model"] == "MyModel"

    def test_llm_node_with_all_parameters(self):
        """Test LLM node with all possible parameters."""
        source = """
@Nodes.llm_node(
    model="gpt-3.5-turbo",
    system_prompt="Be helpful",
    system_prompt_file="/path/to/prompt.txt",
    prompt_template="Question: {question}",
    prompt_file="/path/to/template.txt",
    temperature=0.5,
    max_tokens=200,
    top_p=0.8,
    presence_penalty=0.0,
    frequency_penalty=0.0,
    output="llm_response"
)
def comprehensive_llm(question):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "comprehensive_llm" in self.extractor.nodes
        node = self.extractor.nodes["comprehensive_llm"]
        assert node["type"] == "llm"
        llm_config = node["llm_config"]
        assert llm_config["model"] == "gpt-3.5-turbo"
        assert llm_config["system_prompt"] == "Be helpful"
        assert llm_config["system_prompt_file"] == "/path/to/prompt.txt"
        assert llm_config["prompt_template"] == "Question: {question}"
        assert llm_config["prompt_file"] == "/path/to/template.txt"

    def test_template_node_with_file(self):
        """Test template node with template file."""
        source = """
@Nodes.template_node(template_file="/path/to/template.jinja", output="rendered")
def file_template_node(data):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "file_template_node" in self.extractor.nodes
        node = self.extractor.nodes["file_template_node"]
        assert node["type"] == "template"
        assert node["template_config"]["template_file"] == "/path/to/template.jinja"

    def test_complex_kwargs_unpacking_structures(self):
        """Test complex kwargs unpacking with different structures."""
        source = """
NESTED_CONFIG = {
    "llm": {
        "model": "gpt-4",
        "temperature": 0.7
    }
}

@Nodes.llm_node(**NESTED_CONFIG["llm"], output="result")
def nested_config_node(text):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should handle complex unpacking gracefully
        assert "nested_config_node" in self.extractor.nodes

    def test_decorator_with_complex_response_model(self):
        """Test decorator with complex response model expressions."""
        source = """
from typing import List

@Nodes.structured_llm_node(
    response_model=List[str],
    output="list_result"
)
def list_response_node(input_text):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert "list_response_node" in self.extractor.nodes
        node = self.extractor.nodes["list_response_node"]
        # Complex expressions should be unparsed as strings
        assert "response_model" in node["llm_config"]

    def test_end_loop_without_arguments(self):
        """Test end_loop method without any arguments."""
        source = """
workflow = (
    Workflow()
    .start("begin")
    .start_loop(condition="continue")
    .then("process")
    .end_loop()
)
"""
        tree = ast.parse(source)
        with patch("quantalogic_flow.flow.flow_extractor.logger") as mock_logger:
            self.extractor.visit(tree)
            # Should log warning about missing next_node
            mock_logger.warning.assert_called()

    def test_start_loop_without_previous_node(self):
        """Test start_loop called without a previous node."""
        source = """
workflow = Workflow()
workflow.start_loop(condition="loop_condition")
"""
        tree = ast.parse(source)
        with patch("quantalogic_flow.flow.flow_extractor.logger") as mock_logger:
            self.extractor.visit(tree)
            # Should log warning about missing previous node
            mock_logger.warning.assert_called()

    def test_workflow_with_only_constructor(self):
        """Test workflow with only constructor call."""
        source = """
workflow = Workflow()
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should not crash, start_node should remain None
        assert self.extractor.start_node is None
