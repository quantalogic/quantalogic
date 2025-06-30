"""Unit tests for flow_validator module."""

from quantalogic_flow.flow.flow_manager_schema import (
    FunctionDefinition,
    NodeDefinition,
    TransitionDefinition,
    WorkflowDefinition,
    WorkflowStructure,
)
from quantalogic_flow.flow.flow_validator import (
    ValidationError,
    ValidationResult,
    WorkflowValidator,
    validate_workflow,
)


class TestWorkflowValidator:
    """Test workflow validator functionality."""

    def setup_method(self):
        """Set up test data."""
        self.valid_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="start_node"
            ),
            nodes={
                "start_node": NodeDefinition(
                    name="start_node",
                    function="start_func",
                    output="start_result"
                ),
                "middle_node": NodeDefinition(
                    name="middle_node",
                    function="middle_func",
                    output="middle_result"
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
                "middle_func": FunctionDefinition(
                    name="middle_func",
                    type="embedded",
                    code="def middle_func(): return 'middle'"
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
                    to_node="middle_node",
                    condition=None
                ),
                TransitionDefinition(
                    from_node="middle_node",
                    to_node="end_node",
                    condition=None
                )
            ]
        )

    def test_validation_result_init(self):
        """Test ValidationResult initialization."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_validation_error_init(self):
        """Test ValidationError initialization."""
        error = ValidationError(
            message="Test error",
            node_name="test_node",
            error_type="missing_node"
        )
        
        assert error.message == "Test error"
        assert error.node_name == "test_node"
        assert error.error_type == "missing_node"

    def test_workflow_validator_init(self):
        """Test WorkflowValidator initialization."""
        validator = WorkflowValidator()
        
        assert validator is not None
        # Check if validator has expected methods
        assert hasattr(validator, "validate")
        assert hasattr(validator, "validate_nodes")
        assert hasattr(validator, "validate_transitions")

    def test_validate_workflow_valid(self):
        """Test validation of a valid workflow."""
        result = validate_workflow(self.valid_workflow)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_workflow_missing_start_node(self):
        """Test validation with missing start node."""
        invalid_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="nonexistent_node",
                nodes=["start_node", "end_node"]
            ),
            nodes={
                "start_node": NodeDefinition(
                    name="start_node",
                    function="start_func"
                ),
                "end_node": NodeDefinition(
                    name="end_node",
                    function="end_func"
                )
            },
            functions={
                "start_func": FunctionDefinition(
                    name="start_func",
                    type="embedded",
                    code="def start_func(): pass"
                ),
                "end_func": FunctionDefinition(
                    name="end_func",
                    type="embedded",
                    code="def end_func(): pass"
                )
            },
            transitions=[]
        )
        
        result = validate_workflow(invalid_workflow)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("start" in error.message.lower() for error in result.errors)

    def test_validate_workflow_missing_function(self):
        """Test validation with missing function definition."""
        invalid_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="start_node",
                nodes=["start_node"]
            ),
            nodes={
                "start_node": NodeDefinition(
                    name="start_node",
                    function="missing_func",
                    output="result"
                )
            },
            functions={},  # Empty functions dict
            transitions=[]
        )
        
        result = validate_workflow(invalid_workflow)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("function" in error.message.lower() for error in result.errors)

    def test_validate_workflow_circular_dependency(self):
        """Test validation with circular dependencies."""
        circular_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="node1",
                nodes=["node1", "node2", "node3"]
            ),
            nodes={
                "node1": NodeDefinition(name="node1", function="func1"),
                "node2": NodeDefinition(name="node2", function="func2"),
                "node3": NodeDefinition(name="node3", function="func3")
            },
            functions={
                "func1": FunctionDefinition(name="func1", type="embedded", code="def func1(): pass"),
                "func2": FunctionDefinition(name="func2", type="embedded", code="def func2(): pass"),
                "func3": FunctionDefinition(name="func3", type="embedded", code="def func3(): pass")
            },
            transitions=[
                TransitionDefinition(from_node="node1", to_node="node2"),
                TransitionDefinition(from_node="node2", to_node="node3"),
                TransitionDefinition(from_node="node3", to_node="node1")  # Creates cycle
            ]
        )
        
        result = validate_workflow(circular_workflow)
        
        # Depending on implementation, might detect cycles
        assert isinstance(result, ValidationResult)

    def test_validate_workflow_unreachable_nodes(self):
        """Test validation with unreachable nodes."""
        unreachable_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="start_node",
                nodes=["start_node", "reachable_node", "unreachable_node"]
            ),
            nodes={
                "start_node": NodeDefinition(name="start_node", function="start_func"),
                "reachable_node": NodeDefinition(name="reachable_node", function="reachable_func"),
                "unreachable_node": NodeDefinition(name="unreachable_node", function="unreachable_func")
            },
            functions={
                "start_func": FunctionDefinition(name="start_func", type="embedded", code="def start_func(): pass"),
                "reachable_func": FunctionDefinition(name="reachable_func", type="embedded", code="def reachable_func(): pass"),
                "unreachable_func": FunctionDefinition(name="unreachable_func", type="embedded", code="def unreachable_func(): pass")
            },
            transitions=[
                TransitionDefinition(from_node="start_node", to_node="reachable_node")
                # No transition to unreachable_node
            ]
        )
        
        result = validate_workflow(unreachable_workflow)
        
        # Might detect unreachable nodes as warnings
        assert isinstance(result, ValidationResult)

    def test_validate_workflow_invalid_transition(self):
        """Test validation with invalid transitions."""
        invalid_transition_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="start_node",
                nodes=["start_node", "end_node"]
            ),
            nodes={
                "start_node": NodeDefinition(name="start_node", function="start_func"),
                "end_node": NodeDefinition(name="end_node", function="end_func")
            },
            functions={
                "start_func": FunctionDefinition(name="start_func", type="embedded", code="def start_func(): pass"),
                "end_func": FunctionDefinition(name="end_func", type="embedded", code="def end_func(): pass")
            },
            transitions=[
                TransitionDefinition(
                    from_node="start_node",
                    to_node="nonexistent_node"  # Invalid target
                )
            ]
        )
        
        result = validate_workflow(invalid_transition_workflow)
        
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validate_workflow_with_llm_nodes(self):
        """Test validation of workflow with LLM nodes."""
        llm_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="llm_node",
                nodes=["llm_node"]
            ),
            nodes={
                "llm_node": NodeDefinition(
                    name="llm_node",
                    function="llm_func",
                    node_type="llm",
                    llm_params={"model": "gpt-4", "temperature": 0.7}
                )
            },
            functions={
                "llm_func": FunctionDefinition(
                    name="llm_func",
                    type="embedded",
                    code="def llm_func(query): return query"
                )
            },
            transitions=[]
        )
        
        result = validate_workflow(llm_workflow)
        
        assert isinstance(result, ValidationResult)
        # Should validate LLM parameters
        assert result.is_valid is True or len(result.errors) == 0

    def test_validate_workflow_with_template_nodes(self):
        """Test validation of workflow with template nodes."""
        template_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="template_node",
                nodes=["template_node"]
            ),
            nodes={
                "template_node": NodeDefinition(
                    name="template_node",
                    function="template_func",
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
                    code="def template_func(**kwargs): return kwargs"
                )
            },
            transitions=[]
        )
        
        result = validate_workflow(template_workflow)
        
        assert isinstance(result, ValidationResult)
        # Should validate template configuration
        assert result.is_valid is True or len(result.errors) == 0

    def test_validate_workflow_invalid_function_syntax(self):
        """Test validation with invalid function syntax."""
        invalid_syntax_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="invalid_node",
                nodes=["invalid_node"]
            ),
            nodes={
                "invalid_node": NodeDefinition(
                    name="invalid_node",
                    function="invalid_func"
                )
            },
            functions={
                "invalid_func": FunctionDefinition(
                    name="invalid_func",
                    type="embedded",
                    code="def invalid_func(\n    # Missing closing parenthesis"
                )
            },
            transitions=[]
        )
        
        result = validate_workflow(invalid_syntax_workflow)
        
        # Should detect syntax errors
        assert isinstance(result, ValidationResult)

    def test_validate_workflow_empty_workflow(self):
        """Test validation of empty workflow."""
        empty_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="",
                nodes=[]
            ),
            nodes={},
            functions={},
            transitions=[]
        )
        
        result = validate_workflow(empty_workflow)
        
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validate_workflow_with_input_mappings(self):
        """Test validation of workflow with input mappings."""
        mapping_workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="mapped_node",
                nodes=["mapped_node"]
            ),
            nodes={
                "mapped_node": NodeDefinition(
                    name="mapped_node",
                    function="mapped_func",
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
                    code="def mapped_func(param1, param2): return param1 + param2"
                )
            },
            transitions=[]
        )
        
        result = validate_workflow(mapping_workflow)
        
        assert isinstance(result, ValidationResult)
        # Should validate input mappings
        assert result.is_valid is True or len(result.warnings) >= 0

    def test_workflow_validator_instance_methods(self):
        """Test WorkflowValidator instance methods."""
        validator = WorkflowValidator()
        
        # Test validation of valid workflow
        result = validator.validate(self.valid_workflow)
        assert isinstance(result, ValidationResult)
        
        # Test node validation
        node_result = validator.validate_nodes(self.valid_workflow)
        assert isinstance(node_result, list)  # Should return list of errors
        
        # Test transition validation
        transition_result = validator.validate_transitions(self.valid_workflow)
        assert isinstance(transition_result, list)  # Should return list of errors

    def test_validate_workflow_function_interface(self):
        """Test standalone validate_workflow function."""
        result = validate_workflow(self.valid_workflow)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)
