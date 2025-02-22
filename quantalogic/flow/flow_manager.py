import importlib
from pathlib import Path
from typing import Callable, Dict, Optional, Union

import yaml
from pydantic import ValidationError

from quantalogic.flow import Nodes, Workflow
from quantalogic.flow.flow_manager_schema import (
    FunctionDefinition,
    NodeDefinition,
    TransitionDefinition,
    WorkflowDefinition,
)


class WorkflowManager:
    def __init__(self, workflow: Optional[WorkflowDefinition] = None):
        """Initialize the WorkflowManager with an optional workflow definition."""
        self.workflow = workflow or WorkflowDefinition()

    def add_node(
        self,
        name: str,
        function: str,
        output: Optional[str] = None,
        retries: int = 3,
        delay: float = 1.0,
        timeout: Optional[float] = None,
        parallel: bool = False,
    ) -> None:
        """Add a new node to the workflow definition."""
        node = NodeDefinition(
            function=function,
            output=output or f"{name}_result",
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
        to: Union[str, list[str]],
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

        for node_name, node_def in self.workflow.nodes.items():
            if node_def.function not in functions:
                raise ValueError(f"Function '{node_def.function}' for node '{node_name}' not found")
            func = functions[node_def.function]
            Nodes.define(
                output=node_def.output,
                retries=node_def.retries,
                delay=node_def.delay,
                timeout=node_def.timeout,
                parallel=node_def.parallel,
            )(func)

        if not self.workflow.workflow.start:
            raise ValueError("Start node not set in workflow definition")
        wf = Workflow(start=self.workflow.workflow.start)

        # Track nodes added to handle sequences and loops
        added_nodes = set()
        for trans in self.workflow.workflow.transitions:
            from_node = trans.from_
            to_nodes = [trans.to] if isinstance(trans.to, str) else trans.to
            if from_node not in added_nodes:
                wf.node(from_node)
                added_nodes.add(from_node)
            for to_node in to_nodes:
                if to_node not in added_nodes:
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
