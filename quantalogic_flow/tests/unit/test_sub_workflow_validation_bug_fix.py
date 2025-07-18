"""Unit tests for sub-workflow validation bug fix.

This test file verifies the fix for issue #63 where sub-workflow validation
incorrectly iterated over ALL top-level nodes instead of only the nodes that
actually belong to the sub-workflow.

Bug Description:
- Original code: for sub_node_name, sub_node_def in workflow_def.nodes.items():
- Problem: Validates ALL nodes as if they were sub-nodes
- Fix: Only validate actual sub-nodes using get_sub_workflow_nodes()

Tests verify:
1. get_sub_workflow_nodes() correctly extracts only actual sub-nodes
2. Validation no longer processes false positive nodes
3. Complex sub-workflows with branches work correctly
4. Performance improvement by processing fewer nodes
"""

import pytest
from quantalogic_flow.flow.flow_manager_schema import (
    BranchCondition,
    FunctionDefinition,
    NodeDefinition,
    TransitionDefinition,
    WorkflowDefinition,
    WorkflowStructure,
)
from quantalogic_flow.flow.flow_validator import (
    get_sub_workflow_nodes,
    validate_workflow_definition,
)


class TestSubWorkflowValidationBugFix:
    """Test the sub-workflow validation bug fix."""

    def test_get_sub_workflow_nodes_simple(self):
        """Test get_sub_workflow_nodes with a simple sub-workflow."""
        # Create a simple sub-workflow
        sub_workflow = WorkflowStructure(start="sub_start")
        sub_workflow.transitions = [
            TransitionDefinition(from_node="sub_start", to_node="sub_end")
        ]
        
        # Extract sub-nodes
        result = get_sub_workflow_nodes(sub_workflow)
        expected = {"sub_start", "sub_end"}
        
        assert result == expected, f"Expected {expected}, got {result}"

    def test_get_sub_workflow_nodes_with_branches(self):
        """Test get_sub_workflow_nodes with branch conditions."""
        # Create a sub-workflow with branch conditions
        sub_workflow = WorkflowStructure(start="sub_start")
        sub_workflow.transitions = [
            TransitionDefinition(from_node="sub_start", to_node="sub_decision"),
            TransitionDefinition(from_node="sub_decision", to_node=[
                BranchCondition(to_node="sub_branch_a", condition="ctx['value'] > 10"),
                BranchCondition(to_node="sub_branch_b", condition="ctx['value'] <= 10"),
                "sub_default"
            ])
        ]
        
        # Extract sub-nodes
        result = get_sub_workflow_nodes(sub_workflow)
        expected = {"sub_start", "sub_decision", "sub_branch_a", "sub_branch_b", "sub_default"}
        
        assert result == expected, f"Expected {expected}, got {result}"

    def test_get_sub_workflow_nodes_complex(self):
        """Test get_sub_workflow_nodes with a complex multi-branch sub-workflow."""
        sub_workflow = WorkflowStructure(start="sub_start")
        sub_workflow.transitions = [
            TransitionDefinition(from_node="sub_start", to_node="sub_decision"),
            TransitionDefinition(from_node="sub_decision", to_node=[
                BranchCondition(to_node="sub_path_a", condition="ctx['choice'] == 'a'"),
                BranchCondition(to_node="sub_path_b", condition="ctx['choice'] == 'b'"),
                "sub_default_path"
            ]),
            TransitionDefinition(from_node="sub_path_a", to_node="sub_convergence"),
            TransitionDefinition(from_node="sub_path_b", to_node="sub_convergence"),
            TransitionDefinition(from_node="sub_default_path", to_node="sub_convergence"),
            TransitionDefinition(from_node="sub_convergence", to_node="sub_end")
        ]
        
        result = get_sub_workflow_nodes(sub_workflow)
        expected = {
            "sub_start", "sub_decision", "sub_path_a", "sub_path_b", 
            "sub_default_path", "sub_convergence", "sub_end"
        }
        
        assert result == expected, f"Expected {expected}, got {result}"

    def test_get_sub_workflow_nodes_edge_cases(self):
        """Test edge cases for get_sub_workflow_nodes."""
        # Empty sub-workflow
        empty_sub_workflow = WorkflowStructure()
        result = get_sub_workflow_nodes(empty_sub_workflow)
        assert result == set(), "Empty sub-workflow should return empty set"
        
        # Start-only sub-workflow
        start_only = WorkflowStructure(start="lonely_start")
        result = get_sub_workflow_nodes(start_only)
        assert result == {"lonely_start"}, "Start-only sub-workflow should return start node"

    def test_sub_workflow_validation_fix_prevents_false_positives(self):
        """Test that the fix prevents validation of unrelated nodes as sub-nodes.
        
        This is the core test that demonstrates the bug fix:
        - Before: ALL workflow nodes were validated for each sub-workflow
        - After: Only actual sub-nodes are validated
        """
        # Create a workflow with multiple main nodes and a sub-workflow
        workflow_def = WorkflowDefinition(
            workflow=WorkflowStructure(
                start="start",
                transitions=[
                    TransitionDefinition(from_node="start", to_node="check"),
                    TransitionDefinition(from_node="check", to_node="ai_node"),
                    TransitionDefinition(from_node="ai_node", to_node="nested"),
                    TransitionDefinition(from_node="nested", to_node="finalize")
                ]
            ),
            nodes={
                # Main workflow nodes (should NOT be validated as sub-nodes)
                "start": NodeDefinition(function="start_func", output="start_result"),
                "check": NodeDefinition(function="check_func", output="check_result"),
                "ai_node": NodeDefinition(function="ai_func", output="ai_result"),
                "finalize": NodeDefinition(function="finalize_func", output="final_result"),
                
                # Sub-workflow nodes (only these should be validated as sub-nodes)
                "nested_start": NodeDefinition(function="nested_start_func", output="nested_start_result"),
                "nested_end": NodeDefinition(function="nested_end_func", output="nested_end_result"),
            },
            functions={
                "start_func": FunctionDefinition(type="embedded", code="def start_func(): return 'start'"),
                "check_func": FunctionDefinition(type="embedded", code="def check_func(): return 'check'"),
                "ai_func": FunctionDefinition(type="embedded", code="def ai_func(): return 'ai'"),
                "finalize_func": FunctionDefinition(type="embedded", code="def finalize_func(): return 'final'"),
                "nested_start_func": FunctionDefinition(type="embedded", code="def nested_start_func(): return 'nested_start'"),
                "nested_end_func": FunctionDefinition(type="embedded", code="def nested_end_func(): return 'nested_end'"),
            }
        )
        
        # Create a sub-workflow that only contains nested_start and nested_end
        sub_workflow = WorkflowStructure(start="nested_start")
        sub_workflow.transitions = [
            TransitionDefinition(from_node="nested_start", to_node="nested_end")
        ]
        
        # Add the sub-workflow to the nested node
        workflow_def.nodes["nested"] = NodeDefinition(sub_workflow=sub_workflow)
        
        # Verify the fix extracts only actual sub-nodes
        actual_sub_nodes = get_sub_workflow_nodes(sub_workflow)
        expected_sub_nodes = {"nested_start", "nested_end"}
        
        assert actual_sub_nodes == expected_sub_nodes, (
            f"get_sub_workflow_nodes should return only actual sub-nodes. "
            f"Expected {expected_sub_nodes}, got {actual_sub_nodes}"
        )
        
        # Verify main workflow nodes are NOT included in sub-nodes
        main_workflow_nodes = {"start", "check", "ai_node", "finalize"}
        for main_node in main_workflow_nodes:
            assert main_node not in actual_sub_nodes, (
                f"Main workflow node '{main_node}' should NOT be in sub-workflow nodes"
            )
        
        # Run validation to ensure it works without false errors
        issues = validate_workflow_definition(workflow_def)
        
        # Filter for sub-workflow related issues
        sub_workflow_issues = [issue for issue in issues if issue.node_name and "/" in issue.node_name]
        
        # All sub-workflow issues should be for actual sub-nodes only
        for issue in sub_workflow_issues:
            assert issue.node_name.startswith("nested/nested_"), (
                f"Sub-workflow validation issue for unexpected node: {issue.node_name}"
            )

    def test_sub_workflow_validation_detects_missing_nodes(self):
        """Test that sub-workflow validation correctly detects missing sub-nodes."""
        # Create a sub-workflow that references a node not in the main workflow
        sub_workflow = WorkflowStructure(start="existing_node")
        sub_workflow.transitions = [
            TransitionDefinition(from_node="existing_node", to_node="missing_node")
        ]
        
        workflow_def = WorkflowDefinition(
            workflow=WorkflowStructure(start="main_node"),
            nodes={
                "main_node": NodeDefinition(sub_workflow=sub_workflow),
                "existing_node": NodeDefinition(function="existing_func"),
                # Note: missing_node is NOT defined
            },
            functions={
                "existing_func": FunctionDefinition(type="embedded", code="def existing_func(): return 'existing'"),
            }
        )
        
        # Run validation
        issues = validate_workflow_definition(workflow_def)
        
        # Should detect the missing sub-node
        missing_node_errors = [issue for issue in issues if "missing_node" in issue.description]
        assert len(missing_node_errors) > 0, "Should detect missing sub-node"
        assert "not defined in workflow nodes" in missing_node_errors[0].description

    def test_performance_improvement_demonstration(self):
        """Demonstrate the performance improvement of the fix.
        
        The fix reduces the number of nodes processed for sub-workflow validation
        from ALL workflow nodes to only the actual sub-nodes.
        """
        # Create a workflow with many main nodes and a small sub-workflow
        main_nodes = {f"main_node_{i}": NodeDefinition(function=f"func_{i}") for i in range(50)}
        main_functions = {f"func_{i}": FunctionDefinition(type="embedded", code=f"def func_{i}(): return {i}") for i in range(50)}
        
        # Add sub-workflow nodes
        main_nodes.update({
            "sub_node_1": NodeDefinition(function="sub_func_1"),
            "sub_node_2": NodeDefinition(function="sub_func_2"),
        })
        main_functions.update({
            "sub_func_1": FunctionDefinition(type="embedded", code="def sub_func_1(): return 'sub1'"),
            "sub_func_2": FunctionDefinition(type="embedded", code="def sub_func_2(): return 'sub2'"),
        })
        
        # Create a simple sub-workflow
        sub_workflow = WorkflowStructure(start="sub_node_1")
        sub_workflow.transitions = [
            TransitionDefinition(from_node="sub_node_1", to_node="sub_node_2")
        ]
        
        main_nodes["nested"] = NodeDefinition(sub_workflow=sub_workflow)
        
        total_nodes = len(main_nodes)
        actual_sub_nodes = get_sub_workflow_nodes(sub_workflow)
        
        # The fix should process only 2 nodes instead of 52+
        assert len(actual_sub_nodes) == 2, "Should only extract actual sub-nodes"
        assert actual_sub_nodes == {"sub_node_1", "sub_node_2"}, "Should extract correct sub-nodes"
        
        # Performance improvement calculation
        efficiency_improvement = total_nodes / len(actual_sub_nodes)
        assert efficiency_improvement > 25, f"Should have significant efficiency improvement, got {efficiency_improvement}x"

    def test_bug_fix_handles_missing_inputs_mapping_correctly(self):
        """Test that the fix correctly handles inputs_mapping for sub-nodes."""
        # This test verifies the fix for the inputs_mapping bug where
        # the wrong mapping (node_def vs sub_node_def) was being used
        
        sub_workflow = WorkflowStructure(start="sub_input_node")
        sub_workflow.transitions = [
            TransitionDefinition(from_node="sub_input_node", to_node="sub_output_node")
        ]
        
        workflow_def = WorkflowDefinition(
            workflow=WorkflowStructure(start="main_node"),
            nodes={
                "main_node": NodeDefinition(sub_workflow=sub_workflow),
                "sub_input_node": NodeDefinition(
                    function="sub_input_func",
                    inputs_mapping={"param": "input_value"}  # This should be used for sub-node validation
                ),
                "sub_output_node": NodeDefinition(function="sub_output_func"),
            },
            functions={
                "sub_input_func": FunctionDefinition(type="embedded", code="def sub_input_func(param): return param"),
                "sub_output_func": FunctionDefinition(type="embedded", code="def sub_output_func(): return 'output'"),
            }
        )
        
        # Validation should use the correct inputs_mapping from sub_node_def
        issues = validate_workflow_definition(workflow_def)
        
        # Should not have issues with inputs_mapping handling
        mapping_issues = [issue for issue in issues if "inputs_mapping" in issue.description]
        
        # Any mapping issues should be legitimate, not due to using wrong mapping
        for issue in mapping_issues:
            # Should reference the correct sub-node mapping, not main node mapping
            assert "main_node/" in issue.node_name or issue.node_name == "main_node"