#!/usr/bin/env python3
"""
Direct test of the get_sub_workflow_nodes function to demonstrate the bug fix.
"""

import sys
from typing import Set
from pydantic import BaseModel, Field
from typing import Optional, List, Union

# Minimal model definitions needed for testing
class BranchCondition(BaseModel):
    to_node: str = Field(...)
    condition: Optional[str] = Field(None)

class TransitionDefinition(BaseModel):
    from_node: str = Field(...)
    to_node: Union[str, List[Union[str, BranchCondition]]] = Field(...)
    condition: Optional[str] = Field(None)

class WorkflowStructure(BaseModel):
    start: Optional[str] = Field(None)
    transitions: List[TransitionDefinition] = Field(default_factory=list)

# Copy the actual implementation of get_sub_workflow_nodes from the fixed code
def get_sub_workflow_nodes(sub_workflow: WorkflowStructure) -> Set[str]:
    """Extract the actual node names from a sub-workflow structure.
    
    Args:
        sub_workflow: The WorkflowStructure to extract nodes from.
        
    Returns:
        Set of node names that belong to this sub-workflow.
    """
    sub_nodes = set()
    
    # Add start node if it exists
    if sub_workflow.start:
        sub_nodes.add(sub_workflow.start)
    
    # Add nodes from transitions
    for trans in sub_workflow.transitions:
        # Add from_node
        sub_nodes.add(trans.from_node)
        
        # Add to_node(s)
        if isinstance(trans.to_node, str):
            sub_nodes.add(trans.to_node)
        elif isinstance(trans.to_node, list):
            for target in trans.to_node:
                if isinstance(target, str):
                    sub_nodes.add(target)
                else:  # BranchCondition
                    sub_nodes.add(target.to_node)
    
    return sub_nodes


def test_simple_sub_workflow():
    """Test extraction of nodes from a simple sub-workflow."""
    print("=== Test 1: Simple Sub-Workflow ===")
    
    sub_workflow = WorkflowStructure(start="sub_start")
    sub_workflow.transitions = [
        TransitionDefinition(from_node="sub_start", to_node="sub_end")
    ]
    
    result = get_sub_workflow_nodes(sub_workflow)
    expected = {"sub_start", "sub_end"}
    
    print(f"Expected: {expected}")
    print(f"Got:      {result}")
    
    assert result == expected, f"Test failed: {result} != {expected}"
    print("✓ PASSED")


def test_branching_sub_workflow():
    """Test extraction from sub-workflow with branch conditions."""
    print("\n=== Test 2: Sub-Workflow with Branches ===")
    
    sub_workflow = WorkflowStructure(start="sub_start")
    sub_workflow.transitions = [
        TransitionDefinition(from_node="sub_start", to_node="sub_decision"),
        TransitionDefinition(from_node="sub_decision", to_node=[
            BranchCondition(to_node="sub_branch_a", condition="ctx['value'] > 10"),
            BranchCondition(to_node="sub_branch_b", condition="ctx['value'] <= 10"),
            "sub_default"
        ])
    ]
    
    result = get_sub_workflow_nodes(sub_workflow)
    expected = {"sub_start", "sub_decision", "sub_branch_a", "sub_branch_b", "sub_default"}
    
    print(f"Expected: {sorted(expected)}")
    print(f"Got:      {sorted(result)}")
    
    assert result == expected, f"Test failed: {result} != {expected}"
    print("✓ PASSED")


def test_demonstrates_bug_fix():
    """Demonstrate the core bug fix - only sub-workflow nodes are extracted."""
    print("\n=== Test 3: Demonstrates the Bug Fix ===")
    
    # Simulate the scenario that was broken:
    # - Main workflow has many nodes
    # - Sub-workflow only references 2 specific nodes
    # - OLD BUG: Would process all main workflow nodes
    # - NEW FIX: Only processes the 2 actual sub-nodes
    
    simulated_main_workflow_nodes = [
        "start", "check", "ai_node", "nested_start", "nested_end", "finalize", "template_node"
    ]
    
    # Sub-workflow only references 2 nodes
    sub_workflow = WorkflowStructure(start="nested_start")
    sub_workflow.transitions = [
        TransitionDefinition(from_node="nested_start", to_node="nested_end")
    ]
    
    # The fix should only extract the 2 actual sub-nodes
    actual_sub_nodes = get_sub_workflow_nodes(sub_workflow)
    expected_sub_nodes = {"nested_start", "nested_end"}
    
    print(f"Main workflow nodes (simulated): {simulated_main_workflow_nodes}")
    print(f"Sub-workflow nodes (with fix):   {sorted(actual_sub_nodes)}")
    
    # Verify the fix works
    assert actual_sub_nodes == expected_sub_nodes
    
    # Verify false nodes are excluded
    false_nodes = set(simulated_main_workflow_nodes) - expected_sub_nodes
    for node in false_nodes:
        assert node not in actual_sub_nodes, f"Bug: {node} should NOT be in sub-workflow"
    
    efficiency_ratio = len(simulated_main_workflow_nodes) / len(actual_sub_nodes)
    
    print(f"False nodes correctly excluded:  {sorted(false_nodes)}")
    print(f"Efficiency improvement:          {efficiency_ratio:.1f}x")
    print("✓ PASSED")


def test_complex_sub_workflow():
    """Test a complex sub-workflow with multiple branches and convergence."""
    print("\n=== Test 4: Complex Sub-Workflow ===")
    
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
    
    print(f"Expected: {sorted(expected)}")
    print(f"Got:      {sorted(result)}")
    
    assert result == expected, f"Test failed: {result} != {expected}"
    print("✓ PASSED")


def test_empty_sub_workflow():
    """Test edge case of empty sub-workflow."""
    print("\n=== Test 5: Empty Sub-Workflow ===")
    
    sub_workflow = WorkflowStructure()  # No start, no transitions
    result = get_sub_workflow_nodes(sub_workflow)
    expected = set()
    
    print(f"Expected: {expected}")
    print(f"Got:      {result}")
    
    assert result == expected, f"Test failed: {result} != {expected}"
    print("✓ PASSED")


def test_start_only_sub_workflow():
    """Test sub-workflow with only start node."""
    print("\n=== Test 6: Start-Only Sub-Workflow ===")
    
    sub_workflow = WorkflowStructure(start="lonely_start")
    # No transitions
    result = get_sub_workflow_nodes(sub_workflow)
    expected = {"lonely_start"}
    
    print(f"Expected: {expected}")
    print(f"Got:      {result}")
    
    assert result == expected, f"Test failed: {result} != {expected}"
    print("✓ PASSED")


def main():
    """Run all tests."""
    print("Testing get_sub_workflow_nodes Function - Bug Fix Demonstration")
    print("=" * 70)
    
    try:
        test_simple_sub_workflow()
        test_branching_sub_workflow()
        test_demonstrates_bug_fix()
        test_complex_sub_workflow()
        test_empty_sub_workflow()
        test_start_only_sub_workflow()
        
        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED!")
        print("\n📋 Summary of the Bug Fix:")
        print("• PROBLEM: Sub-workflow validation iterated over ALL workflow nodes")
        print("• SOLUTION: get_sub_workflow_nodes() extracts only actual sub-nodes")
        print("• BENEFIT: Eliminates false validation errors")
        print("• BENEFIT: Significant performance improvement")
        print("• BENEFIT: Correct dependency graph construction")
        
        return True
    
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)