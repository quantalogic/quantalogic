import importlib
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import urllib
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, Union

import yaml  # type: ignore
from loguru import logger
from pydantic import BaseModel, ValidationError

# Import directly from flow.py to avoid circular import through __init__.py
from quantalogic.flow.flow import Nodes, Workflow
from quantalogic.flow.flow_manager_schema import (
    BranchCondition,
    FunctionDefinition,
    LLMConfig,
    NodeDefinition,
    TransitionDefinition,
    WorkflowDefinition,
    WorkflowStructure,
)


class WorkflowManager:
    def __init__(self, workflow: Optional[WorkflowDefinition] = None):
        """Initialize the WorkflowManager with an optional workflow definition."""
        self.workflow = workflow or WorkflowDefinition()
        self._ensure_dependencies()

    def _ensure_dependencies(self) -> None:
        """Ensure all specified dependencies are installed or available."""
        if not self.workflow.dependencies:
            return

        for dep in self.workflow.dependencies:
            if dep.startswith("http://") or dep.startswith("https://"):
                # Remote URL: handled by import_module_from_source later
                logger.debug(f"Dependency '{dep}' is a remote URL, will be fetched during instantiation")
            elif os.path.isfile(dep):
                # Local file: handled by import_module_from_source later
                logger.debug(f"Dependency '{dep}' is a local file, will be loaded during instantiation")
            else:
                # Assume PyPI package
                try:
                    # Check if the module is already installed
                    module_name = dep.split(">")[0].split("<")[0].split("=")[0].strip()
                    importlib.import_module(module_name)
                    logger.debug(f"Dependency '{dep}' is already installed")
                except ImportError:
                    logger.info(f"Installing dependency '{dep}' via pip")
                    try:
                        subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
                        logger.debug(f"Successfully installed '{dep}'")
                    except subprocess.CalledProcessError as e:
                        raise ValueError(f"Failed to install dependency '{dep}': {e}")

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
        # Convert dict to LLMConfig if provided
        llm_config_obj = LLMConfig(**llm_config) if llm_config is not None else None
        
        node = NodeDefinition(
            function=function,
            sub_workflow=sub_workflow,
            llm_config=llm_config_obj,
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
            if t.from_node != name and (isinstance(t.to_node, str) or all(
                isinstance(tn, str) and tn != name or isinstance(tn, BranchCondition) and tn.to_node != name
                for tn in t.to_node
            ))
        ]
        if self.workflow.workflow.start == name:
            self.workflow.workflow.start = None
        if name in self.workflow.workflow.convergence_nodes:
            self.workflow.workflow.convergence_nodes.remove(name)

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
        from_node: str,
        to_node: Union[str, List[Union[str, BranchCondition]]],
        condition: Optional[str] = None,
        strict: bool = True,
    ) -> None:
        """Add a transition between nodes, supporting branching.
        
        Args:
            from_node: Source node name
            to_node: Target node name, list of target node names (for parallel), or list of BranchCondition objects (for branching)
            condition: Optional condition for simple transitions (ignored if to_node is a list of BranchCondition)
            strict: If True, validates that all nodes exist before adding the transition
        """
        if strict:
            if from_node not in self.workflow.nodes:
                raise ValueError(f"Source node '{from_node}' does not exist")
            if isinstance(to_node, str):
                if to_node not in self.workflow.nodes:
                    raise ValueError(f"Target node '{to_node}' does not exist")
            else:
                for t in to_node:
                    target = t if isinstance(t, str) else t.to_node
                    if target not in self.workflow.nodes:
                        raise ValueError(f"Target node '{target}' does not exist")
        # Create TransitionDefinition with named parameters
        transition = TransitionDefinition(
            from_node=from_node,
            to_node=to_node,
            condition=condition
        )
        self.workflow.workflow.transitions.append(transition)

    def set_start_node(self, name: str) -> None:
        """Set the start node of the workflow."""
        if name not in self.workflow.nodes:
            raise ValueError(f"Node '{name}' does not exist")
        self.workflow.workflow.start = name

    def add_convergence_node(self, name: str) -> None:
        """Add a convergence node to the workflow."""
        if name not in self.workflow.nodes:
            raise ValueError(f"Node '{name}' does not exist")
        if name not in self.workflow.workflow.convergence_nodes:
            self.workflow.workflow.convergence_nodes.append(name)
            logger.debug(f"Added convergence node '{name}'")

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

    def add_observer(self, observer_name: str) -> None:
        """Add an observer function name to the workflow."""
        if observer_name not in self.workflow.functions:
            raise ValueError(f"Observer function '{observer_name}' not defined in functions")
        if observer_name not in self.workflow.observers:
            self.workflow.observers.append(observer_name)
            logger.debug(f"Added observer '{observer_name}' to workflow")

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

    def import_module_from_source(self, source: str) -> Any:
        """
        Import a module from various sources: installed module name (e.g., PyPI), local file path, or remote URL.

        Args:
            source: The module specification (e.g., 'requests', '/path/to/file.py', 'https://example.com/module.py').

        Returns:
            The imported module object.

        Raises:
            ValueError: If the module cannot be imported, with suggestions for installation if it's a PyPI package.
        """
        if source.startswith("http://") or source.startswith("https://"):
            # Handle remote URL
            try:
                with urllib.request.urlopen(source) as response:
                    code = response.read().decode("utf-8")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as temp_file:
                    temp_file.write(code.encode("utf-8"))
                    temp_path = temp_file.name
                module_name = f"temp_module_{hash(temp_path)}"
                spec = importlib.util.spec_from_file_location(module_name, temp_path)
                if spec is None:
                    raise ValueError(f"Failed to create module spec from {temp_path}")
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                if spec.loader is None:
                    raise ValueError(f"Module spec has no loader for {temp_path}")
                spec.loader.exec_module(module)
                os.remove(temp_path)
                return module
            except Exception as e:
                raise ValueError(f"Failed to import module from URL '{source}': {e}")
        elif os.path.isfile(source):
            # Handle local file path
            try:
                module_name = f"local_module_{hash(source)}"
                spec = importlib.util.spec_from_file_location(module_name, source)
                if spec is None:
                    raise ValueError(f"Failed to create module spec from {source}")
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                if spec.loader is None:
                    raise ValueError(f"Module spec has no loader for {source}")
                spec.loader.exec_module(module)
                return module
            except Exception as e:
                raise ValueError(f"Failed to import module from file '{source}': {e}")
        else:
            # Assume installed module name from PyPI or system
            try:
                return importlib.import_module(source)
            except ImportError as e:
                logger.error(f"Module '{source}' not found: {e}")
                raise ValueError(
                    f"Failed to import module '{source}': {e}. "
                    f"This may be a PyPI package. Ensure it is installed using 'pip install {source}' "
                    "or check if the module name is correct."
                )

    def instantiate_workflow(self) -> Workflow:
        """Instantiates a Workflow object based on the definitions stored in the WorkflowManager."""
        # Ensure dependencies are available before instantiation
        self._ensure_dependencies()

        functions: Dict[str, Callable] = {}
        for func_name, func_def in self.workflow.functions.items():
            if func_def.type == "embedded":
                local_scope: Dict[str, Any] = {}
                if func_def.code is not None:
                    exec(func_def.code, local_scope)
                    if func_name not in local_scope:
                        raise ValueError(f"Embedded function '{func_name}' not defined in code")
                    functions[func_name] = local_scope[func_name]
                else:
                    raise ValueError(f"Embedded function '{func_name}' has no code")
            elif func_def.type == "external":
                try:
                    if func_def.module is None:
                        raise ValueError(f"External function '{func_name}' has no module specified")
                    module = self.import_module_from_source(func_def.module)
                    if func_def.function is None:
                        raise ValueError(f"External function '{func_name}' has no function name specified")
                    functions[func_name] = getattr(module, func_def.function)
                except (ImportError, AttributeError) as e:
                    raise ValueError(f"Failed to import external function '{func_name}': {e}")

        # Check if start node is set
        if not self.workflow.workflow.start:
            raise ValueError("Start node not set in workflow definition")
            
        # Ensure start node is a string
        start_node_name = str(self.workflow.workflow.start) if self.workflow.workflow.start else "start"
        if self.workflow.workflow.start is None:
            logger.warning("Start node was None, using 'start' as default")
        
        # Create the workflow with a valid start node
        wf = Workflow(start_node=start_node_name)

        # Register observers
        for observer_name in self.workflow.observers:
            if observer_name not in functions:
                raise ValueError(f"Observer '{observer_name}' not found in functions")
            wf.add_observer(functions[observer_name])
            logger.debug(f"Registered observer '{observer_name}' in workflow")

        sub_workflows: Dict[str, Workflow] = {}
        for node_name, node_def in self.workflow.nodes.items():
            if node_def.sub_workflow:
                # Ensure sub-workflow has a valid start node
                start_node = str(node_def.sub_workflow.start) if node_def.sub_workflow.start else f"{node_name}_start"
                if node_def.sub_workflow.start is None:
                    logger.warning(f"Sub-workflow for node '{node_name}' has no start node, using '{start_node}'")
                sub_wf = Workflow(start_node=start_node)
                sub_workflows[node_name] = sub_wf
                added_sub_nodes = set()
                for trans in node_def.sub_workflow.transitions:
                    from_node = trans.from_node
                    if from_node not in added_sub_nodes:
                        sub_wf.node(from_node)
                        added_sub_nodes.add(from_node)
                    if isinstance(trans.to_node, str):
                        to_nodes = [trans.to_node]
                        condition = eval(f"lambda ctx: {trans.condition}") if trans.condition else None
                        if to_nodes[0] not in added_sub_nodes:
                            sub_wf.node(to_nodes[0])
                            added_sub_nodes.add(to_nodes[0])
                        sub_wf.then(to_nodes[0], condition=condition)
                    elif all(isinstance(tn, str) for tn in trans.to_node):
                        to_nodes = trans.to_node
                        for to_node in to_nodes:
                            if to_node not in added_sub_nodes:
                                sub_wf.node(to_node)
                                added_sub_nodes.add(to_node)
                        sub_wf.parallel(*to_nodes)
                    else:  # List of BranchCondition
                        branches = [(tn.to_node, eval(f"lambda ctx: {tn.condition}") if tn.condition else None) 
                                  for tn in trans.to_node]
                        for to_node, _ in branches:
                            if to_node not in added_sub_nodes:
                                sub_wf.node(to_node)
                                added_sub_nodes.add(to_node)
                        sub_wf.branch(branches)
                inputs = list(Nodes.NODE_REGISTRY[sub_wf.start_node][1])
                output = node_def.output if node_def.output is not None else f"{node_name}_result"
                wf.add_sub_workflow(node_name, sub_wf, inputs={k: k for k in inputs}, output=output)
            elif node_def.function:
                if node_def.function not in functions:
                    raise ValueError(f"Function '{node_def.function}' for node '{node_name}' not found")
                func = functions[node_def.function]
                Nodes.define(
                    output=node_def.output,
                )(func)
            elif node_def.llm_config:
                llm_config = node_def.llm_config
                input_vars = set(re.findall(r"{{\s*([^}]+?)\s*}}", llm_config.prompt_template)) if not llm_config.prompt_file else set()
                cleaned_inputs = set()
                for input_var in input_vars:
                    base_var = re.split(r"\s*[\+\-\*/]\s*", input_var.strip())[0].strip()
                    if base_var.isidentifier():
                        cleaned_inputs.add(base_var)
                inputs_list: List[str] = list(cleaned_inputs)

                async def dummy_func(**kwargs):
                    pass  # Replaced by decorator logic

                if llm_config.response_model:
                    response_model = self._resolve_model(llm_config.response_model)
                    decorated_func = Nodes.structured_llm_node(
                        model=llm_config.model,
                        system_prompt=llm_config.system_prompt or "",
                        prompt_template=llm_config.prompt_template,
                        prompt_file=llm_config.prompt_file,
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
                    decorated_func = Nodes.llm_node(
                        model=llm_config.model,
                        system_prompt=llm_config.system_prompt or "",
                        prompt_template=llm_config.prompt_template,
                        prompt_file=llm_config.prompt_file,
                        output=node_def.output or f"{node_name}_result",
                        temperature=llm_config.temperature,
                        max_tokens=llm_config.max_tokens or 2000,
                        top_p=llm_config.top_p,
                        presence_penalty=llm_config.presence_penalty,
                        frequency_penalty=llm_config.frequency_penalty,
                        api_key=llm_config.api_key,
                    )(dummy_func)

                Nodes.NODE_REGISTRY[node_name] = (decorated_func, inputs_list, node_def.output or f"{node_name}_result")
                logger.debug(
                    f"Registered LLM node '{node_name}' with inputs {inputs_list} and output {node_def.output or f'{node_name}_result'}"
                )

        added_nodes = set()
        for trans in self.workflow.workflow.transitions:
            from_node = trans.from_node
            if from_node not in added_nodes and from_node not in sub_workflows:
                wf.node(from_node)
                added_nodes.add(from_node)
            if isinstance(trans.to_node, str):
                to_nodes = [trans.to_node]
                condition = eval(f"lambda ctx: {trans.condition}") if trans.condition else None
                if to_nodes[0] not in added_nodes and to_nodes[0] not in sub_workflows:
                    wf.node(to_nodes[0])
                    added_nodes.add(to_nodes[0])
                wf.then(to_nodes[0], condition=condition)
            elif all(isinstance(tn, str) for tn in trans.to_node):
                to_nodes = trans.to_node
                for to_node in to_nodes:
                    if to_node not in added_nodes and to_node not in sub_workflows:
                        wf.node(to_node)
                        added_nodes.add(to_node)
                wf.parallel(*to_nodes)
            else:  # List of BranchCondition
                branches = [(tn.to_node, eval(f"lambda ctx: {tn.condition}") if tn.condition else None) 
                          for tn in trans.to_node]
                for to_node, _ in branches:
                    if to_node not in added_nodes and to_node not in sub_workflows:
                        wf.node(to_node)
                        added_nodes.add(to_node)
                wf.branch(branches)

        # Handle convergence nodes
        for conv_node in self.workflow.workflow.convergence_nodes:
            if conv_node not in added_nodes and conv_node not in sub_workflows:
                wf.node(conv_node)
                added_nodes.add(conv_node)
            wf.converge(conv_node)

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
            self._ensure_dependencies()
        except ValidationError as e:
            raise ValueError(f"Invalid workflow YAML: {e}")

    def save_to_yaml(self, file_path: Union[str, Path]) -> None:
        """Save the workflow to a YAML file using aliases and multi-line block scalars for code."""
        file_path = Path(file_path)

        def str_representer(dumper, data):
            if "\n" in data:
                return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
            return dumper.represent_scalar("tag:yaml.org,2002:str", data)

        yaml.add_representer(str, str_representer, Dumper=yaml.SafeDumper)

        with file_path.open("w") as f:
            yaml.safe_dump(
                self.workflow.model_dump(by_alias=True),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                width=120,
            )


def main():
    """Demonstrate usage of WorkflowManager with observer, branch, and converge support."""
    manager = WorkflowManager()
    manager.workflow.dependencies = ["requests>=2.28.0"]
    manager.add_function(
        name="greet",
        type_="embedded",
        code="def greet(user_name): return f'Hello, {user_name}!'",
    )
    manager.add_function(
        name="check_condition",
        type_="embedded",
        code="def check_condition(user_name): return len(user_name) > 3",
    )
    manager.add_function(
        name="farewell",
        type_="embedded",
        code="def farewell(user_name): return f'Goodbye, {user_name}!'",
    )
    manager.add_function(
        name="monitor",
        type_="embedded",
        code="""async def monitor(event):
            print(f'[EVENT] {event.event_type.value} @ {event.node_name or "workflow"}')
            if event.result:
                print(f'Result: {event.result}')
            if event.exception:
                print(f'Error: {event.exception}')""",
    )
    manager.add_node(name="start", function="greet")
    manager.add_node(name="branch_true", function="check_condition")
    manager.add_node(name="branch_false", function="check_condition")
    manager.add_node(name="end", function="farewell")
    manager.set_start_node("start")
    manager.add_transition(
        from_node="start",
        to_node=[
            BranchCondition(to_node="branch_true", condition="ctx.get('user_name') == 'Alice'"),
            BranchCondition(to_node="branch_false", condition="ctx.get('user_name') != 'Alice'")
        ]
    )
    manager.add_convergence_node("end")
    manager.add_observer("monitor")
    manager.save_to_yaml("workflow.yaml")
    new_manager = WorkflowManager()
    new_manager.load_from_yaml("workflow.yaml")
    print(new_manager.workflow.model_dump())


if __name__ == "__main__":
    main()