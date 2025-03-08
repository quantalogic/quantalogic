#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru>=0.7.2",              # Logging utility
#     "litellm>=1.0.0",             # LLM integration
#     "pydantic>=2.0.0",            # Data validation and settings
#     "anyio>=4.0.0",               # Async utilities
#     "jinja2>=3.1.0",              # Templating engine
#     "instructor"  # Structured LLM output with litellm integration
# ]
# ///

import asyncio
import inspect  # Added for accurate parameter detection
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import instructor
from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound
from litellm import acompletion
from loguru import logger
from pydantic import BaseModel, ValidationError


# Define event types and structure for observer system
class WorkflowEventType(Enum):
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    TRANSITION_EVALUATED = "transition_evaluated"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    SUB_WORKFLOW_ENTERED = "sub_workflow_entered"
    SUB_WORKFLOW_EXITED = "sub_workflow_exited"


@dataclass
class WorkflowEvent:
    event_type: WorkflowEventType
    node_name: Optional[str]
    context: Dict[str, Any]
    result: Optional[Any] = None
    exception: Optional[Exception] = None
    transition_from: Optional[str] = None
    transition_to: Optional[str] = None
    sub_workflow_name: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None  # Added to store token usage and cost


WorkflowObserver = Callable[[WorkflowEvent], None]


# Define a class for sub-workflow nodes with updated inputs handling
class SubWorkflowNode:
    def __init__(self, sub_workflow: "Workflow", inputs: Dict[str, Any], output: str):
        """Initialize a sub-workflow node with flexible inputs mapping."""
        self.sub_workflow = sub_workflow
        self.inputs = inputs  # Maps sub_key to main_key, callable, or value
        self.output = output

    async def __call__(self, engine: "WorkflowEngine"):
        """Execute the sub-workflow with the engine's context using inputs mapping."""
        sub_context = {}
        for sub_key, mapping in self.inputs.items():
            if callable(mapping):
                sub_context[sub_key] = mapping(engine.context)
            elif isinstance(mapping, str):
                sub_context[sub_key] = engine.context.get(mapping)
            else:
                sub_context[sub_key] = mapping  # Direct value
        sub_engine = self.sub_workflow.build(parent_engine=engine)
        result = await sub_engine.run(sub_context)
        return result.get(self.output)


class WorkflowEngine:
    def __init__(self, workflow, parent_engine: Optional["WorkflowEngine"] = None):
        """Initialize the WorkflowEngine with a workflow and optional parent for sub-workflows."""
        self.workflow = workflow
        self.context: Dict[str, Any] = {}
        self.observers: List[WorkflowObserver] = []
        self.parent_engine = parent_engine  # Link to parent engine for sub-workflow observer propagation

    def add_observer(self, observer: WorkflowObserver) -> None:
        """Register an event observer callback."""
        if observer not in self.observers:
            self.observers.append(observer)
            logger.debug(f"Added observer: {observer}")
        if self.parent_engine:
            self.parent_engine.add_observer(observer)  # Propagate to parent for global visibility

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

            # Prepare inputs with mappings
            input_mappings = self.workflow.node_input_mappings.get(current_node, {})
            inputs = {}
            # Add all mapped inputs
            for key, mapping in input_mappings.items():
                if callable(mapping):
                    inputs[key] = mapping(self.context)
                elif isinstance(mapping, str):
                    inputs[key] = self.context.get(mapping)
                else:
                    inputs[key] = mapping  # Direct value
            # For parameters in node_inputs that are not mapped, get from context
            for param in self.workflow.node_inputs[current_node]:
                if param not in inputs:
                    inputs[param] = self.context.get(param)

            result = None
            exception = None

            # Handle sub-workflow nodes
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
                    result = await node_func(self)  # Sub-workflow handles its own inputs
                    usage = None  # Sub-workflow usage is handled by its own nodes
                else:
                    result = await node_func(**inputs)
                    usage = getattr(node_func, "usage", None)  # Extract usage if set by LLM nodes
                output_key = self.workflow.node_outputs[current_node]
                if output_key:
                    self.context[output_key] = result
                elif isinstance(result, dict):  # Update context if node returns a dict and output is None
                    self.context.update(result)
                    logger.debug(f"Updated context with {result} from node {current_node}")
                await self._notify_observers(
                    WorkflowEvent(
                        event_type=WorkflowEventType.NODE_COMPLETED,
                        node_name=current_node,
                        context=self.context,
                        result=result,
                        usage=usage,  # Include usage data in the event
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


class Workflow:
    def __init__(self, start_node: str):
        """Initialize a workflow with a starting node."""
        self.start_node = start_node
        self.nodes: Dict[str, Callable] = {}
        self.node_inputs: Dict[str, List[str]] = {}
        self.node_outputs: Dict[str, Optional[str]] = {}
        self.transitions: Dict[str, List[Tuple[str, Optional[Callable]]]] = {}
        self.node_input_mappings: Dict[str, Dict[str, Any]] = {}  # Store input mappings for nodes
        self.current_node = None
        self._observers: List[WorkflowObserver] = []
        self._register_node(start_node)  # Register the start node without setting current_node
        self.current_node = start_node  # Set current_node explicitly after registration

    def _register_node(self, name: str):
        """Register a node without modifying the current node."""
        if name not in Nodes.NODE_REGISTRY:
            raise ValueError(f"Node {name} not registered")
        func, inputs, output = Nodes.NODE_REGISTRY[name]
        self.nodes[name] = func
        self.node_inputs[name] = inputs
        self.node_outputs[name] = output

    def node(self, name: str, inputs_mapping: Optional[Dict[str, Any]] = None):
        """Add a node to the workflow chain with an optional inputs mapping."""
        self._register_node(name)
        if inputs_mapping:
            self.node_input_mappings[name] = inputs_mapping
            logger.debug(f"Added inputs mapping for node {name}: {inputs_mapping}")
        self.current_node = name
        return self

    def sequence(self, *nodes: str):
        """Add a sequence of nodes to execute in order."""
        if not nodes:
            return self
        for node in nodes:
            if node not in Nodes.NODE_REGISTRY:
                raise ValueError(f"Node {node} not registered")
            func, inputs, output = Nodes.NODE_REGISTRY[node]
            self.nodes[node] = func
            self.node_inputs[node] = inputs
            self.node_outputs[node] = output
        for i in range(len(nodes) - 1):
            self.transitions.setdefault(nodes[i], []).append((nodes[i + 1], None))
        self.current_node = nodes[-1]
        return self

    def then(self, next_node: str, condition: Optional[Callable] = None):
        """Add a transition to the next node with an optional condition."""
        if next_node not in self.nodes:
            self._register_node(next_node)  # Register without changing current_node
        if self.current_node:
            self.transitions.setdefault(self.current_node, []).append((next_node, condition))
            logger.debug(f"Added transition from {self.current_node} to {next_node} with condition {condition}")
        else:
            logger.warning("No current node set for transition")
        self.current_node = next_node
        return self

    def branch(self, branches: List[Tuple[str, Optional[Callable]]]) -> "Workflow":
        """Add multiple conditional branches from the current node."""
        if not self.current_node:
            logger.warning("No current node set for branching")
            return self
        for next_node, condition in branches:
            if next_node not in self.nodes:
                self._register_node(next_node)
            self.transitions.setdefault(self.current_node, []).append((next_node, condition))
            logger.debug(f"Added branch from {self.current_node} to {next_node} with condition {condition}")
        return self

    def converge(self, convergence_node: str) -> "Workflow":
        """Set a convergence point for all previous branches."""
        if convergence_node not in self.nodes:
            self._register_node(convergence_node)
        # Find all leaf nodes (nodes with no outgoing transitions) and point them to convergence_node
        for node in self.nodes:
            if (node not in self.transitions or not self.transitions[node]) and node != convergence_node:
                self.transitions.setdefault(node, []).append((convergence_node, None))
                logger.debug(f"Added convergence from {node} to {convergence_node}")
        self.current_node = convergence_node
        return self

    def parallel(self, *nodes: str):
        """Add parallel nodes to execute concurrently."""
        if self.current_node:
            for node in nodes:
                self.transitions.setdefault(self.current_node, []).append((node, None))
        self.current_node = None  # Reset after parallel to force explicit next node
        return self

    def add_observer(self, observer: WorkflowObserver) -> "Workflow":
        """Add an event observer callback to the workflow."""
        if observer not in self._observers:
            self._observers.append(observer)
            logger.debug(f"Added observer to workflow: {observer}")
        return self  # Support chaining

    def add_sub_workflow(self, name: str, sub_workflow: "Workflow", inputs: Dict[str, Any], output: str):
        """Add a sub-workflow as a node with flexible inputs mapping."""
        sub_node = SubWorkflowNode(sub_workflow, inputs, output)
        self.nodes[name] = sub_node
        self.node_inputs[name] = []  # Inputs handled internally by SubWorkflowNode
        self.node_outputs[name] = output
        self.current_node = name
        logger.debug(f"Added sub-workflow {name} with inputs {inputs} and output {output}")
        return self

    def build(self, parent_engine: Optional["WorkflowEngine"] = None) -> WorkflowEngine:
        """Build and return a WorkflowEngine instance with registered observers."""
        engine = WorkflowEngine(self, parent_engine=parent_engine)
        for observer in self._observers:
            engine.add_observer(observer)
        return engine


class Nodes:
    NODE_REGISTRY: Dict[str, Tuple[Callable, List[str], Optional[str]]] = {}  # Registry to hold node functions and metadata

    @classmethod
    def define(cls, output: Optional[str] = None):
        """Decorator for defining simple workflow nodes."""
        def decorator(func: Callable) -> Callable:
            async def wrapped_func(**kwargs):
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(**kwargs)
                    else:
                        result = func(**kwargs)
                    logger.debug(f"Node {func.__name__} executed with result: {result}")
                    return result
                except Exception as e:
                    logger.error(f"Error in node {func.__name__}: {e}")
                    raise

            # Get parameter names from function signature
            sig = inspect.signature(func)
            inputs = [param.name for param in sig.parameters.values()]
            logger.debug(f"Registering node {func.__name__} with inputs {inputs} and output {output}")
            cls.NODE_REGISTRY[func.__name__] = (wrapped_func, inputs, output)
            return wrapped_func
        return decorator

    @classmethod
    def validate_node(cls, output: str):
        """Decorator for nodes that validate inputs."""
        def decorator(func: Callable) -> Callable:
            async def wrapped_func(**kwargs):
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(**kwargs)
                    else:
                        result = func(**kwargs)
                    if not isinstance(result, str):
                        raise ValueError(f"Validation node {func.__name__} must return a string")
                    logger.info(f"Validation result from {func.__name__}: {result}")
                    return result
                except Exception as e:
                    logger.error(f"Validation error in {func.__name__}: {e}")
                    raise

            # Get parameter names from function signature
            sig = inspect.signature(func)
            inputs = [param.name for param in sig.parameters.values()]
            logger.debug(f"Registering node {func.__name__} with inputs {inputs} and output {output}")
            cls.NODE_REGISTRY[func.__name__] = (wrapped_func, inputs, output)
            return wrapped_func
        return decorator

    @classmethod
    def transform_node(cls, output: str, transformer: Callable[[Any], Any]):
        """Decorator for nodes that transform their inputs."""
        def decorator(func: Callable) -> Callable:
            async def wrapped_func(**kwargs):
                try:
                    # Apply transformer to the first input value
                    input_key = list(kwargs.keys())[0] if kwargs else None
                    if input_key:
                        transformed_input = transformer(kwargs[input_key])
                        kwargs[input_key] = transformed_input
                    if asyncio.iscoroutinefunction(func):
                        result = await func(**kwargs)
                    else:
                        result = func(**kwargs)
                    logger.debug(f"Transformed node {func.__name__} executed with result: {result}")
                    return result
                except Exception as e:
                    logger.error(f"Error in transform node {func.__name__}: {e}")
                    raise

            # Get parameter names from function signature
            sig = inspect.signature(func)
            inputs = [param.name for param in sig.parameters.values()]
            logger.debug(f"Registering node {func.__name__} with inputs {inputs} and output {output}")
            cls.NODE_REGISTRY[func.__name__] = (wrapped_func, inputs, output)
            return wrapped_func
        return decorator

    @staticmethod
    def _load_prompt_from_file(prompt_file: str, context: Dict[str, Any]) -> str:
        """Load and render a Jinja2 template from an external file."""
        try:
            file_path = Path(prompt_file).resolve()
            directory = file_path.parent
            filename = file_path.name
            env = Environment(loader=FileSystemLoader(directory))
            template = env.get_template(filename)
            return template.render(**context)
        except TemplateNotFound as e:
            logger.error(f"Jinja2 template file '{prompt_file}' not found: {e}")
            raise ValueError(f"Prompt file '{prompt_file}' not found")
        except Exception as e:
            logger.error(f"Error loading or rendering prompt file '{prompt_file}': {e}")
            raise

    @staticmethod
    def _render_template(template: str, template_file: Optional[str], context: Dict[str, Any]) -> str:
        """Render a Jinja2 template from either a string or an external file."""
        if template_file:
            return Nodes._load_prompt_from_file(template_file, context)
        try:
            return Template(template).render(**context)
        except Exception as e:
            logger.error(f"Error rendering template: {e}")
            raise

    @classmethod
    def llm_node(
        cls,
        system_prompt: str,
        output: str,
        prompt_template: str = "",
        prompt_file: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        top_p: float = 1.0,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
        **kwargs,
    ):
        """Decorator for creating LLM nodes with plain text output, supporting dynamic parameters via input mappings."""
        def decorator(func: Callable) -> Callable:
            async def wrapped_func(model: str, **func_kwargs):
                # Extract parameters from func_kwargs if provided, else use defaults
                system_prompt_to_use = func_kwargs.pop("system_prompt", system_prompt)
                prompt_template_to_use = func_kwargs.pop("prompt_template", prompt_template)
                prompt_file_to_use = func_kwargs.pop("prompt_file", prompt_file)
                temperature_to_use = func_kwargs.pop("temperature", temperature)
                max_tokens_to_use = func_kwargs.pop("max_tokens", max_tokens)
                top_p_to_use = func_kwargs.pop("top_p", top_p)
                presence_penalty_to_use = func_kwargs.pop("presence_penalty", presence_penalty)
                frequency_penalty_to_use = func_kwargs.pop("frequency_penalty", frequency_penalty)

                # Use only signature parameters for template rendering
                sig = inspect.signature(func)
                template_vars = {k: v for k, v in func_kwargs.items() if k in sig.parameters}
                prompt = cls._render_template(prompt_template_to_use, prompt_file_to_use, template_vars)
                messages = [
                    {"role": "system", "content": system_prompt_to_use},
                    {"role": "user", "content": prompt},
                ]
                
                # Log the model and a preview of the prompt
                truncated_prompt = prompt[:200] + "..." if len(prompt) > 200 else prompt
                logger.info(f"LLM node {func.__name__} using model: {model}")
                logger.debug(f"System prompt: {system_prompt_to_use[:100]}...")
                logger.debug(f"User prompt preview: {truncated_prompt}")
                
                try:
                    response = await acompletion(
                        model=model,
                        messages=messages,
                        temperature=temperature_to_use,
                        max_tokens=max_tokens_to_use,
                        top_p=top_p_to_use,
                        presence_penalty=presence_penalty_to_use,
                        frequency_penalty=frequency_penalty_to_use,
                        drop_params=True,
                        **kwargs,
                    )
                    content = response.choices[0].message.content.strip()
                    wrapped_func.usage = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                        "cost": getattr(response, "cost", None),
                    }
                    logger.debug(f"LLM output from {func.__name__}: {content[:50]}...")
                    return content
                except Exception as e:
                    logger.error(f"Error in LLM node {func.__name__}: {e}")
                    raise

            # Get parameter names from function signature and add 'model'
            sig = inspect.signature(func)
            inputs = ['model'] + [param.name for param in sig.parameters.values()]
            logger.debug(f"Registering node {func.__name__} with inputs {inputs} and output {output}")
            cls.NODE_REGISTRY[func.__name__] = (wrapped_func, inputs, output)
            return wrapped_func
        return decorator

    @classmethod
    def structured_llm_node(
        cls,
        system_prompt: str,
        output: str,
        response_model: Type[BaseModel],
        prompt_template: str = "",
        prompt_file: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        top_p: float = 1.0,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
        **kwargs,
    ):
        """Decorator for creating LLM nodes with structured output, supporting dynamic parameters via input mappings."""
        try:
            client = instructor.from_litellm(acompletion)
        except ImportError:
            logger.error("Instructor not installed. Install with 'pip install instructor[litellm]'")
            raise ImportError("Instructor is required for structured_llm_node")

        def decorator(func: Callable) -> Callable:
            async def wrapped_func(model: str, **func_kwargs):
                # Extract parameters from func_kwargs if provided, else use defaults
                system_prompt_to_use = func_kwargs.pop("system_prompt", system_prompt)
                prompt_template_to_use = func_kwargs.pop("prompt_template", prompt_template)
                prompt_file_to_use = func_kwargs.pop("prompt_file", prompt_file)
                temperature_to_use = func_kwargs.pop("temperature", temperature)
                max_tokens_to_use = func_kwargs.pop("max_tokens", max_tokens)
                top_p_to_use = func_kwargs.pop("top_p", top_p)
                presence_penalty_to_use = func_kwargs.pop("presence_penalty", presence_penalty)
                frequency_penalty_to_use = func_kwargs.pop("frequency_penalty", frequency_penalty)

                # Use only signature parameters for template rendering
                sig = inspect.signature(func)
                template_vars = {k: v for k, v in func_kwargs.items() if k in sig.parameters}
                prompt = cls._render_template(prompt_template_to_use, prompt_file_to_use, template_vars)
                messages = [
                    {"role": "system", "content": system_prompt_to_use},
                    {"role": "user", "content": prompt},
                ]
                
                # Log the model and a preview of the prompt
                truncated_prompt = prompt[:200] + "..." if len(prompt) > 200 else prompt
                logger.info(f"Structured LLM node {func.__name__} using model: {model}")
                logger.debug(f"System prompt: {system_prompt_to_use[:100]}...")
                logger.debug(f"User prompt preview: {truncated_prompt}")
                logger.debug(f"Expected response model: {response_model.__name__}")
                
                try:
                    structured_response, raw_response = await client.chat.completions.create_with_completion(
                        model=model,
                        messages=messages,
                        response_model=response_model,
                        temperature=temperature_to_use,
                        max_tokens=max_tokens_to_use,
                        top_p=top_p_to_use,
                        presence_penalty=presence_penalty_to_use,
                        frequency_penalty=frequency_penalty_to_use,
                        drop_params=True,
                        **kwargs,
                    )
                    wrapped_func.usage = {
                        "prompt_tokens": raw_response.usage.prompt_tokens,
                        "completion_tokens": raw_response.usage.completion_tokens,
                        "total_tokens": raw_response.usage.total_tokens,
                        "cost": getattr(raw_response, "cost", None),
                    }
                    logger.debug(f"Structured output from {func.__name__}: {structured_response}")
                    return structured_response
                except ValidationError as e:
                    logger.error(f"Validation error in {func.__name__}: {e}")
                    raise
                except Exception as e:
                    logger.error(f"Error in structured LLM node {func.__name__}: {e}")
                    raise

            # Get parameter names from function signature and add 'model'
            sig = inspect.signature(func)
            inputs = ['model'] + [param.name for param in sig.parameters.values()]
            logger.debug(f"Registering node {func.__name__} with inputs {inputs} and output {output}")
            cls.NODE_REGISTRY[func.__name__] = (wrapped_func, inputs, output)
            return wrapped_func
        return decorator

    @classmethod
    def template_node(
        cls,
        output: str,
        template: str = "",
        template_file: Optional[str] = None,
    ):
        """Decorator for creating nodes that apply a Jinja2 template to inputs, supporting dynamic parameters."""
        def decorator(func: Callable) -> Callable:
            async def wrapped_func(**func_kwargs):
                # Extract template parameters from func_kwargs if provided, else use defaults
                template_to_use = func_kwargs.pop("template", template)
                template_file_to_use = func_kwargs.pop("template_file", template_file)

                # Use only signature parameters (excluding rendered_content) for template rendering
                sig = inspect.signature(func)
                expected_params = [p.name for p in sig.parameters.values() if p.name != 'rendered_content']
                template_vars = {k: v for k, v in func_kwargs.items() if k in expected_params}
                rendered_content = cls._render_template(template_to_use, template_file_to_use, template_vars)

                # Filter func_kwargs for the function call
                filtered_kwargs = {k: v for k, v in func_kwargs.items() if k in expected_params}

                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(rendered_content=rendered_content, **filtered_kwargs)
                    else:
                        result = func(rendered_content=rendered_content, **filtered_kwargs)
                    logger.debug(f"Template node {func.__name__} rendered: {rendered_content[:50]}...")
                    return result
                except Exception as e:
                    logger.error(f"Error in template node {func.__name__}: {e}")
                    raise

            # Get parameter names from function signature and add 'rendered_content' if not present
            sig = inspect.signature(func)
            inputs = [param.name for param in sig.parameters.values()]
            if 'rendered_content' not in inputs:
                inputs.insert(0, 'rendered_content')
            logger.debug(f"Registering node {func.__name__} with inputs {inputs} and output {output}")
            cls.NODE_REGISTRY[func.__name__] = (wrapped_func, inputs, output)
            return wrapped_func
        return decorator


# Example workflow with observer integration, updated nodes, input mappings, and dynamic parameters
async def example_workflow():
    # Define Pydantic model for structured output
    class OrderDetails(BaseModel):
        order_id: str
        items_in_stock: List[str]
        items_out_of_stock: List[str]

    # Define an example observer for progress
    async def progress_monitor(event: WorkflowEvent):
        print(f"[{event.event_type.value}] {event.node_name or 'Workflow'}")
        if event.result is not None:
            print(f"Result: {event.result}")
        if event.exception is not None:
            print(f"Exception: {event.exception}")

    # Define an observer for token usage
    class TokenUsageObserver:
        def __init__(self):
            self.total_prompt_tokens = 0
            self.total_completion_tokens = 0
            self.total_cost = 0.0
            self.node_usages = {}

        def __call__(self, event: WorkflowEvent):
            if event.event_type == WorkflowEventType.NODE_COMPLETED and event.usage:
                usage = event.usage
                self.total_prompt_tokens += usage.get("prompt_tokens", 0)
                self.total_completion_tokens += usage.get("completion_tokens", 0)
                if usage.get("cost") is not None:
                    self.total_cost += usage["cost"]
                self.node_usages[event.node_name] = usage
            if event.event_type == WorkflowEventType.WORKFLOW_COMPLETED:
                print(f"Total prompt tokens: {self.total_prompt_tokens}")
                print(f"Total completion tokens: {self.total_completion_tokens}")
                print(f"Total cost: {self.total_cost}")
                for node, usage in self.node_usages.items():
                    print(f"Node {node}: {usage}")

    # Define nodes
    @Nodes.validate_node(output="validation_result")
    async def validate_order(order: Dict[str, Any]) -> str:
        return "Order validated" if order.get("items") else "Invalid order"

    @Nodes.structured_llm_node(
        system_prompt="You are an inventory checker. Respond with a JSON object containing 'order_id', 'items_in_stock', and 'items_out_of_stock'.",
        output="inventory_status",
        response_model=OrderDetails,
        prompt_template="Check if the following items are in stock: {{ items }}. Return the result in JSON format with 'order_id' set to '123'.",
    )
    async def check_inventory(items: List[str]) -> OrderDetails:
        return OrderDetails(order_id="123", items_in_stock=["item1"], items_out_of_stock=[])

    @Nodes.define(output="payment_status")
    async def process_payment(order: Dict[str, Any]) -> str:
        return "Payment processed"

    @Nodes.define(output="shipping_confirmation")
    async def arrange_shipping(order: Dict[str, Any]) -> str:
        return "Shipping arranged"

    @Nodes.define(output="order_status")
    async def update_order_status(shipping_confirmation: str) -> str:
        return "Order updated"

    @Nodes.define(output="email_status")
    async def send_confirmation_email(shipping_confirmation: str) -> str:
        return "Email sent"

    @Nodes.define(output="notification_status")
    async def notify_customer_out_of_stock(inventory_status: OrderDetails) -> str:
        return "Customer notified of out-of-stock"

    @Nodes.transform_node(output="transformed_items", transformer=lambda x: [item.upper() for item in x])
    async def transform_items(items: List[str]) -> List[str]:
        return items

    @Nodes.template_node(
        output="formatted_message",
        template="Order contains: {{ items | join(', ') }}",
    )
    async def format_order_message(rendered_content: str, items: List[str]) -> str:
        return rendered_content

    # Sub-workflow for payment and shipping
    payment_shipping_sub_wf = Workflow("process_payment").sequence("process_payment", "arrange_shipping")

    # Instantiate token usage observer
    token_observer = TokenUsageObserver()

    # Main workflow with dynamic parameter overrides
    workflow = (
        Workflow("validate_order")
        .add_observer(progress_monitor)
        .add_observer(token_observer)
        .node("validate_order", inputs_mapping={"order": "customer_order"})
        .node("transform_items")
        .node("format_order_message", inputs_mapping={
            "items": "items",
            "template": "Custom order: {{ items | join(', ') }}"  # Dynamic override
        })
        .node("check_inventory", inputs_mapping={
            "model": lambda ctx: "gemini/gemini-2.0-flash",
            "items": "transformed_items",
            "temperature": 0.5,  # Dynamic override
            "max_tokens": 1000   # Dynamic override
        })
        .add_sub_workflow(
            "payment_shipping",
            payment_shipping_sub_wf,
            inputs={"order": lambda ctx: {"items": ctx["items"]}},
            output="shipping_confirmation"
        )
        .branch([
            ("payment_shipping", lambda ctx: len(ctx.get("inventory_status").items_out_of_stock) == 0 if ctx.get("inventory_status") else False),
            ("notify_customer_out_of_stock", lambda ctx: len(ctx.get("inventory_status").items_out_of_stock) > 0 if ctx.get("inventory_status") else True)
        ])
        .converge("update_order_status")
        .sequence("update_order_status", "send_confirmation_email")
    )

    # Execute workflow
    initial_context = {"customer_order": {"items": ["item1", "item2"]}, "items": ["item1", "item2"]}
    engine = workflow.build()
    result = await engine.run(initial_context)
    logger.info(f"Workflow result: {result}")


if __name__ == "__main__":
    logger.info("Initializing Quantalogic Flow Package")
    asyncio.run(example_workflow())