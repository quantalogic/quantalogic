#!/usr/bin/env python3

import tempfile
from quantalogic_flow.flow.flow_generator import generate_executable_script
from quantalogic_flow.flow.flow_manager_schema import *

# Test with the exact same setup as the failing test
workflow_structure = WorkflowStructure(
    start='start_node',
    nodes=['start_node', 'end_node'],
    transitions=[
        TransitionDefinition(from_node='start_node', to_node='end_node', condition=None)
    ]
)

workflow_def = WorkflowDefinition(
    workflow=workflow_structure,
    nodes={
        'start_node': NodeDefinition(name='start_node', function='start_func', output='start_result'),
        'end_node': NodeDefinition(name='end_node', function='end_func', output='end_result')
    },
    functions={
        'start_func': FunctionDefinition(name='start_func', type='embedded', code='def start_func(input_data):\n    return input_data', is_async=False),
        'end_func': FunctionDefinition(name='end_func', type='embedded', code='def end_func(data):\n    return f"processed: {data}"', is_async=False)
    }
)

global_vars = {'DEFAULT_MODEL': 'gpt-4', 'TEMPERATURE': 0.7}

with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
    output_file = f.name

generate_executable_script(workflow_def, global_vars, output_file)

# Debug: let's see what transitions we have
print('=== Debug Info ===')
print('Start node:', workflow_def.workflow.start)
print('Transitions count:', len(workflow_def.workflow.transitions))
print('Transitions:')
for i, trans in enumerate(workflow_def.workflow.transitions):
    print(f'  {i}: {trans.from_node} -> {trans.to_node} (condition: {trans.condition})')
print('Raw transitions list:', workflow_def.workflow.transitions)
print()

with open(output_file) as f:
    content = f.read()

print('=== Generated Script ===')
print(content)
print()
print('=== Test Checks ===')
print('Contains "workflow = Workflow(\\"start_node\\")\":', 'workflow = Workflow("start_node")' in content)
print('Contains ".sequence(\\"end_func\\")\":', '.sequence("end_func")' in content)
print('Contains "workflow.sequence(\\"end_node\\")\":', 'workflow.sequence("end_node")' in content)
print('Contains multiline format:', 'Workflow("start_node")' in content and '.sequence(' in content)
