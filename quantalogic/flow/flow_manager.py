import importlib
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, Union

import yaml
from loguru import logger
from pydantic import BaseModel, ValidationError

# Import directly from flow.py to avoid circular import through __init__.py
from quantalogic.flow.flow import Nodes, Workflow
from quantalogic.flow.flow_manager_schema import (
    FunctionDefinition,
    NodeDefinition,
    TransitionDefinition,
    WorkflowDefinition,
    WorkflowStructure,
)


class WorkflowManager:
    def __init__(self, workflow: Optional[WorkflowDefinition] = None):
        """Initialize the WorkflowManager with an optional workflow definition."""
        self.workflow = workflow or WorkflowDefinition()

    def add_node(
        self,
        name: str,
        function: Optional[str] = None,
        sub_workflow: Optional[WorkflowStructure] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        output: Optional[str] = None,
        retries: int = 3,
        delay: float = 1.0,
        timeout: Optional[float] = None,
        parallel: bool = False,
    ) -> None:
        """Add a new node to the workflow definition, supporting sub-workflows and LLM nodes."""
        node = NodeDefinition(
            function=function,
            sub_workflow=sub_workflow,
            llm_config=llm_config,
            output=output or (f"{name}_result" if function or llm_config else None),
            retries=retries,
            delay=delay,
            timeout=timeout,
            parallel=parallel,
        )
        self.workflow.nodes[name] = node

    def remove_node(self, name: str) -> None:
        """Remove a node and clean up related transitions and start node."""
        if name not in self.workflow.nodes:
            raise ValueError(f"Node '{name}' does not exist")
        del self.workflow.nodes[name]
        self.workflow.workflow.transitions = [
            t
            for t in self.workflow.workflow.transitions
            if t.from_ != name and (isinstance(t.to, str) or name not in t.to)
        ]
        if self.workflow.workflow.start == name:
            self.workflow.workflow.start = None

    def update_node(
        self,
        name: str,
        function: Optional[str] = None,
        output: Optional[str] = None,
        retries: Optional[int] = None,
        delay: Optional[float] = None,
        timeout: Optional[Union[float, None]] = None,
        parallel: Optional[bool] = None,
    ) -> None:
        """Update specific fields of an existing node."""
        if name not in self.workflow.nodes:
            raise ValueError(f"Node '{name}' does not exist")
        node = self.workflow.nodes[name]
        if function is not None:
            node.function = function
        if output is not None:
            node.output = output
        if retries is not None:
            node.retries = retries
        if delay is not None:
            node.delay = delay
        if timeout is not None:
            node.timeout = timeout
        if parallel is not None:
            node.parallel = parallel

    def add_transition(
        self,
        from_: str,
        to: Union[str, List[str]],
        condition: Optional[str] = None,
    ) -> None:
        """Add a transition between nodes, ensuring all nodes exist."""
        if from_ not in self.workflow.nodes:
            raise ValueError(f"Source node '{from_}' does not exist")
        if isinstance(to, str):
            if to not in self.workflow.nodes:
                raise ValueError(f"Target node '{to}' does not exist")
        else:
            for t in to:
                if t not in self.workflow.nodes:
                    raise ValueError(f"Target node '{t}' does not exist")
        transition = TransitionDefinition(from_=from_, to=to, condition=condition)
        self.workflow.workflow.transitions.append(transition)

    def set_start_node(self, name: str) -> None:
        """Set the start node of the workflow."""
        if name not in self.workflow.nodes:
            raise ValueError(f"Node '{name}' does not exist")
        self.workflow.workflow.start = name

    def add_function(
        self,
        name: str,
        type_: str,
        code: Optional[str] = None,
        module: Optional[str] = None,
        function: Optional[str] = None,
    ) -> None:
        """Add a function definition to the workflow."""
        func_def = FunctionDefinition(type=type_, code=code, module=module, function=function)
        self.workflow.functions[name] = func_def

    def _resolve_model(self, model_str: str) -> Type[BaseModel]:
        """Resolve a string to a Pydantic model class for structured_llm_node."""
        try:
            module_name, class_name = model_str.split(":")
            module = importlib.import_module(module_name)
            model_class = getattr(module, class_name)
            if not issubclass(model_class, BaseModel):
                raise ValueError(f"{model_str} is not a Pydantic model")
            return model_class
        except (ValueError, ImportError, AttributeError) as e:
            raise ValueError(f"Failed to resolve response_model '{model_str}': {e}")

    def instantiate_workflow(self) -> Workflow:
        """Instantiates a Workflow object based on the definitions stored in the WorkflowManager."""
        functions: Dict[str, Callable] = {}
        for func_name, func_def in self.workflow.functions.items():
            if func_def.type == "embedded":
                local_scope = {}
                exec(func_def.code, local_scope)
                if func_name not in local_scope:
                    raise ValueError(f"Embedded function '{func_name}' not defined in code")
                functions[func_name] = local_scope[func_name]
            elif func_def.type == "external":
                try:
                    module = importlib.import_module(func_def.module)
                    functions[func_name] = getattr(module, func_def.function)
                except (ImportError, AttributeError) as e:
                    raise ValueError(f"Failed to import external function '{func_name}': {e}")

        if not self.workflow.workflow.start:
            raise ValueError("Start node not set in workflow definition")
        wf = Workflow(start=self.workflow.workflow.start)

        sub_workflows: Dict[str, Workflow] = {}
        for node_name, node_def in self.workflow.nodes.items():
            if node_def.sub_workflow:
                sub_wf = Workflow(node_def.sub_workflow.start)
                sub_workflows[node_name] = sub_wf
                added_sub_nodes = set()
                for trans in node_def.sub_workflow.transitions:
                    from_node = trans.from_
                    to_nodes = [trans.to] if isinstance(trans.to, str) else trans.to
                    if from_node not in added_sub_nodes:
                        sub_wf.node(from_node)
                        added_sub_nodes.add(from_node)
                    for to_node in to_nodes:
                        if to_node not in added_sub_nodes:
                            sub_wf.node(to_node)
                            added_sub_nodes.add(to_node)
                    condition = eval(f"lambda ctx: {trans.condition}") if trans.condition else lambda _: True
                    if len(to_nodes) > 1:
                        sub_wf.parallel(*to_nodes, condition=condition)
                    else:
                        sub_wf.then(to_nodes[0], condition=condition)
                inputs = list(Nodes.NODE_REGISTRY[sub_wf.start_node][1])
                wf.add_sub_workflow(node_name, sub_wf, inputs={k: k for k in inputs}, output=node_def.output)
            elif node_def.function:
                if node_def.function not in functions:
                    raise ValueError(f"Function '{node_def.function}' for node '{node_name}' not found")
                func = functions[node_def.function]
                Nodes.define(
                    output=node_def.output,
                )(func)
            elif node_def.llm_config:
                llm_config = node_def.llm_config
                # Extract inputs from prompt_template using regex
                inputs = set(re.findall(r"{{\s*([^}]+?)\s*}}", llm_config.prompt_template))
                cleaned_inputs = set()
                for input_var in inputs:
                    base_var = re.split(r"\s*[\+\-\*/]\s*", input_var.strip())[0].strip()
                    if base_var.isidentifier():
                        cleaned_inputs.add(base_var)
                inputs_list = list(cleaned_inputs)

                # Define a dummy function to be decorated
                async def dummy_func(**kwargs):
                    pass  # This will be replaced by the decorator logic

                if llm_config.response_model:
                    # Structured LLM node
                    response_model = self._resolve_model(llm_config.response_model)
                    decorated_func = Nodes.structured_llm_node(
                        model=llm_config.model,
                        system_prompt=llm_config.system_prompt or "",
                        prompt_template=llm_config.prompt_template,
                        response_model=response_model,
                        output=node_def.output or f"{node_name}_result",
                        temperature=llm_config.temperature,
                        max_tokens=llm_config.max_tokens or 2000,
                        top_p=llm_config.top_p,
                        presence_penalty=llm_config.presence_penalty,
                        frequency_penalty=llm_config.frequency_penalty,
                        api_key=llm_config.api_key,
                    )(dummy_func)
                else:
                    # Plain LLM node
                    decorated_func = Nodes.llm_node(
                        model=llm_config.model,
                        system_prompt=llm_config.system_prompt or "",
                        prompt_template=llm_config.prompt_template,
                        output=node_def.output or f"{node_name}_result",
                        temperature=llm_config.temperature,
                        max_tokens=llm_config.max_tokens or 2000,
                        top_p=llm_config.top_p,
                        presence_penalty=llm_config.presence_penalty,
                        frequency_penalty=llm_config.frequency_penalty,
                        api_key=llm_config.api_key,
                    )(dummy_func)

                # Register the node in NODE_REGISTRY with proper inputs
                Nodes.NODE_REGISTRY[node_name] = (decorated_func, inputs_list, node_def.output or f"{node_name}_result")
                logger.debug(f"Registered LLM node '{node_name}' with inputs {inputs_list} and output {node_def.output or f'{node_name}_result'}")

        added_nodes = set()
        for trans in self.workflow.workflow.transitions:
            from_node = trans.from_
            to_nodes = [trans.to] if isinstance(trans.to, str) else trans.to
            if from_node not in added_nodes and from_node not in sub_workflows:
                wf.node(from_node)
                added_nodes.add(from_node)
            for to_node in to_nodes:
                if to_node not in added_nodes and to_node not in sub_workflows:
                    wf.node(to_node)
                    added_nodes.add(to_node)
            condition = eval(f"lambda ctx: {trans.condition}") if trans.condition else lambda _: True
            if len(to_nodes) > 1:
                wf.parallel(*to_nodes, condition=condition)
            else:
                wf.then(to_nodes[0], condition=condition)

        return wf

    def load_from_yaml(self, file_path: Union[str, Path]) -> None:
        """Load a workflow from a YAML file with validation."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"YAML file '{file_path}' not found")
        with file_path.open("r") as f:
            data = yaml.safe_load(f)
        try:
            self.workflow = WorkflowDefinition.model_validate(data)
        except ValidationError as e:
            raise ValueError(f"Invalid workflow YAML: {e}")

    def save_to_yaml(self, file_path: Union[str, Path]) -> None:
        """Save the workflow to a YAML file using aliases for field names."""
        file_path = Path(file_path)
        with file_path.open("w") as f:
            yaml.safe_dump(
                self.workflow.model_dump(by_alias=True),
                f,
                default_flow_style=False,
                sort_keys=False,
            )


def main():
    """Demonstrate usage of WorkflowManager."""
    manager = WorkflowManager()
    manager.add_function(
        name="greet",
        type_="embedded",
        code="def greet(user_name): return f'Hello, {user_name}!'",
    )
    manager.add_function(
        name="farewell",
        type_="embedded",
        code="def farewell(user_name): return f'Goodbye, {user_name}!'",
    )
    manager.add_node(name="start", function="greet")
    manager.add_node(name="end", function="farewell")
    manager.set_start_node("start")
    manager.add_transition(from_="start", to="end")
    manager.save_to_yaml("workflow.yaml")
    new_manager = WorkflowManager()
    new_manager.load_from_yaml("workflow.yaml")
    print(new_manager.workflow.model_dump())


if __name__ == "__main__":
    main()