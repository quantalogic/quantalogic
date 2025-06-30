#!/usr/bin/env python3

import tempfile
from quantalogic_flow.flow.flow_generator import generate_executable_script
from quantalogic_flow.flow.flow_manager_schema import (
    FunctionDefinition,
    NodeDefinition,
    TransitionDefinition,
    WorkflowDefinition,
    WorkflowStructure,
)

# Create the branch workflow exactly like the test
branch_workflow = WorkflowDefinition(
    workflow=WorkflowStructure(
        start="start_node",
        nodes=["start_node", "branch1", "branch2", "default_node"],
        transitions=[
            TransitionDefinition(
                from_node="start_node",
                to_node="branch1",
                condition="lambda ctx: ctx.get('use_branch1', False)"
            ),
            TransitionDefinition(
                from_node="start_node",
                to_node="branch2",
                condition="lambda ctx: ctx.get('use_branch2', False)"
            ),
            TransitionDefinition(
                from_node="start_node",
                to_node="default_node",
                condition=None
            )
        ]
    ),
    nodes={
        "start_node": NodeDefinition(
            function="start_func",
            output="start_result"
        ),
        "branch1": NodeDefinition(
            function="branch1_func",
            output="branch1_result"
        ),
        "branch2": NodeDefinition(
            function="branch2_func",
            output="branch2_result"
        ),
        "default_node": NodeDefinition(
            function="default_func",
            output="default_result"
        )
    },
    functions={
        "start_func": FunctionDefinition(
            name="start_func",
            type="embedded",
            code="def start_func():\n    return 'start'",
            is_async=False
        ),
        "branch1_func": FunctionDefinition(
            name="branch1_func",
            type="embedded",
            code="def branch1_func():\n    return 'branch1'",
            is_async=False
        ),
        "branch2_func": FunctionDefinition(
            name="branch2_func",
            type="embedded",
            code="def branch2_func():\n    return 'branch2'",
            is_async=False
        ),
        "default_func": FunctionDefinition(
            name="default_func",
            type="embedded",
            code="def default_func():\n    return 'default'",
            is_async=False
        )
    }
)

global_vars = {"test_value": "hello"}

with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
    output_file = f.name

generate_executable_script(
    workflow_def=branch_workflow,
    global_vars=global_vars,
    output_file=output_file
)

with open(output_file) as f:
    content = f.read()

print("Generated content:")
print(content)
print(f"\nLooking for '.branch(' in content: {'.branch(' in content}")
print(f"Looking for 'default=' in content: {'default=' in content}")
