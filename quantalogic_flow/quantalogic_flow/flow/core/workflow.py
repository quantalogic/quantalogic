"""
Workflow definition module.

This module contains the Workflow class for defining and building workflows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Tuple

from loguru import logger

from .events import WorkflowObserver
from .sub_workflow import SubWorkflowNode

if TYPE_CHECKING:
    from .engine import WorkflowEngine


class Workflow:
    """Workflow definition class for building and orchestrating node sequences."""

    def __init__(self, start_node: str):
        """Initialize a workflow with a starting node.

        Args:
            start_node: The name of the initial node in the workflow.
        """
        self.start_node = start_node
        self.nodes: Dict[str, Any] = {}
        self.transitions: Dict[str, List[Tuple[str, Callable | None]]] = {}
        self.current_node: str | None = start_node
        self.is_looping = False
        self.loop_start_node: str | None = None
        self.is_parallel = False
        self.parallel_nodes: List[str] = []
        self.parallel_source_node: str | None = None
        self.convergence_nodes: Dict[str, str] = {}
        self.parallel_blocks: Dict[str, List[str]] = {}
        self._observers: List[WorkflowObserver] = []
        self.loop_stack: List[Tuple[str, List[str]]] = []
        self.loop_nodes: List[str] = []
        self.node_inputs: Dict[str, List[str]] = {}
        self.node_outputs: Dict[str, str] = {}
        self.node_input_mappings: Dict[str, Dict[str, Any]] = {}
        self.loop_entry_node: str | None = None
        self._register_node(start_node)

    def is_parallel_node(self, node_name: str) -> bool:
        """Check if a node is part of any parallel execution block."""
        for nodes in self.parallel_blocks.values():
            if node_name in nodes:
                return True
        return False

    def get_parallel_source_for_node(self, node_name: str) -> str | None:
        """Find the source node that initiated the parallel execution containing the given node."""
        for source, nodes in self.parallel_blocks.items():
            if node_name in nodes:
                return source
        return None

    def _register_node(self, name: str):
        """Register a node without modifying the current node."""
        # Import here to avoid circular imports
        from ..nodes import Nodes

        if name not in Nodes.NODE_REGISTRY:
            raise ValueError(f"Node {name} not registered")
        func, inputs, output = Nodes.NODE_REGISTRY[name]
        self.nodes[name] = func
        self.node_inputs[name] = inputs
        if output:
            self.node_outputs[name] = output

    def add_node(self, name: str, func: Callable, inputs: List[str], output: str):
        """Add a node dynamically to the workflow."""
        self.nodes[name] = func
        self.transitions.setdefault(self.current_node, []).append((name, None))
        logger.debug(f"Added node {name} to workflow with transition from {self.current_node}")

    def node(self, name: str, inputs_mapping: Dict[str, Any] | None = None) -> Workflow:
        """Add a node to the workflow without connecting it to the previous one."""
        self._register_node(name)
        if inputs_mapping:
            self.node_input_mappings[name] = inputs_mapping

        if self.is_parallel:
            # This is a convergence point
            if self.parallel_source_node:
                self.convergence_nodes[self.parallel_source_node] = name
            if not self.parallel_nodes:  # Handle empty parallel block
                self.transitions.setdefault(self.parallel_source_node, []).append((name, None))
            for node_name in self.parallel_nodes:
                self.transitions.setdefault(node_name, []).append((name, None))
            self.is_parallel = False
            self.parallel_nodes = []

        self.current_node = name
        return self

    def sequence(self, *nodes: str):
        """Add a sequence of nodes to execute in order.

        Args:
            *nodes: Variable number of node names to execute sequentially.

        Returns:
            Self for method chaining.
        """
        if not nodes:
            return self
        for node in nodes:
            # Import here to avoid circular imports
            from ..nodes import Nodes
            if node not in Nodes.NODE_REGISTRY:
                raise ValueError(f"Node {node} not registered")
            func, inputs, output = Nodes.NODE_REGISTRY[node]
            self.nodes[node] = func
            self.node_inputs[node] = inputs
            if output:
                self.node_outputs[node] = output

        # Add transition from current node to first node in sequence
        # Prevent self-loops by checking if current_node is the same as the first node
        if self.current_node and nodes and self.current_node != nodes[0]:
            self.transitions.setdefault(self.current_node, []).append((nodes[0], None))
            logger.debug(f"Added transition from {self.current_node} to {nodes[0]}")
        elif self.current_node and nodes and self.current_node == nodes[0]:
            logger.debug(f"Skipped self-loop transition from {self.current_node} to {nodes[0]}")

        # Add transitions between sequential nodes
        for i in range(len(nodes) - 1):
            self.transitions.setdefault(nodes[i], []).append((nodes[i + 1], None))
            logger.debug(f"Added transition from {nodes[i]} to {nodes[i + 1]}")

        self.current_node = nodes[-1] if nodes else self.current_node
        return self

    def then(self, next_node: str, condition: Callable | None = None) -> Workflow:
        """Connect the current node to the next one."""
        if self.current_node == next_node:
            logger.warning(f"Skipping self-loop transition from {self.current_node} to {next_node}")
            return self

        if self.current_node is None and not self.is_parallel:
            raise ValueError("Cannot call .then() without a current node.")

        self._register_node(next_node)

        if self.is_parallel:
            # This is a convergence point
            if self.parallel_source_node:
                self.convergence_nodes[self.parallel_source_node] = next_node
            if not self.parallel_nodes:  # Handle empty parallel block
                if self.parallel_source_node:
                    self.transitions.setdefault(self.parallel_source_node, []).append((next_node, None))
            for node_name in self.parallel_nodes:
                self.transitions.setdefault(node_name, []).append((next_node, None))
            self.is_parallel = False
            self.parallel_nodes = []
        else:
            if self.current_node:
                self.transitions.setdefault(self.current_node, []).append((next_node, condition))

        self.current_node = next_node
        return self

    def branch(
        self,
        branches: List[Tuple[str, Callable | None]],
        default: str | None,
        next_node: str | None = None,
    ) -> Workflow:
        """Add multiple conditional branches from the current node with an optional default and next node.

        Args:
            branches: List of tuples (next_node, condition), where condition takes context and returns a boolean.
            default: Optional node to transition to if no branch conditions are met.
            next_node: Optional node to set as current_node after branching (e.g., for convergence).

        Returns:
            Self for method chaining.
        """
        if not self.current_node:
            logger.warning("No current node set for branching")
            return self
        for next_node_name, condition in branches:
            if next_node_name not in self.nodes:
                self._register_node(next_node_name)
            self.transitions.setdefault(self.current_node, []).append((next_node_name, condition))
            logger.debug(f"Added branch from {self.current_node} to {next_node_name} with condition {condition}")
        if default:
            if default not in self.nodes:
                self._register_node(default)
            self.transitions.setdefault(self.current_node, []).append((default, None))
            logger.debug(f"Added default transition from {self.current_node} to {default}")

        if not self.is_parallel:
            self.current_node = next_node  # Explicitly set next_node if provided
        return self

    def converge(self, convergence_node: str) -> Workflow:
        """Set a convergence point for all previous branches.

        Args:
            convergence_node: Name of the node where branches converge.

        Returns:
            Self for method chaining.
        """
        if convergence_node not in self.nodes:
            self._register_node(convergence_node)

        if self.is_parallel and self.parallel_source_node:
            # The nodes that need to converge are the ones that were started in parallel.
            parallel_nodes = self.parallel_nodes
            for node in parallel_nodes:
                self.transitions.setdefault(node, []).append((convergence_node, None))

            # Store the convergence mapping
            self.convergence_nodes[self.parallel_source_node] = convergence_node

            # Reset parallel state
            self.is_parallel = False
            self.parallel_source_node = None
        else:
            # Fallback for non-parallel convergence (e.g., after a branch)
            # This connects all nodes that don't have an outgoing transition to the convergence node.
            for node in self.nodes:
                if (node not in self.transitions or not self.transitions[node]) and node != convergence_node:
                    self.transitions.setdefault(node, []).append((convergence_node, None))
                    logger.debug(f"Added convergence from {node} to {convergence_node}")

        self.current_node = convergence_node
        return self

    def parallel(self, *node_names: str) -> Workflow:
        """Define parallel execution paths from the current node."""
        if self.current_node is None:
            raise ValueError("Cannot start parallel execution without a current node.")

        from_node = self.current_node
        self.parallel_source_node = from_node
        self.current_node = None
        self.is_parallel = True
        self.parallel_nodes = list(node_names)
        self.parallel_blocks[from_node] = self.parallel_nodes

        if not node_names: # Handle empty parallel() call
            return self

        for node_name in node_names:
            self._register_node(node_name)
            self.transitions.setdefault(from_node, []).append((node_name, None))
        return self

    def add_observer(self, observer: WorkflowObserver) -> Workflow:
        """Add an event observer callback to the workflow.

        Args:
            observer: Callable to handle workflow events.

        Returns:
            Self for method chaining.
        """
        if observer not in self._observers:
            self._observers.append(observer)
            logger.debug(f"Added observer to workflow: {observer}")
        return self

    def add_sub_workflow(
        self,
        name: str,
        sub_workflow: Workflow,
        inputs: Dict[str, Any],
        output: str,
    ):
        """Add a sub-workflow as a node with flexible inputs mapping.

        Args:
            name: Name of the sub-workflow node.
            sub_workflow: The Workflow instance to embed.
            inputs: Dictionary mapping sub-workflow inputs to context keys or callables.
            output: Context key for the sub-workflow's result.

        Returns:
            Self for method chaining.
        """
        sub_node = SubWorkflowNode(sub_workflow, inputs, output)
        self.nodes[name] = sub_node
        self.node_inputs[name] = []
        self.node_outputs[name] = output
        self.node_input_mappings[name] = inputs or {}

        if self.current_node and self.current_node != name:
            self.transitions.setdefault(self.current_node, []).append((name, None))
            logger.debug(f"Added transition from {self.current_node} to sub-workflow {name}")

        if not self.is_parallel:
            self.current_node = name
        return self

    def loop(self, *node_names: str) -> Workflow:
        """Define a loop with a sequence of nodes.
        
        Args:
            *node_names: The nodes to execute in each loop iteration.
            
        Returns:
            Self for method chaining.
        """
        if not self.current_node:
            raise ValueError("Cannot start a loop without a current node.")

        if not node_names:
            raise ValueError("Loop must contain at least one node.")

        self.loop_entry_node = self.current_node
        self.loop_stack.append((self.current_node, list(node_names)))

        # Register all nodes in the loop
        for node in node_names:
            self._register_node(node)

        # The first node in the loop sequence becomes the current node
        self.current_node = node_names[0]

        return self

    @property
    def in_loop(self) -> bool:
        """Check if the workflow is currently defining a loop."""
        return len(self.loop_stack) > 0

    def end_loop(self, condition: Callable[[Dict[str, Any]], bool], next_node: str | None = None) -> Workflow:
        """End the current loop and set the transition to the next node.

        Args:
            condition: A callable that determines when the loop should exit.
            next_node: The node to transition to when the loop ends.

        Returns:
            Self for method chaining.
        """
        if not self.in_loop:
            raise ValueError("end_loop() called without an active loop.")

        entry_node, loop_nodes = self.loop_stack.pop()

        if not loop_nodes:
            raise ValueError("Loop must contain at least one node.")

        # Transition from the node before the loop to the first node of the loop
        self.transitions.setdefault(entry_node, []).append((loop_nodes[0], None))

        # Create transitions within the loop
        for i in range(len(loop_nodes) - 1):
            self.transitions.setdefault(loop_nodes[i], []).append((loop_nodes[i+1], None))

        # Add conditional transition from the last loop node
        last_node = loop_nodes[-1]

        # Loop back to the first node if condition is NOT met
        def loop_back_condition(ctx):
            return not condition(ctx)
        self.transitions.setdefault(last_node, []).append((loop_nodes[0], loop_back_condition))

        # Transition to the next node if the condition is met
        if next_node:
            self._register_node(next_node)
            self.transitions.setdefault(last_node, []).append((next_node, condition))
            self.current_node = next_node
        else:
            # If there's no next node, the workflow might end here if the condition is false.
            self.current_node = None

        self.loop_entry_node = None # Reset after loop is defined
        return self

    def build(self, **kwargs) -> WorkflowEngine:
        """Build an executable engine from the workflow."""
        # Import here to avoid circular imports
        from .engine import WorkflowEngine

        # Reset parallel flag at build time
        self.is_parallel = False
        self.parallel_source_node = None

        return WorkflowEngine(
            workflow=self,
            observers=self._observers,
            **kwargs
        )
