"""
Workflow definition module.

This module contains the Workflow class for defining and building workflows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

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
        self.nodes: Dict[str, Callable] = {}
        self.node_inputs: Dict[str, List[str]] = {}
        self.node_outputs: Dict[str, str | None] = {}
        self.transitions: Dict[str, List[Tuple[str, Callable | None]]] = {}
        self.node_input_mappings: Dict[str, Dict[str, Any]] = {}
        self.current_node = None
        self._observers: List[WorkflowObserver] = []
        self._register_node(start_node)
        self.current_node = start_node
        # Loop-specific attributes (support for nested loops)
        self.loop_stack = []  # Stack of loop states: (entry_node, loop_nodes)
    
    @property
    def in_loop(self) -> bool:
        """Check if currently in a loop."""
        return len(self.loop_stack) > 0
    
    @property
    def loop_nodes(self) -> List[str]:
        """Get the current loop's nodes."""
        return self.loop_stack[-1][1] if self.loop_stack else []
    
    @property
    def loop_entry_node(self) -> str:
        """Get the current loop's entry node."""
        return self.loop_stack[-1][0] if self.loop_stack else None

    def _register_node(self, name: str):
        """Register a node without modifying the current node."""
        # Import here to avoid circular imports
        from ..nodes import Nodes
        if name not in Nodes.NODE_REGISTRY:
            raise ValueError(f"Node {name} not registered")
        func, inputs, output = Nodes.NODE_REGISTRY[name]
        self.nodes[name] = func
        self.node_inputs[name] = inputs
        self.node_outputs[name] = output

    def node(self, name: str, inputs_mapping: Dict[str, Any] | None = None):
        """Add a node to the workflow chain with an optional inputs mapping.

        Args:
            name: The name of the node to add.
            inputs_mapping: Optional dictionary mapping node inputs to context keys or callables.

        Returns:
            Self for method chaining.
        """
        self._register_node(name)
        if self.in_loop:
            self.loop_stack[-1][1].append(name)  # Add to current loop's nodes
        if inputs_mapping:
            self.node_input_mappings[name] = inputs_mapping
            logger.debug(f"Added inputs mapping for node {name}: {inputs_mapping}")
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

    def then(self, next_node: str, condition: Callable | None = None):
        """Add a transition to the next node with an optional condition.

        Args:
            next_node: Name of the node to transition to.
            condition: Optional callable taking context and returning a boolean.

        Returns:
            Self for method chaining.
        """
        if next_node not in self.nodes:
            self._register_node(next_node)
        
        # Prevent self-loops by checking if current_node is the same as next_node
        if self.current_node and self.current_node != next_node:
            self.transitions.setdefault(self.current_node, []).append((next_node, condition))
            logger.debug(f"Added transition from {self.current_node} to {next_node} with condition {condition}")
        elif self.current_node and self.current_node == next_node:
            logger.debug(f"Skipped self-loop transition from {self.current_node} to {next_node}")
        elif not self.current_node:
            logger.warning("No current node set for transition")
        
        self.current_node = next_node
        return self

    def branch(
        self,
        branches: List[Tuple[str, Callable | None]],
        default: str | None = None,
        next_node: str | None = None,
    ) -> "Workflow":
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
        self.current_node = next_node  # Explicitly set next_node if provided
        return self

    def converge(self, convergence_node: str) -> "Workflow":
        """Set a convergence point for all previous branches.

        Args:
            convergence_node: Name of the node where branches converge.

        Returns:
            Self for method chaining.
        """
        if convergence_node not in self.nodes:
            self._register_node(convergence_node)
        for node in self.nodes:
            if (node not in self.transitions or not self.transitions[node]) and node != convergence_node:
                self.transitions.setdefault(node, []).append((convergence_node, None))
                logger.debug(f"Added convergence from {node} to {convergence_node}")
        self.current_node = convergence_node
        return self

    def parallel(self, *nodes: str):
        """Add parallel nodes to execute concurrently.

        Args:
            *nodes: Variable number of node names to execute in parallel.

        Returns:
            Self for method chaining.
        """
        if self.current_node:
            for node in nodes:
                self._register_node(node)  # Register each parallel node
                self.transitions.setdefault(self.current_node, []).append((node, None))
        self.current_node = None
        return self

    def add_observer(self, observer: WorkflowObserver) -> "Workflow":
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

    def add_sub_workflow(self, name: str, sub_workflow: "Workflow", inputs: Dict[str, Any], output: str):
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
        self.current_node = name
        logger.debug(f"Added sub-workflow {name} with inputs {inputs} and output {output}")
        return self

    def start_loop(self):
        """Begin defining a loop in the workflow.

        Raises:
            ValueError: If called without a current node.

        Returns:
            Self for method chaining.
        """
        if self.current_node is None:
            raise ValueError("Cannot start loop without a current node")
        # Push new loop state onto stack
        self.loop_stack.append((self.current_node, []))
        return self

    def end_loop(self, condition: Callable[[Dict[str, Any]], bool], next_node: str):
        """End the loop, setting up transitions based on the condition.

        Args:
            condition: Callable taking context and returning True when the loop should exit.
            next_node: Name of the node to transition to after the loop exits.

        Raises:
            ValueError: If no loop nodes are defined.

        Returns:
            Self for method chaining.
        """
        if not self.in_loop:
            raise ValueError("No loop nodes defined")
        
        # Pop current loop state
        entry_node, loop_nodes = self.loop_stack.pop()
        
        if not loop_nodes:
            raise ValueError("No loop nodes defined")
        
        first_node = loop_nodes[0]
        last_node = loop_nodes[-1]
        
        # Transition from the node before the loop to the first loop node
        self.transitions.setdefault(entry_node, []).append((first_node, None))
        
        # Transitions within the loop
        for i in range(len(loop_nodes) - 1):
            self.transitions.setdefault(loop_nodes[i], []).append((loop_nodes[i + 1], None))
        
        # Conditional transitions from the last loop node
        # If condition is False, loop back to the first node
        self.transitions.setdefault(last_node, []).append((first_node, lambda ctx: not condition(ctx)))
        # If condition is True, exit to the next node
        self.transitions.setdefault(last_node, []).append((next_node, condition))
        
        # Register the next_node if not already present
        if next_node not in self.nodes:
            self._register_node(next_node)
        
        # Update state
        self.current_node = next_node
        
        return self

    def build(self, parent_engine: "WorkflowEngine" | None = None) -> "WorkflowEngine":
        """Build and return a WorkflowEngine instance with registered observers.

        Args:
            parent_engine: Optional parent WorkflowEngine for sub-workflows.

        Returns:
            Configured WorkflowEngine instance.
        """
        # Import here to avoid circular imports
        from .engine import WorkflowEngine
        engine = WorkflowEngine(self, parent_engine=parent_engine)
        for observer in self._observers:
            engine.add_observer(observer)
        return engine
