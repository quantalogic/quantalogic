"""
Workflow engine module.

This module contains the WorkflowEngine class for executing workflows.
"""

import asyncio
from typing import Any, Dict, List, Optional

from loguru import logger

from .events import WorkflowEvent, WorkflowEventType, WorkflowObserver
from .sub_workflow import SubWorkflowNode


class WorkflowEngine:
    """Engine for executing workflows with event monitoring and context management."""
    
    def __init__(self, workflow, parent_engine: Optional["WorkflowEngine"] = None):
        """Initialize the WorkflowEngine with a workflow and optional parent for sub-workflows."""
        self.workflow = workflow
        self.context: Dict[str, Any] = {}
        self.observers: List[WorkflowObserver] = []
        self.parent_engine = parent_engine

    def add_observer(self, observer: WorkflowObserver) -> None:
        """Register an event observer callback."""
        if observer not in self.observers:
            self.observers.append(observer)
            logger.debug(f"Added observer: {observer}")
        if self.parent_engine:
            self.parent_engine.add_observer(observer)

    def remove_observer(self, observer: WorkflowObserver) -> None:
        """Remove an event observer callback."""
        if observer in self.observers:
            self.observers.remove(observer)
            logger.debug(f"Removed observer: {observer}")

    async def _notify_observers(self, event: WorkflowEvent) -> None:
        """Asynchronously notify all observers of an event."""
        tasks = []
        for observer in self.observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    tasks.append(observer(event))
                else:
                    observer(event)
            except Exception as e:
                logger.error(f"Observer {observer} failed for {event.event_type.value}: {e}")
        if tasks:
            await asyncio.gather(*tasks)

    async def run(self, initial_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the workflow starting from the entry node with event notifications."""
        self.context = initial_context.copy()
        await self._notify_observers(
            WorkflowEvent(event_type=WorkflowEventType.WORKFLOW_STARTED, node_name=None, context=self.context)
        )

        current_node = self.workflow.start_node
        while current_node:
            logger.info(f"Executing node: {current_node}")
            await self._notify_observers(
                WorkflowEvent(event_type=WorkflowEventType.NODE_STARTED, node_name=current_node, context=self.context)
            )

            node_func = self.workflow.nodes.get(current_node)
            if not node_func:
                logger.error(f"Node {current_node} not found")
                exc = ValueError(f"Node {current_node} not found")
                await self._notify_observers(
                    WorkflowEvent(
                        event_type=WorkflowEventType.NODE_FAILED,
                        node_name=current_node,
                        context=self.context,
                        exception=exc,
                    )
                )
                break

            input_mappings = self.workflow.node_input_mappings.get(current_node, {})
            inputs = {}
            for key, mapping in input_mappings.items():
                if callable(mapping):
                    inputs[key] = mapping(self.context)
                elif isinstance(mapping, str):
                    inputs[key] = self.context.get(mapping)
                else:
                    inputs[key] = mapping
            for param in self.workflow.node_inputs[current_node]:
                if param not in inputs:
                    inputs[param] = self.context.get(param)

            result = None
            exception = None

            if isinstance(node_func, SubWorkflowNode):
                await self._notify_observers(
                    WorkflowEvent(
                        event_type=WorkflowEventType.SUB_WORKFLOW_ENTERED,
                        node_name=current_node,
                        context=self.context,
                        sub_workflow_name=current_node,
                    )
                )

            try:
                if isinstance(node_func, SubWorkflowNode):
                    result = await node_func(self)
                    usage = None
                else:
                    result = await node_func(**inputs)
                    usage = getattr(node_func, "usage", None)
                output_key = self.workflow.node_outputs[current_node]
                if output_key:
                    self.context[output_key] = result
                elif isinstance(result, dict):
                    self.context.update(result)
                    logger.debug(f"Updated context with {result} from node {current_node}")
                await self._notify_observers(
                    WorkflowEvent(
                        event_type=WorkflowEventType.NODE_COMPLETED,
                        node_name=current_node,
                        context=self.context,
                        result=result,
                        usage=usage,
                    )
                )
            except Exception as e:
                logger.error(f"Error executing node {current_node}: {e}")
                exception = e
                await self._notify_observers(
                    WorkflowEvent(
                        event_type=WorkflowEventType.NODE_FAILED,
                        node_name=current_node,
                        context=self.context,
                        exception=e,
                    )
                )
                raise
            finally:
                if isinstance(node_func, SubWorkflowNode):
                    await self._notify_observers(
                        WorkflowEvent(
                            event_type=WorkflowEventType.SUB_WORKFLOW_EXITED,
                            node_name=current_node,
                            context=self.context,
                            sub_workflow_name=current_node,
                            result=result,
                            exception=exception,
                        )
                    )

            next_nodes = self.workflow.transitions.get(current_node, [])
            current_node = None
            for next_node, condition in next_nodes:
                await self._notify_observers(
                    WorkflowEvent(
                        event_type=WorkflowEventType.TRANSITION_EVALUATED,
                        node_name=None,
                        context=self.context,
                        transition_from=current_node,
                        transition_to=next_node,
                    )
                )
                if condition is None or condition(self.context):
                    current_node = next_node
                    break

        logger.info("Workflow execution completed")
        await self._notify_observers(
            WorkflowEvent(event_type=WorkflowEventType.WORKFLOW_COMPLETED, node_name=None, context=self.context)
        )
        return self.context
