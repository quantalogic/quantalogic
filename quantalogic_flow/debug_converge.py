#!/usr/bin/env python3

from quantalogic_flow.flow.flow import Workflow, Nodes

@Nodes.define(output="start_output")
def start_node(input_data):
    return input_data

@Nodes.define(output="branch1_output")
def branch1_node(data):
    return f"branch1: {data}"

@Nodes.define(output="branch2_output")
def branch2_node(data):
    return f"branch2: {data}"

@Nodes.define(output="convergence_output")
def convergence_node(data):
    return f"converged: {data}"

workflow = Workflow("start_node")
print(f"After init: nodes={workflow.nodes}, transitions={workflow.transitions}")

workflow.parallel("branch1_node", "branch2_node")
print(f"After parallel: nodes={workflow.nodes}, transitions={workflow.transitions}")

workflow.converge("convergence_node")
print(f"After converge: nodes={workflow.nodes}, transitions={workflow.transitions}")

# Check convergence setup
convergence_transitions = []
for node, transitions in workflow.transitions.items():
    for target, condition in transitions:
        if target == "convergence_node":
            convergence_transitions.append(node)

print(f"Convergence transitions: {convergence_transitions}")
print(f"Current node: {workflow.current_node}")
