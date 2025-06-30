"""Tests for the WorkflowExtractor class and flow extraction functionality.

This test suite is designed to test the actual implementation of flow_extractor.py,
focusing on extracting workflow definitions from Python source code.
"""

import ast
import tempfile
from pathlib import Path

import pytest

from quantalogic_flow.flow.flow_extractor import (
    WorkflowExtractor,
    extract_workflow_from_file,
    print_workflow_definition,
)
from quantalogic_flow.flow.flow_manager_schema import (
    FunctionDefinition,
    LLMConfig,
    NodeDefinition,
    TemplateConfig,
    TransitionDefinition,
    WorkflowDefinition,
    WorkflowStructure,
)


class TestWorkflowExtractor:
    """Test cases for WorkflowExtractor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = WorkflowExtractor()

    def test_extractor_initialization(self):
        """Test that WorkflowExtractor initializes correctly."""
        assert self.extractor.functions == {}
        assert self.extractor.nodes == {}
        assert self.extractor.transitions == []
        assert self.extractor.convergence_nodes == []
        assert self.extractor.observers == []
        assert self.extractor.global_vars == {}
        assert self.extractor.start_node is None

    def test_visit_module_empty(self):
        """Test visiting an empty module."""
        source = ""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        assert len(self.extractor.functions) == 0
        assert len(self.extractor.nodes) == 0
        assert len(self.extractor.transitions) == 0

    def test_visit_module_with_simple_function(self):
        """Test visiting a module with a simple function (no decorators)."""
        source = """
def simple_function():
    return "hello"
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Simple functions without decorators should not be extracted
        assert len(self.extractor.functions) == 0
        assert len(self.extractor.nodes) == 0

    def test_visit_function_with_nodes_define_decorator(self):
        """Test visiting a function with @Nodes.define decorator."""
        source = """
@Nodes.define(output="result")
def test_node(input_param):
    return input_param * 2
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should extract the function and create a node
        assert "test_node" in self.extractor.functions
        assert "test_node" in self.extractor.nodes
        
        func_def = self.extractor.functions["test_node"]
        assert func_def["type"] == "embedded"
        assert "def test_node(input_param):" in func_def["code"]
        
        node_info = self.extractor.nodes["test_node"]
        assert node_info["type"] == "function"
        assert node_info["function"] == "test_node"
        assert node_info["output"] == "result"

    def test_visit_function_with_llm_node_decorator(self):
        """Test visiting a function with @Nodes.llm_node decorator."""
        source = """
@Nodes.llm_node(
    model="gpt-4",
    prompt_template="Analyze: {text}",
    output="analysis"
)
def analyze_text(text):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should extract the function and create an LLM node
        assert "analyze_text" in self.extractor.functions
        assert "analyze_text" in self.extractor.nodes
        
        node_info = self.extractor.nodes["analyze_text"]
        assert node_info["type"] == "llm"
        assert node_info["output"] == "analysis"
        assert "model" in node_info["llm_config"]
        assert node_info["llm_config"]["model"] == "gpt-4"
        assert node_info["llm_config"]["prompt_template"] == "Analyze: {text}"

    def test_visit_function_with_structured_llm_decorator(self):
        """Test visiting a function with @Nodes.structured_llm_node decorator."""
        source = """
@Nodes.structured_llm_node(
    model="gpt-4",
    prompt_template="Extract data from: {text}",
    response_model="my_module:MyModel",
    output="structured_data"
)
def extract_data(text):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should extract the function and create a structured LLM node
        assert "extract_data" in self.extractor.functions
        assert "extract_data" in self.extractor.nodes
        
        node_info = self.extractor.nodes["extract_data"]
        assert node_info["type"] == "structured_llm"
        assert node_info["output"] == "structured_data"
        assert "response_model" in node_info["llm_config"]
        assert node_info["llm_config"]["response_model"] == "my_module:MyModel"

    def test_visit_function_with_template_decorator(self):
        """Test visiting a function with @Nodes.template_node decorator."""
        source = """
@Nodes.template_node(
    template="Hello {{name}}!",
    output="greeting"
)
def generate_greeting(name):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should extract the function and create a template node
        assert "generate_greeting" in self.extractor.functions
        assert "generate_greeting" in self.extractor.nodes
        
        node_info = self.extractor.nodes["generate_greeting"]
        assert node_info["type"] == "template"
        assert node_info["output"] == "greeting"
        assert "template" in node_info["template_config"]
        assert node_info["template_config"]["template"] == "Hello {{name}}!"

    def test_visit_async_function_def(self):
        """Test visiting an async function definition."""
        source = """
@Nodes.define(output="async_result")
async def async_node(data):
    return await process_data(data)
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should extract async function
        assert "async_node" in self.extractor.functions
        assert "async_node" in self.extractor.nodes
        
        func_def = self.extractor.functions["async_node"]
        assert func_def["type"] == "embedded"
        assert "async def async_node(data):" in func_def["code"]

    def test_visit_assign_global_variable(self):
        """Test visiting global variable assignments."""
        source = """
API_KEY = "secret-key"
MODEL_NAME = "gpt-4"
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should capture global variables
        assert "API_KEY" in self.extractor.global_vars
        assert "MODEL_NAME" in self.extractor.global_vars
        assert self.extractor.global_vars["API_KEY"] == "secret-key"
        assert self.extractor.global_vars["MODEL_NAME"] == "gpt-4"

    def test_visit_assign_workflow_creation(self):
        """Test visiting workflow creation assignment."""
        source = """
workflow = Workflow("start_node")
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should set start node
        assert self.extractor.start_node == "start_node"

    def test_process_workflow_then_method(self):
        """Test processing workflow.then() method calls."""
        source = """
workflow = Workflow("start")
workflow.then("next_node")
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)

        # Should create transition
        assert len(self.extractor.transitions) == 1
        transition = self.extractor.transitions[0]
        assert transition.from_node == "start"
        assert transition.to_node == "next_node"
        assert transition.condition is None

    def test_process_workflow_then_with_condition(self):
        """Test processing workflow.then() with condition."""
        source = """
workflow = Workflow("start")
workflow.then("next_node", condition=lambda ctx: ctx.get("continue"))
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should create conditional transition
        assert len(self.extractor.transitions) == 1
        transition = self.extractor.transitions[0]
        assert transition.from_node == "start"
        assert transition.to_node == "next_node"
        assert transition.condition is not None

    def test_process_workflow_parallel_method(self):
        """Test processing workflow.parallel() method calls."""
        source = """
workflow = Workflow("start")
workflow.parallel("node1", "node2", "node3")
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should create parallel transitions
        assert len(self.extractor.transitions) == 1
        transition = self.extractor.transitions[0]
        assert transition.from_node == "start"
        assert isinstance(transition.to_node, list)
        assert "node1" in transition.to_node
        assert "node2" in transition.to_node
        assert "node3" in transition.to_node

    def test_process_workflow_branch_method(self):
        """Test processing workflow.branch() method calls."""
        source = """
workflow = Workflow("start")
workflow.branch([
    ("path1", lambda ctx: ctx.get("type") == "A"),
    ("path2", lambda ctx: ctx.get("type") == "B")
])
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should create branching transitions
        assert len(self.extractor.transitions) == 2
        transitions = self.extractor.transitions
        assert transitions[0].from_node == "start"
        assert transitions[1].from_node == "start"
        target_nodes = [t.to_node for t in transitions]
        assert "path1" in target_nodes
        assert "path2" in target_nodes

    def test_process_workflow_converge_method(self):
        """Test processing workflow.converge() method calls."""
        source = """
workflow = Workflow("start")
workflow.converge("merge_node")
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should add convergence node
        assert "merge_node" in self.extractor.convergence_nodes

    def test_process_workflow_add_observer(self):
        """Test processing workflow.add_observer() method calls."""
        source = """
workflow = Workflow("start")
workflow.add_observer(monitor_function)
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should add observer
        assert len(self.extractor.observers) == 1

    def test_process_workflow_node_with_inputs_mapping(self):
        """Test processing workflow.node() with inputs mapping."""
        source = """
workflow = Workflow("start")
workflow.node("processor", inputs_mapping={"data": "input_data"})
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should create node with inputs mapping
        assert "processor" in self.extractor.nodes
        node_info = self.extractor.nodes["processor"]
        assert "inputs_mapping" in node_info
        assert node_info["inputs_mapping"]["data"] == "input_data"

    def test_multiple_decorated_functions(self):
        """Test extracting multiple decorated functions."""
        source = """
@Nodes.define(output="result1")
def func1(x):
    return x + 1

@Nodes.llm_node(model="gpt-4", prompt_template="Process: {text}", output="result2")
def func2(text):
    pass

@Nodes.template_node(template="Hello {{name}}", output="result3")
def func3(name):
    pass
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should extract all three functions and nodes
        assert len(self.extractor.functions) == 3
        assert len(self.extractor.nodes) == 3
        assert "func1" in self.extractor.functions
        assert "func2" in self.extractor.functions
        assert "func3" in self.extractor.functions

    def test_complex_workflow_chain(self):
        """Test extracting a complex workflow with chained method calls."""
        source = """
@Nodes.define(output="processed")
def processor(data):
    return data.upper()

@Nodes.define(output="final")
def finalizer(data):
    return f"Final: {data}"

workflow = Workflow("processor")
workflow.then("finalizer")
workflow.add_observer(monitor)
"""
        tree = ast.parse(source)
        self.extractor.visit(tree)
        
        # Should extract everything correctly
        assert len(self.extractor.functions) == 2
        assert len(self.extractor.nodes) == 2
        assert len(self.extractor.transitions) == 1
        assert len(self.extractor.observers) == 1
        assert self.extractor.start_node == "processor"


class TestExtractWorkflowFromFile:
    """Test cases for extract_workflow_from_file function."""

    def test_extract_from_simple_file(self):
        """Test extracting workflow from a simple Python file."""
        source_code = '''
from quantalogic_flow.flow.flow import Nodes, Workflow

@Nodes.define(output="greeting")
def greet(name):
    return f"Hello, {name}!"

@Nodes.define(output="farewell")
def say_goodbye(name):
    return f"Goodbye, {name}!"

workflow = Workflow("greet")
workflow.then("say_goodbye")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            temp_file = f.name
        
        try:
            workflow_def, global_vars = extract_workflow_from_file(temp_file)
            
            # Verify workflow definition structure
            assert isinstance(workflow_def, WorkflowDefinition)
            assert workflow_def.workflow.start == "greet"
            assert len(workflow_def.functions) == 2
            assert len(workflow_def.nodes) == 2
            assert len(workflow_def.workflow.transitions) == 1
            
            # Verify functions
            assert "greet" in workflow_def.functions
            assert "say_goodbye" in workflow_def.functions
            assert workflow_def.functions["greet"].type == "embedded"
            
            # Verify nodes
            assert "greet" in workflow_def.nodes
            assert "say_goodbye" in workflow_def.nodes
            greet_node = workflow_def.nodes["greet"]
            assert greet_node.function == "greet"
            assert greet_node.output == "greeting"
            
            # Verify transitions
            transition = workflow_def.workflow.transitions[0]
            assert transition.from_node == "greet"
            assert transition.to_node == "say_goodbye"
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_from_file_with_llm_nodes(self):
        """Test extracting workflow with LLM nodes."""
        source_code = '''
from quantalogic_flow.flow.flow import Nodes, Workflow

@Nodes.llm_node(
    model="gpt-4",
    prompt_template="Summarize this text: {text}",
    output="summary"
)
def summarize(text):
    pass

@Nodes.structured_llm_node(
    model="gpt-4",
    prompt_template="Extract entities from: {text}",
    response_model="my_module:EntityModel",
    output="entities"
)
def extract_entities(text):
    pass

workflow = Workflow("summarize")
workflow.then("extract_entities")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            temp_file = f.name
        
        try:
            workflow_def, global_vars = extract_workflow_from_file(temp_file)
            
            # Verify LLM nodes
            assert len(workflow_def.nodes) == 2
            
            summarize_node = workflow_def.nodes["summarize"]
            assert summarize_node.llm_config is not None
            assert summarize_node.llm_config.model == "gpt-4"
            assert summarize_node.llm_config.prompt_template == "Summarize this text: {text}"
            
            entities_node = workflow_def.nodes["extract_entities"]
            assert entities_node.llm_config is not None
            assert entities_node.llm_config.response_model == "my_module:EntityModel"
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_from_file_with_template_nodes(self):
        """Test extracting workflow with template nodes."""
        source_code = '''
from quantalogic_flow.flow.flow import Nodes, Workflow

@Nodes.template_node(
    template="Dear {{name}},\\n\\nYour order {{order_id}} is ready.\\n\\nBest regards",
    output="email_content"
)
def generate_email(name, order_id):
    pass

workflow = Workflow("generate_email")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            temp_file = f.name
        
        try:
            workflow_def, global_vars = extract_workflow_from_file(temp_file)
            
            # Verify template node
            assert len(workflow_def.nodes) == 1
            
            email_node = workflow_def.nodes["generate_email"]
            assert email_node.template_config is not None
            assert "Dear {{name}}" in email_node.template_config.template
            assert email_node.output == "email_content"
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_from_file_with_global_vars(self):
        """Test extracting workflow with global variables."""
        source_code = '''
from quantalogic_flow.flow.flow import Nodes, Workflow

API_KEY = "test-key"
MODEL = "gpt-4"
DEBUG = True

@Nodes.define(output="result")
def process_data(data):
    return data

workflow = Workflow("process_data")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            temp_file = f.name
        
        try:
            workflow_def, global_vars = extract_workflow_from_file(temp_file)
            
            # Verify global variables
            assert "API_KEY" in global_vars
            assert "MODEL" in global_vars
            assert "DEBUG" in global_vars
            assert global_vars["API_KEY"] == "test-key"
            assert global_vars["MODEL"] == "gpt-4"
            assert global_vars["DEBUG"] is True
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_from_nonexistent_file(self):
        """Test extracting from a file that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            extract_workflow_from_file("nonexistent_file.py")

    def test_extract_from_file_with_syntax_error(self):
        """Test extracting from a file with syntax errors."""
        source_code = '''
def invalid_syntax(
    # Missing closing parenthesis
    return "error"
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            temp_file = f.name
        
        try:
            with pytest.raises(SyntaxError):
                extract_workflow_from_file(temp_file)
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_from_empty_file(self):
        """Test extracting from an empty file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("")
            temp_file = f.name
        
        try:
            workflow_def, global_vars = extract_workflow_from_file(temp_file)
            
            # Should return empty workflow definition
            assert isinstance(workflow_def, WorkflowDefinition)
            assert len(workflow_def.functions) == 0
            assert len(workflow_def.nodes) == 0
            assert len(workflow_def.workflow.transitions) == 0
            assert global_vars == {}
            
        finally:
            Path(temp_file).unlink(missing_ok=True)


class TestPrintWorkflowDefinition:
    """Test cases for print_workflow_definition function."""

    def test_print_simple_workflow(self, capsys):
        """Test printing a simple workflow definition."""
        workflow_def = WorkflowDefinition(
            functions={
                "test_func": FunctionDefinition(
                    type="embedded",
                    code="def test_func():\n    return 'test'"
                )
            },
            nodes={
                "test_node": NodeDefinition(
                    function="test_func",
                    output="test_result"
                )
            },
            workflow=WorkflowStructure(
                start="test_node",
                transitions=[]
            )
        )
        
        print_workflow_definition(workflow_def)
        captured = capsys.readouterr()
        
        # Verify output contains expected sections
        assert "### Workflow Definition ###" in captured.out
        assert "#### Functions:" in captured.out
        assert "#### Nodes:" in captured.out
        assert "#### Workflow Structure:" in captured.out
        assert "test_func" in captured.out
        assert "test_node" in captured.out

    def test_print_workflow_with_llm_nodes(self, capsys):
        """Test printing a workflow with LLM nodes."""
        workflow_def = WorkflowDefinition(
            functions={
                "llm_func": FunctionDefinition(
                    type="embedded",
                    code="def llm_func(): pass"
                )
            },
            nodes={
                "llm_node": NodeDefinition(
                    llm_config=LLMConfig(
                        model="gpt-4",
                        prompt_template="Process: {text}"
                    ),
                    output="llm_result"
                )
            },
            workflow=WorkflowStructure(
                start="llm_node",
                transitions=[]
            )
        )
        
        print_workflow_definition(workflow_def)
        captured = capsys.readouterr()
        
        # Verify LLM-specific output
        assert "Type: LLM" in captured.out
        assert "Model: gpt-4" in captured.out
        assert "Prompt Template: Process: {text}" in captured.out

    def test_print_workflow_with_template_nodes(self, capsys):
        """Test printing a workflow with template nodes."""
        workflow_def = WorkflowDefinition(
            functions={
                "template_func": FunctionDefinition(
                    type="embedded",
                    code="def template_func(): pass"
                )
            },
            nodes={
                "template_node": NodeDefinition(
                    template_config=TemplateConfig(
                        template="Hello {{name}}!"
                    ),
                    output="template_result"
                )
            },
            workflow=WorkflowStructure(
                start="template_node",
                transitions=[]
            )
        )
        
        print_workflow_definition(workflow_def)
        captured = capsys.readouterr()
        
        # Verify template-specific output
        assert "Type: Template" in captured.out
        assert "Template: Hello {{name}}!" in captured.out

    def test_print_workflow_with_transitions(self, capsys):
        """Test printing a workflow with transitions."""
        workflow_def = WorkflowDefinition(
            functions={},
            nodes={},
            workflow=WorkflowStructure(
                start="start_node",
                transitions=[
                    TransitionDefinition(
                        from_node="start_node",
                        to_node="end_node",
                        condition="ctx.get('continue')"
                    )
                ]
            )
        )
        
        print_workflow_definition(workflow_def)
        captured = capsys.readouterr()
        
        # Verify transition output
        assert "Transitions:" in captured.out
        assert "start_node -> end_node" in captured.out
        assert "[Condition: ctx.get('continue')]" in captured.out


class TestWorkflowExtractionIntegration:
    """Integration tests for workflow extraction functionality."""

    def test_complete_workflow_extraction(self):
        """Test extracting a complete workflow with all features."""
        source_code = '''
from quantalogic_flow.flow.flow import Nodes, Workflow

# Global configuration
API_KEY = "test-api-key"
MODEL_NAME = "gpt-4"

@Nodes.define(output="user_input")
def get_user_input():
    return input("Enter your text: ")

@Nodes.llm_node(
    model=MODEL_NAME,
    prompt_template="Analyze the sentiment of: {text}",
    output="sentiment"
)
def analyze_sentiment(text):
    pass

@Nodes.template_node(
    template="Sentiment: {{sentiment}}\\nOriginal: {{text}}",
    output="report"
)
def generate_report(sentiment, text):
    pass

def monitor_execution(event):
    print(f"Event: {event}")

# Workflow definition
workflow = Workflow("get_user_input")
workflow.then("analyze_sentiment")
workflow.then("generate_report")
workflow.add_observer(monitor_execution)
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            temp_file = f.name
        
        try:
            workflow_def, global_vars = extract_workflow_from_file(temp_file)
            
            # Verify complete extraction
            assert workflow_def.workflow.start == "get_user_input"
            assert len(workflow_def.functions) == 3
            assert len(workflow_def.nodes) == 3
            assert len(workflow_def.workflow.transitions) == 2
            assert len(workflow_def.observers) == 1
            
            # Verify global variables
            assert global_vars["API_KEY"] == "test-api-key"
            assert global_vars["MODEL_NAME"] == "gpt-4"
            
            # Verify different node types
            input_node = workflow_def.nodes["get_user_input"]
            assert input_node.function == "get_user_input"
            
            sentiment_node = workflow_def.nodes["analyze_sentiment"]
            assert sentiment_node.llm_config is not None
            assert sentiment_node.llm_config.model == "gpt-4"
            
            report_node = workflow_def.nodes["generate_report"]
            assert report_node.template_config is not None
            
            # Verify transitions
            transitions = workflow_def.workflow.transitions
            assert transitions[0].from_node == "get_user_input"
            assert transitions[0].to_node == "analyze_sentiment"
            assert transitions[1].from_node == "analyze_sentiment"
            assert transitions[1].to_node == "generate_report"
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_workflow_with_complex_chaining(self):
        """Test extracting workflow with complex method chaining."""
        source_code = '''
from quantalogic_flow.flow.flow import Nodes, Workflow

@Nodes.define(output="data")
def process_data():
    return {"type": "important", "value": 42}

@Nodes.define(output="result_a")
def process_a(data):
    return f"A: {data}"

@Nodes.define(output="result_b")
def process_b(data):
    return f"B: {data}"

@Nodes.define(output="final_result")
def merge_results(result_a, result_b):
    return f"Final: {result_a} + {result_b}"

workflow = Workflow("process_data")
workflow.branch([
    ("process_a", lambda ctx: ctx.get("data", {}).get("type") == "important"),
    ("process_b", lambda ctx: ctx.get("data", {}).get("type") == "normal")
])
workflow.converge("merge_results")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            temp_file = f.name
        
        try:
            workflow_def, global_vars = extract_workflow_from_file(temp_file)
            
            # Verify branching structure
            assert len(workflow_def.workflow.transitions) == 2  # branch and converge
            assert len(workflow_def.workflow.convergence_nodes) == 1
            assert "merge_results" in workflow_def.workflow.convergence_nodes
            
        finally:
            Path(temp_file).unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__])
