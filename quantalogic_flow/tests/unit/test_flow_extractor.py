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


class TestLoopExtraction:
    """Test cases for loop extraction functionality."""

    def test_extract_simple_loop(self):
        """Test extracting a workflow with a simple loop."""
        source_code = '''
from quantalogic_flow.flow.flow import Nodes, Workflow

@Nodes.define(output="counter")
def increment_counter(counter=0):
    return counter + 1

@Nodes.define(output="result")
def process_data(counter):
    return f"Processing {counter}"

workflow = Workflow("increment_counter")
workflow.start_loop()
workflow.then("process_data")
workflow.end_loop(condition="ctx.get('counter', 0) >= 10", next_node="increment_counter")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            temp_file = f.name
        
        try:
            workflow_def, global_vars = extract_workflow_from_file(temp_file)
            
            # Verify basic workflow structure
            assert workflow_def.workflow.start == "increment_counter"
            assert len(workflow_def.nodes) == 2
            assert len(workflow_def.functions) == 2
            
            # Verify loop was extracted
            assert len(workflow_def.workflow.loops) == 1
            loop = workflow_def.workflow.loops[0]
            
            # Verify loop properties
            assert loop.loop_id.startswith("loop_")
            assert loop.entry_node == "increment_counter"
            assert "process_data" in loop.nodes
            assert loop.condition == "ctx.get('counter', 0) >= 10"
            assert loop.exit_node == "increment_counter"
            assert len(loop.nested_loops) == 0  # No nested loops
            
            # Verify loop transitions were created
            loop_transitions = [t for t in workflow_def.workflow.transitions 
                             if t.condition and ("not (" in t.condition or "ctx.get('counter', 0) >= 10" in t.condition)]
            assert len(loop_transitions) >= 2  # Loop-back and exit transitions
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_nested_loops(self):
        """Test extracting a workflow with nested loops."""
        source_code = '''
from quantalogic_flow.flow.flow import Nodes, Workflow

@Nodes.define(output="outer_counter")
def outer_increment(outer_counter=0):
    return outer_counter + 1

@Nodes.define(output="inner_counter")
def inner_increment(inner_counter=0):
    return inner_counter + 1

@Nodes.define(output="result")
def process_inner(outer_counter, inner_counter):
    return f"Outer: {outer_counter}, Inner: {inner_counter}"

@Nodes.define(output="outer_result")
def process_outer(outer_counter):
    return f"Outer complete: {outer_counter}"

workflow = Workflow("outer_increment")
workflow.start_loop()  # Outer loop
workflow.then("inner_increment")
workflow.start_loop()  # Inner loop (nested)
workflow.then("process_inner")
workflow.end_loop(condition="ctx.get('inner_counter', 0) >= 5", next_node="process_outer")
workflow.then("process_outer")
workflow.end_loop(condition="ctx.get('outer_counter', 0) >= 3", next_node="outer_increment")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            temp_file = f.name
        
        try:
            workflow_def, global_vars = extract_workflow_from_file(temp_file)
            
            # Verify basic workflow structure
            assert workflow_def.workflow.start == "outer_increment"
            assert len(workflow_def.nodes) == 4
            assert len(workflow_def.functions) == 4
            
            # Verify nested loop structure - should have 1 top-level loop with 1 nested loop
            assert len(workflow_def.workflow.loops) == 1
            
            # Get the top-level (outer) loop
            outer_loop = workflow_def.workflow.loops[0]
            
            # Verify outer loop structure
            assert outer_loop.entry_node == "outer_increment"
            assert "inner_increment" in outer_loop.nodes
            assert "process_outer" in outer_loop.nodes
            assert outer_loop.condition == "ctx.get('outer_counter', 0) >= 3"
            assert outer_loop.exit_node == "outer_increment"
            
            # Verify nested loop structure
            assert len(outer_loop.nested_loops) == 1
            inner_loop = outer_loop.nested_loops[0]
            
            # Verify inner loop
            assert inner_loop.entry_node == "inner_increment"
            assert "process_inner" in inner_loop.nodes
            assert inner_loop.condition == "ctx.get('inner_counter', 0) >= 5"
            assert inner_loop.exit_node == "process_outer"
            assert len(inner_loop.nested_loops) == 0  # Inner loop has no nested loops
            
            # Verify transitions include loop logic
            all_transitions = workflow_def.workflow.transitions
            loop_transitions = [t for t in all_transitions if t.condition and ("not (" in t.condition)]
            assert len(loop_transitions) >= 2  # At least one for each loop
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_extract_complex_nested_loops(self):
        """Test extracting a workflow with multiple levels of nested loops."""
        source_code = '''
from quantalogic_flow.flow.flow import Nodes, Workflow

@Nodes.define(output="level_a")
def increment_a(level_a=0):
    return level_a + 1

@Nodes.define(output="level_b")
def increment_b(level_b=0):
    return level_b + 1

@Nodes.define(output="level_c")
def increment_c(level_c=0):
    return level_c + 1

@Nodes.define(output="deep_result")
def process_deepest(level_a, level_b, level_c):
    return f"A:{level_a}, B:{level_b}, C:{level_c}"

workflow = Workflow("increment_a")
workflow.start_loop()  # Level A loop
workflow.then("increment_b")
workflow.start_loop()  # Level B loop (nested in A)
workflow.then("increment_c")
workflow.start_loop()  # Level C loop (nested in B)
workflow.then("process_deepest")
workflow.end_loop(condition="ctx.get('level_c', 0) >= 2", next_node="increment_b")
workflow.end_loop(condition="ctx.get('level_b', 0) >= 3", next_node="increment_a")
workflow.end_loop(condition="ctx.get('level_a', 0) >= 4", next_node="increment_a")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            temp_file = f.name
        
        try:
            workflow_def, global_vars = extract_workflow_from_file(temp_file)
            
            # Verify nested loop structure - should have 1 top-level loop with 2 levels of nesting
            assert len(workflow_def.workflow.loops) == 1
            
            # Get the top-level loop (Level A)
            level_a_loop = workflow_def.workflow.loops[0]
            
            # Verify Level A loop
            assert level_a_loop.entry_node == "increment_a"
            assert "increment_b" in level_a_loop.nodes
            assert "increment_c" in level_a_loop.nodes
            assert "process_deepest" in level_a_loop.nodes
            assert level_a_loop.condition == "ctx.get('level_a', 0) >= 4"
            assert level_a_loop.exit_node == "increment_a"
            
            # Verify Level B loop (nested in A)
            assert len(level_a_loop.nested_loops) == 1
            level_b_loop = level_a_loop.nested_loops[0]
            
            assert level_b_loop.entry_node == "increment_b"
            assert "increment_c" in level_b_loop.nodes
            assert "process_deepest" in level_b_loop.nodes
            assert level_b_loop.condition == "ctx.get('level_b', 0) >= 3"
            assert level_b_loop.exit_node == "increment_a"
            
            # Verify Level C loop (nested in B)
            assert len(level_b_loop.nested_loops) == 1
            level_c_loop = level_b_loop.nested_loops[0]
            
            assert level_c_loop.entry_node == "increment_c"
            assert "process_deepest" in level_c_loop.nodes
            assert level_c_loop.condition == "ctx.get('level_c', 0) >= 2"
            assert level_c_loop.exit_node == "increment_b"
            assert len(level_c_loop.nested_loops) == 0  # Deepest level has no nested loops
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_loop_extraction_with_other_workflow_elements(self):
        """Test loop extraction in a workflow with branches, convergence, and observers."""
        source_code = '''
from quantalogic_flow.flow.flow import Nodes, Workflow

@Nodes.define(output="init_data")
def initialize():
    return {"counter": 0, "type": "normal"}

@Nodes.define(output="counter")
def increment(counter):
    return counter + 1

@Nodes.define(output="result_a")
def process_a(counter):
    return f"A: {counter}"

@Nodes.define(output="result_b")
def process_b(counter):
    return f"B: {counter}"

@Nodes.define(output="merged")
def merge_results(result_a, result_b):
    return f"Merged: {result_a} + {result_b}"

@Nodes.define(output="final")
def finalize(merged):
    return f"Final: {merged}"

def monitor_loop(event):
    print(f"Loop event: {event}")

workflow = Workflow("initialize")
workflow.then("increment")
workflow.start_loop()
workflow.branch([
    ("process_a", lambda ctx: ctx.get("type") == "normal"),
    ("process_b", lambda ctx: ctx.get("type") == "special")
])
workflow.converge("merge_results")
workflow.end_loop(condition="ctx.get('counter', 0) >= 5", next_node="finalize")
workflow.then("finalize")
workflow.add_observer(monitor_loop)
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            temp_file = f.name
        
        try:
            workflow_def, global_vars = extract_workflow_from_file(temp_file)
            
            # Verify all elements are present
            assert len(workflow_def.nodes) == 6
            assert len(workflow_def.functions) == 6
            assert len(workflow_def.workflow.loops) == 1
            assert len(workflow_def.workflow.convergence_nodes) == 1
            assert len(workflow_def.observers) == 1
            
            # Verify loop structure
            loop = workflow_def.workflow.loops[0]
            assert loop.entry_node == "increment"
            assert "process_a" in loop.nodes or "process_b" in loop.nodes  # Branch nodes should be in loop
            assert "merge_results" in loop.nodes  # Convergence node should be in loop
            assert loop.condition == "ctx.get('counter', 0) >= 5"
            assert loop.exit_node == "finalize"
            
            # Verify convergence node
            assert "merge_results" in workflow_def.workflow.convergence_nodes
            
            # Verify observer
            assert "monitor_loop" in workflow_def.observers
            
            # Verify transitions include branches and loop logic
            transitions = workflow_def.workflow.transitions
            branch_transitions = [t for t in transitions if t.condition and "type" in t.condition]
            loop_transitions = [t for t in transitions if t.condition and ("not (" in t.condition or "counter" in t.condition)]
            
            assert len(branch_transitions) >= 2  # Branch conditions
            assert len(loop_transitions) >= 2   # Loop back and exit
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_loop_round_trip_integrity(self):
        """Test that extracted loops can be regenerated and re-extracted maintaining structure."""
        # Skip this test for now due to import issues
        pytest.skip("Skipping round-trip test due to import issues")

    def test_loop_with_empty_body(self):
        """Test extracting a loop with no nodes between start_loop and end_loop."""
        source_code = '''
from quantalogic_flow.flow.flow import Nodes, Workflow

@Nodes.define(output="counter")
def increment(counter=0):
    return counter + 1

workflow = Workflow("increment")
workflow.start_loop()
workflow.end_loop(condition="ctx.get('counter', 0) >= 10", next_node="increment")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            temp_file = f.name
        
        try:
            workflow_def, global_vars = extract_workflow_from_file(temp_file)
            
            # Should still create a loop, even if empty
            assert len(workflow_def.workflow.loops) == 1
            loop = workflow_def.workflow.loops[0]
            
            assert loop.entry_node == "increment"
            assert len(loop.nodes) == 0  # Empty loop body
            assert loop.condition == "ctx.get('counter', 0) >= 10"
            assert loop.exit_node == "increment"
            
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_malformed_loop_handling(self):
        """Test handling of malformed loop constructs."""
        # Test start_loop without end_loop
        source_code1 = '''
from quantalogic_flow.flow.flow import Nodes, Workflow

@Nodes.define(output="data")
def process():
    return "data"

workflow = Workflow("process")
workflow.start_loop()
workflow.then("process")
# Missing end_loop
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code1)
            temp_file1 = f.name
        
        try:
            workflow_def, global_vars = extract_workflow_from_file(temp_file1)
            
            # Should not create incomplete loops
            # The extractor should handle this gracefully without crashing
            assert isinstance(workflow_def, WorkflowDefinition)
            assert len(workflow_def.nodes) >= 1
            
        finally:
            Path(temp_file1).unlink(missing_ok=True)
        
        # Test end_loop without start_loop
        source_code2 = '''
from quantalogic_flow.flow.flow import Nodes, Workflow

@Nodes.define(output="data")
def process():
    return "data"

workflow = Workflow("process")
workflow.then("process")
workflow.end_loop(condition="False", next_node="process")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code2)
            temp_file2 = f.name
        
        try:
            workflow_def, global_vars = extract_workflow_from_file(temp_file2)
            
            # Should handle gracefully without creating invalid loops
            assert isinstance(workflow_def, WorkflowDefinition)
            # Should not have created any loops from malformed construct
            assert len(workflow_def.workflow.loops) == 0
            
        finally:
            Path(temp_file2).unlink(missing_ok=True)


class TestNestedLoopRoundTrip:
    """Test round-trip integrity for nested loops specifically."""

    def test_deeply_nested_loop_round_trip(self):
        """Test round-trip for deeply nested loops (3+ levels)."""
        # Skip this test for now due to import issues
        pytest.skip("Skipping round-trip test due to import issues")

    def test_mixed_nested_and_sequential_loops(self):
        """Test extraction of workflows with both nested loops and sequential loops."""
        source_code = '''
from quantalogic_flow.flow.flow import Nodes, Workflow

@Nodes.define(output="counter1")
def count1(counter1=0):
    return counter1 + 1

@Nodes.define(output="counter2")
def count2(counter2=0):
    return counter2 + 1

@Nodes.define(output="counter3")
def count3(counter3=0):
    return counter3 + 1

@Nodes.define(output="result")
def process_all(counter1, counter2, counter3):
    return f"All: {counter1}, {counter2}, {counter3}"

workflow = Workflow("count1")
# First loop (with nested loop)
workflow.start_loop()
workflow.then("count2")
workflow.start_loop()  # Nested in first loop
workflow.then("process_all")
workflow.end_loop(condition="ctx.get('counter2', 0) >= 3", next_node="count1")
workflow.end_loop(condition="ctx.get('counter1', 0) >= 2", next_node="count3")

# Second loop (sequential, not nested)
workflow.then("count3")
workflow.start_loop()
workflow.then("process_all")
workflow.end_loop(condition="ctx.get('counter3', 0) >= 5", next_node="count3")
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            temp_file = f.name
        
        try:
            workflow_def, global_vars = extract_workflow_from_file(temp_file)
            
            # Should have 2 top-level loops: one with nesting + one sequential
            assert len(workflow_def.workflow.loops) == 2
            
            # Sort loops by entry node to identify them
            loops = sorted(workflow_def.workflow.loops, key=lambda x: x.entry_node)
            
            # Identify the loops
            nested_parent = None
            sequential_loop = None
            
            for loop in loops:
                if len(loop.nested_loops) > 0:
                    nested_parent = loop
                elif loop.entry_node == "count3":
                    sequential_loop = loop
            
            assert nested_parent is not None
            assert sequential_loop is not None
            
            # Verify nested structure
            assert len(nested_parent.nested_loops) == 1
            nested_child = nested_parent.nested_loops[0]
            assert nested_child.entry_node == "count2"
            
            # Verify sequential loop has no nesting
            assert len(sequential_loop.nested_loops) == 0
            
        finally:
            Path(temp_file).unlink(missing_ok=True)
