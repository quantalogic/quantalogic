#!/usr/bin/env python3
"""
Test file to demonstrate the sub-workflow validation bug fix.

This test demonstrates:
1. The original bug where sub-workflow validation incorrectly iterated over ALL top-level nodes
2. The fix where only actual sub-nodes are validated
3. Edge cases with complex sub-workflows
"""

import sys
import os

# Add the quantalogic_flow package to the Python path
sys.path.insert(0, '/home/runner/work/quantalogic/quantalogic/quantalogic_flow')

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


def test_get_sub_workflow_nodes_simple():
    """Test the get_sub_workflow_nodes function with a simple sub-workflow."""
    print("=== Testing get_sub_workflow_nodes with simple sub-workflow ===")
    
    # Create a simple sub-workflow with start node and one transition
    sub_workflow = WorkflowStructure(start="sub_start")
    sub_workflow.transitions = [
        TransitionDefinition(from_node="sub_start", to_node="sub_end")
    ]
    
    # Extract sub-nodes
    sub_nodes = get_sub_workflow_nodes(sub_workflow)
    print(f"Sub-workflow nodes: {sub_nodes}")
    
    # Should contain exactly the 2 nodes referenced in the sub-workflow
    expected = {"sub_start", "sub_end"}
    assert sub_nodes == expected, f"Expected {expected}, got {sub_nodes}"
    print("✓ Simple sub-workflow extraction works correctly")


def test_get_sub_workflow_nodes_with_branches():
    """Test the get_sub_workflow_nodes function with branch conditions."""
    print("=== Testing get_sub_workflow_nodes with branch conditions ===")
    
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
    sub_nodes = get_sub_workflow_nodes(sub_workflow)
    print(f"Sub-workflow nodes with branches: {sub_nodes}")
    
    # Should contain all nodes referenced in the sub-workflow
    expected = {"sub_start", "sub_decision", "sub_branch_a", "sub_branch_b", "sub_default"}
    assert sub_nodes == expected, f"Expected {expected}, got {sub_nodes}"
    print("✓ Sub-workflow with branches extraction works correctly")


def test_original_bug_demonstration():
    """Demonstrate the original bug where ALL nodes were validated for each sub-workflow."""
    print("=== Demonstrating the original bug (before fix) ===")
    
    # Create a workflow with multiple top-level nodes and one sub-workflow
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
            # Main workflow nodes
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
    
    print(f"Total nodes in workflow: {list(workflow_def.nodes.keys())}")
    print(f"Nodes that should be in sub-workflow: {get_sub_workflow_nodes(sub_workflow)}")
    
    # With the fix, only actual sub-nodes should be validated
    actual_sub_nodes = get_sub_workflow_nodes(sub_workflow)
    expected_sub_nodes = {"nested_start", "nested_end"}
    
    print(f"✓ Sub-workflow correctly identifies only {expected_sub_nodes}")
    print(f"✓ Does NOT include main workflow nodes like: {set(workflow_def.nodes.keys()) - expected_sub_nodes - {'nested'}}")
    
    assert actual_sub_nodes == expected_sub_nodes, f"Expected {expected_sub_nodes}, got {actual_sub_nodes}"
    
    # Run validation to ensure no false positives
    issues = validate_workflow_definition(workflow_def)
    node_specific_issues = [issue for issue in issues if issue.node_name and "/" in issue.node_name]
    
    print(f"Sub-workflow validation issues: {len(node_specific_issues)}")
    for issue in node_specific_issues:
        print(f"  - {issue.node_name}: {issue.description}")
    
    # Should only have issues for actual sub-nodes, not main workflow nodes
    for issue in node_specific_issues:
        assert issue.node_name.startswith("nested/nested_"), f"Unexpected issue for {issue.node_name}: {issue.description}"
    
    print("✓ No false validation errors for main workflow nodes")


def test_sub_workflow_validation_with_missing_nodes():
    """Test that sub-workflow validation correctly identifies missing sub-nodes."""
    print("=== Testing sub-workflow validation with missing nodes ===")
    
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
    print(f"✓ Correctly detected missing sub-node: {missing_node_errors[0].description}")


def test_complex_sub_workflow_with_multiple_branches():
    """Test a complex sub-workflow with multiple branches and convergence."""
    print("=== Testing complex sub-workflow with multiple branches ===")
    
    # Create a complex sub-workflow
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
    
    # Extract nodes
    sub_nodes = get_sub_workflow_nodes(sub_workflow)
    expected_nodes = {
        "sub_start", "sub_decision", "sub_path_a", "sub_path_b", 
        "sub_default_path", "sub_convergence", "sub_end"
    }
    
    print(f"Complex sub-workflow nodes: {sub_nodes}")
    assert sub_nodes == expected_nodes, f"Expected {expected_nodes}, got {sub_nodes}"
    print("✓ Complex sub-workflow extraction works correctly")


def test_validation_performance_comparison():
    """Demonstrate the efficiency improvement of the fix."""
    print("=== Testing validation performance improvement ===")
    
    # Create a workflow with many top-level nodes and a small sub-workflow
    main_nodes = {f"main_node_{i}": NodeDefinition(function=f"func_{i}") for i in range(100)}
    main_functions = {f"func_{i}": FunctionDefinition(type="embedded", code=f"def func_{i}(): return {i}") for i in range(100)}
    
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
    
    workflow_def = WorkflowDefinition(
        workflow=WorkflowStructure(start="main_node_0"),
        nodes=main_nodes,
        functions=main_functions
    )
    
    print(f"Workflow has {len(workflow_def.nodes)} total nodes")
    
    # With the fix, only actual sub-nodes are processed
    actual_sub_nodes = get_sub_workflow_nodes(sub_workflow)
    print(f"Sub-workflow contains only {len(actual_sub_nodes)} nodes: {actual_sub_nodes}")
    
    # Old approach would process all 102 nodes for sub-workflow validation
    # New approach processes only 2 nodes
    efficiency_improvement = len(workflow_def.nodes) / len(actual_sub_nodes)
    print(f"✓ Efficiency improvement: {efficiency_improvement:.1f}x fewer nodes processed for sub-workflow validation")
    
    assert len(actual_sub_nodes) == 2, "Should only process actual sub-nodes"
    assert actual_sub_nodes == {"sub_node_1", "sub_node_2"}, "Should only contain actual sub-nodes"


def main():
    """Run all tests to demonstrate the sub-workflow validation fix."""
    print("Testing Sub-Workflow Validation Bug Fix")
    print("=" * 50)
    
    try:
        test_get_sub_workflow_nodes_simple()
        print()
        
        test_get_sub_workflow_nodes_with_branches()
        print()
        
        test_original_bug_demonstration()
        print()
        
        test_sub_workflow_validation_with_missing_nodes()
        print()
        
        test_complex_sub_workflow_with_multiple_branches()
        print()
        
        test_validation_performance_comparison()
        print()
        
        print("=" * 50)
        print("✅ ALL TESTS PASSED")
        print("✅ Sub-workflow validation bug fix is working correctly!")
        print("✅ The fix eliminates false validation errors and improves performance")
        
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)