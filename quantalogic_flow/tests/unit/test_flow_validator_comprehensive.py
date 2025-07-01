"""Comprehensive tests for flow validation edge cases and error handling."""

import pytest

from quantalogic_flow.flow.flow_manager_schema import (
    BranchCondition,
    FunctionDefinition,
    LoopDefinition,
    NodeDefinition,
    TransitionDefinition,
    WorkflowDefinition,
    WorkflowStructure,
)
from quantalogic_flow.flow.flow_validator import validate_workflow


class TestFlowValidatorEdgeCases:
    """Test flow validator with comprehensive edge cases."""

    def test_validate_empty_workflow(self):
        """Test validation of completely empty workflow."""
        workflow = WorkflowDefinition()
        result = validate_workflow(workflow)
        
        assert not result.is_valid
        assert any("start node" in error.message.lower() for error in result.errors)

    def test_validate_workflow_with_no_nodes(self):
        """Test validation of workflow with start but no nodes."""
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(start="nonexistent")
        )
        result = validate_workflow(workflow)
        
        assert not result.is_valid
        assert any("start node" in error.message.lower() for error in result.errors)

    def test_validate_workflow_with_unreachable_nodes(self):
        """Test validation of workflow with unreachable nodes."""
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="node1",
                transitions=[
                    TransitionDefinition(from_node="node1", to_node="node2")
                ]
            ),
            nodes={
                "node1": NodeDefinition(function="func1"),
                "node2": NodeDefinition(function="func2"),
                "node3": NodeDefinition(function="func3")  # Unreachable
            },
            functions={
                "func1": FunctionDefinition(type="embedded", code="def func1(): pass"),
                "func2": FunctionDefinition(type="embedded", code="def func2(): pass"),
                "func3": FunctionDefinition(type="embedded", code="def func3(): pass"),
            }
        )
        result = validate_workflow(workflow)
        
        # Current validator doesn't detect unreachable nodes
        # This is valid workflow structure, so it should pass
        assert result.is_valid

    def test_validate_workflow_with_circular_dependency(self):
        """Test validation of workflow with circular dependencies."""
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="node1",
                transitions=[
                    TransitionDefinition(from_node="node1", to_node="node2"),
                    TransitionDefinition(from_node="node2", to_node="node3"),
                    TransitionDefinition(from_node="node3", to_node="node1")  # Circular
                ]
            ),
            nodes={
                "node1": NodeDefinition(function="func1"),
                "node2": NodeDefinition(function="func2"),
                "node3": NodeDefinition(function="func3")
            },
            functions={
                "func1": FunctionDefinition(type="embedded", code="def func1(): pass"),
                "func2": FunctionDefinition(type="embedded", code="def func2(): pass"),
                "func3": FunctionDefinition(type="embedded", code="def func3(): pass"),
            }
        )
        result = validate_workflow(workflow)
        
        # Should detect circular dependency as error for unconditional cycles
        assert not result.is_valid and any("circular" in error.message.lower() for error in result.errors)

    def test_validate_workflow_with_missing_function_references(self):
        """Test validation of workflow with nodes referencing missing functions."""
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="node1",
                transitions=[
                    TransitionDefinition(from_node="node1", to_node="node2")
                ]
            ),
            nodes={
                "node1": NodeDefinition(function="func1"),
                "node2": NodeDefinition(function="missing_func")  # Missing function
            },
            functions={
                "func1": FunctionDefinition(type="embedded", code="def func1(): pass")
                # missing_func not defined
            }
        )
        result = validate_workflow(workflow)
        
        assert not result.is_valid
        assert any("missing_func" in error.message for error in result.errors)

    def test_validate_workflow_with_invalid_transitions(self):
        """Test validation of workflow with invalid transition references."""
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="node1",
                transitions=[
                    TransitionDefinition(from_node="nonexistent_from", to_node="node1"),
                    TransitionDefinition(from_node="node1", to_node="nonexistent_to")
                ]
            ),
            nodes={
                "node1": NodeDefinition(function="func1")
            },
            functions={
                "func1": FunctionDefinition(type="embedded", code="def func1(): pass")
            }
        )
        result = validate_workflow(workflow)
        
        assert not result.is_valid
        assert any("nonexistent" in error.message for error in result.errors)

    def test_validate_workflow_with_branch_conditions(self):
        """Test validation of workflow with branch conditions."""
        branch_condition = BranchCondition(to_node="node2", condition="ctx.value > 10")
        
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="node1",
                transitions=[
                    TransitionDefinition(from_node="node1", to_node=[branch_condition, "node3"])
                ]
            ),
            nodes={
                "node1": NodeDefinition(function="func1"),
                "node2": NodeDefinition(function="func2"),
                "node3": NodeDefinition(function="func3")
            },
            functions={
                "func1": FunctionDefinition(type="embedded", code="def func1(): pass"),
                "func2": FunctionDefinition(type="embedded", code="def func2(): pass"),
                "func3": FunctionDefinition(type="embedded", code="def func3(): pass"),
            }
        )
        result = validate_workflow(workflow)
        
        assert result.is_valid

    def test_validate_workflow_with_invalid_branch_conditions(self):
        """Test validation with branch conditions referencing non-existent nodes."""
        branch_condition = BranchCondition(to_node="nonexistent_node", condition="ctx.value > 10")
        
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="node1",
                transitions=[
                    TransitionDefinition(from_node="node1", to_node=[branch_condition])
                ]
            ),
            nodes={
                "node1": NodeDefinition(function="func1")
            },
            functions={
                "func1": FunctionDefinition(type="embedded", code="def func1(): pass")
            }
        )
        result = validate_workflow(workflow)
        
        assert not result.is_valid
        assert any("nonexistent_node" in error.message for error in result.errors)

    def test_validate_workflow_with_loops(self):
        """Test validation of workflow with loop definitions."""
        inner_loop = LoopDefinition(
            nodes=["inner_node"],
            condition="ctx.inner_counter < 5",
            exit_node="node2"
        )
        
        outer_loop = LoopDefinition(
            nodes=["node1"],
            condition="ctx.outer_counter < 3",
            exit_node="end_node",
            nested_loops=[inner_loop]
        )
        
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="node1",
                transitions=[
                    TransitionDefinition(from_node="node1", to_node="inner_node"),
                    TransitionDefinition(from_node="inner_node", to_node="node2"),
                    TransitionDefinition(from_node="node2", to_node="end_node")
                ],
                loops=[outer_loop]
            ),
            nodes={
                "node1": NodeDefinition(function="func1"),
                "inner_node": NodeDefinition(function="func2"),
                "node2": NodeDefinition(function="func3"),
                "end_node": NodeDefinition(function="func4")
            },
            functions={
                "func1": FunctionDefinition(type="embedded", code="def func1(): pass"),
                "func2": FunctionDefinition(type="embedded", code="def func2(): pass"),
                "func3": FunctionDefinition(type="embedded", code="def func3(): pass"),
                "func4": FunctionDefinition(type="embedded", code="def func4(): pass"),
            }
        )
        result = validate_workflow(workflow)
        
        assert result.is_valid

    def test_validate_workflow_with_invalid_loop_nodes(self):
        """Test validation with loops referencing non-existent nodes."""
        loop_def = LoopDefinition(
            nodes=["nonexistent_node"],
            condition="ctx.counter < 10",
            exit_node="also_nonexistent"
        )
        
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="node1",
                loops=[loop_def]
            ),
            nodes={
                "node1": NodeDefinition(function="func1")
            },
            functions={
                "func1": FunctionDefinition(type="embedded", code="def func1(): pass")
            }
        )
        result = validate_workflow(workflow)
        
        assert not result.is_valid
        assert any("nonexistent" in error.message for error in result.errors)

    def test_validate_workflow_with_convergence_nodes(self):
        """Test validation of workflow with convergence nodes."""
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="node1",
                transitions=[
                    TransitionDefinition(from_node="node1", to_node=["node2", "node3"]),
                    TransitionDefinition(from_node="node2", to_node="convergence"),
                    TransitionDefinition(from_node="node3", to_node="convergence")
                ],
                convergence_nodes=["convergence"]
            ),
            nodes={
                "node1": NodeDefinition(function="func1"),
                "node2": NodeDefinition(function="func2"),
                "node3": NodeDefinition(function="func3"),
                "convergence": NodeDefinition(function="func4")
            },
            functions={
                "func1": FunctionDefinition(type="embedded", code="def func1(): pass"),
                "func2": FunctionDefinition(type="embedded", code="def func2(): pass"),
                "func3": FunctionDefinition(type="embedded", code="def func3(): pass"),
                "func4": FunctionDefinition(type="embedded", code="def func4(): pass"),
            }
        )
        result = validate_workflow(workflow)
        
        assert result.is_valid

    def test_validate_workflow_with_invalid_convergence_nodes(self):
        """Test validation with convergence nodes that don't exist."""
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="node1",
                convergence_nodes=["nonexistent_convergence"]
            ),
            nodes={
                "node1": NodeDefinition(function="func1")
            },
            functions={
                "func1": FunctionDefinition(type="embedded", code="def func1(): pass")
            }
        )
        result = validate_workflow(workflow)
        
        assert not result.is_valid
        assert any("nonexistent_convergence" in error.message for error in result.errors)

    def test_validate_workflow_with_complex_nested_structure(self):
        """Test validation of complex nested workflow structure."""
        # Create a complex nested structure with multiple loops and branches
        inner_loop1 = LoopDefinition(
            nodes=["inner1"],
            condition="ctx.inner1_counter < 3",
            exit_node="branch_point"
        )
        
        inner_loop2 = LoopDefinition(
            nodes=["inner2"],
            condition="ctx.inner2_counter < 2",
            exit_node="convergence"
        )
        
        outer_loop = LoopDefinition(
            nodes=["outer_start", "branch_point"],
            condition="ctx.outer_counter < 5",
            exit_node="final_node",
            nested_loops=[inner_loop1, inner_loop2]
        )
        
        branch_condition = BranchCondition(to_node="inner2", condition="ctx.branch_value == 'path2'")
        
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="outer_start",
                transitions=[
                    TransitionDefinition(from_node="outer_start", to_node="inner1"),
                    TransitionDefinition(from_node="inner1", to_node="branch_point"),
                    TransitionDefinition(from_node="branch_point", to_node=[branch_condition, "convergence"]),
                    TransitionDefinition(from_node="inner2", to_node="convergence"),
                    TransitionDefinition(from_node="convergence", to_node="final_node")
                ],
                convergence_nodes=["convergence"],
                loops=[outer_loop]
            ),
            nodes={
                "outer_start": NodeDefinition(function="func1"),
                "inner1": NodeDefinition(function="func2"),
                "branch_point": NodeDefinition(function="func3"),
                "inner2": NodeDefinition(function="func4"),
                "convergence": NodeDefinition(function="func5"),
                "final_node": NodeDefinition(function="func6")
            },
            functions={
                "func1": FunctionDefinition(type="embedded", code="def func1(): pass"),
                "func2": FunctionDefinition(type="embedded", code="def func2(): pass"),
                "func3": FunctionDefinition(type="embedded", code="def func3(): pass"),
                "func4": FunctionDefinition(type="embedded", code="def func4(): pass"),
                "func5": FunctionDefinition(type="embedded", code="def func5(): pass"),
                "func6": FunctionDefinition(type="embedded", code="def func6(): pass"),
            }
        )
        result = validate_workflow(workflow)
        
        assert result.is_valid

    def test_validate_workflow_with_malformed_conditions(self):
        """Test validation with syntactically invalid conditions."""
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="node1",
                transitions=[
                    TransitionDefinition(
                        from_node="node1", 
                        to_node="node2", 
                        condition="ctx.value ) ( invalid"  # Invalid syntax
                    )
                ]
            ),
            nodes={
                "node1": NodeDefinition(function="func1"),
                "node2": NodeDefinition(function="func2")
            },
            functions={
                "func1": FunctionDefinition(type="embedded", code="def func1(): pass"),
                "func2": FunctionDefinition(type="embedded", code="def func2(): pass"),
            }
        )
        result = validate_workflow(workflow)
        
        # Should warn about invalid condition syntax
        assert result.warnings or not result.is_valid

    def test_validate_workflow_with_empty_function_code(self):
        """Test validation with functions that have empty or invalid code."""
        # These should fail at schema validation level
        with pytest.raises(Exception):  # ValidationError from Pydantic
            WorkflowDefinition(
                workflow=WorkflowStructure(start="node1"),
                nodes={
                    "node1": NodeDefinition(function="empty_func"),
                },
                functions={
                    "empty_func": FunctionDefinition(type="embedded", code=""),  # Empty code - should fail validation
                }
            )

    def test_validate_workflow_performance_with_large_structure(self):
        """Test validation performance with a large workflow structure."""
        # Create a large workflow to test performance
        nodes = {}
        functions = {}
        transitions = []
        
        # Create 100 nodes
        for i in range(100):
            node_name = f"node_{i}"
            func_name = f"func_{i}"
            
            nodes[node_name] = NodeDefinition(function=func_name)
            functions[func_name] = FunctionDefinition(
                type="embedded", 
                code=f"def {func_name}(): return {i}"
            )
            
            if i > 0:
                transitions.append(TransitionDefinition(
                    from_node=f"node_{i-1}", 
                    to_node=node_name
                ))
        
        workflow = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="node_0",
                transitions=transitions
            ),
            nodes=nodes,
            functions=functions
        )
        
        # Validation should complete in reasonable time
        import time
        start_time = time.time()
        result = validate_workflow(workflow)
        end_time = time.time()
        
        assert result.is_valid
        assert (end_time - start_time) < 5.0  # Should complete within 5 seconds
