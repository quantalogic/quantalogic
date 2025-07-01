import ast
import os

from loguru import logger

from quantalogic_flow.flow.flow_generator import generate_executable_script
from quantalogic_flow.flow.flow_manager import WorkflowManager
from quantalogic_flow.flow.flow_manager_schema import (
    BranchCondition,
    FunctionDefinition,
    NodeDefinition,
    TemplateConfig,
    TransitionDefinition,
    WorkflowDefinition,
    WorkflowStructure,
)


class WorkflowExtractor(ast.NodeVisitor):
    """
    AST visitor to extract workflow nodes and structure from a Python file.

    This class parses Python source code to identify workflow components defined with Nodes decorators
    and Workflow construction, including branch, converge, and loop patterns, building a WorkflowDefinition
    compatible with WorkflowManager. Fully supports input mappings and template nodes.
    """

    def __init__(self):
        """Initialize the extractor with empty collections for workflow components."""
        self.nodes = {}  # Maps node names to their definitions
        self.functions = {}  # Maps function names to their code
        self.transitions = []  # List of TransitionDefinition objects
        self.start_node = None  # Starting node of the workflow
        self.global_vars = {}  # Tracks global variable assignments (e.g., DEFAULT_LLM_PARAMS)
        self.observers = []  # List of observer function names
        self.convergence_nodes = []  # List of convergence nodes
        # Enhanced loop support for nested loops
        self.loop_stack = []       # Stack of active loops (supports nesting)
        self.loops = []            # List of completed LoopDefinition objects
        self.loop_definitions = {} # Maps loop IDs to definitions with nested loop IDs
        self.current_node = None   # Track current node for chaining
        self._loop_id_counter = 0  # Counter for generating unique loop IDs

    def _generate_loop_id(self):
        """Generate a unique loop ID."""
        self._loop_id_counter += 1
        return f"loop_{self._loop_id_counter}"
    
    def _get_current_loop(self):
        """Get the currently active loop (top of stack), or None if no active loops."""
        return self.loop_stack[-1] if self.loop_stack else None
    
    def _is_in_loop(self):
        """Check if we're currently inside any loop."""
        return len(self.loop_stack) > 0

    def visit_Module(self, node):
        """Log and explicitly process top-level statements in the module."""
        logger.debug(f"Visiting module with {len(node.body)} top-level statements")
        for item in node.body:
            logger.debug(f"Processing top-level node: {type(item).__name__}")
            if isinstance(item, ast.FunctionDef):
                self.visit_FunctionDef(item)
            elif isinstance(item, ast.AsyncFunctionDef):
                self.visit_AsyncFunctionDef(item)
            else:
                self.visit(item)

    def visit_Assign(self, node):
        """Detect global variable assignments and workflow assignments."""
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            var_name = node.targets[0].id
            value = node.value

            # Handle global variable assignments (e.g., MODEL, DEFAULT_LLM_PARAMS)
            if isinstance(value, ast.Dict):
                self.global_vars[var_name] = {}
                for k, v in zip(value.keys, value.values):
                    if isinstance(k, ast.Constant):
                        key = k.value
                        if isinstance(v, ast.Constant):
                            self.global_vars[var_name][key] = v.value
                        elif isinstance(v, ast.Name) and v.id in self.global_vars:
                            self.global_vars[var_name][key] = self.global_vars[v.id]
                logger.debug(
                    f"Captured global variable '{var_name}' with keys: {list(self.global_vars[var_name].keys())}"
                )

            # Handle simple constant assignments (e.g., MODEL = "gemini/gemini-2.0-flash")
            elif isinstance(value, ast.Constant):
                self.global_vars[var_name] = value.value
                logger.debug(f"Captured global constant '{var_name}' with value: {value.value}")

            # Handle workflow assignments, including parenthesized expressions
            if isinstance(value, ast.Tuple) and len(value.elts) == 1:
                value = value.elts[0]  # Unwrap single-element tuple from parentheses
            if isinstance(value, ast.Call):
                self.process_workflow_expr(value, var_name)

        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        """Extract node information from synchronous function definitions."""
        logger.debug(f"Visiting synchronous function definition: '{node.name}'")
        for decorator in node.decorator_list:
            decorator_name = None
            kwargs = {}
            logger.debug(f"Examining decorator for '{node.name}': {ast.dump(decorator)}")

            if (
                isinstance(decorator, ast.Attribute)
                and isinstance(decorator.value, ast.Name)
                and decorator.value.id == "Nodes"
            ):
                decorator_name = decorator.attr
                logger.debug(f"Found simple decorator 'Nodes.{decorator_name}' for '{node.name}'")

            elif (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "Nodes"
            ):
                decorator_name = decorator.func.attr
                logger.debug(f"Found call decorator 'Nodes.{decorator_name}' for '{node.name}'")
                for kw in decorator.keywords:
                    if kw.arg is None and isinstance(kw.value, ast.Name):  # Handle **kwargs
                        var_name = kw.value.id
                        if var_name in self.global_vars:
                            kwargs.update(self.global_vars[var_name])
                            logger.debug(f"Unpacked '{var_name}' into kwargs: {self.global_vars[var_name]}")
                    elif isinstance(kw.value, ast.Constant):
                        kwargs[kw.arg] = kw.value.value
                    elif isinstance(kw.value, ast.Name):
                        # Handle variable references (e.g., model=MODEL_NAME)  
                        var_name = kw.value.id
                        if var_name in self.global_vars:
                            kwargs[kw.arg] = self.global_vars[var_name]
                            logger.debug(f"Resolved variable '{var_name}' to value '{self.global_vars[var_name]}' for '{kw.arg}'")
                        elif kw.arg == "response_model":
                            kwargs[kw.arg] = ast.unparse(kw.value)
                        else:
                            kwargs[kw.arg] = var_name  # Keep as variable name if not in global_vars
                    elif kw.arg == "response_model" and isinstance(kw.value, ast.Name):
                        kwargs[kw.arg] = ast.unparse(kw.value)
                    elif kw.arg == "transformer" and isinstance(kw.value, ast.Lambda):
                        kwargs[kw.arg] = ast.unparse(kw.value)
                    elif kw.arg == "response_model":
                        # Handle complex response model expressions (e.g., List[str], custom types)
                        kwargs[kw.arg] = ast.unparse(kw.value)
                    else:
                        # Handle any other complex expressions by unparsing them
                        if not isinstance(kw.value, (ast.Constant, ast.Name)):
                            kwargs[kw.arg] = ast.unparse(kw.value)

            if decorator_name:
                func_name = node.name
                inputs = [arg.arg for arg in node.args.args]

                if decorator_name == "define":
                    output = kwargs.get("output")
                    self.nodes[func_name] = {
                        "type": "function",
                        "function": func_name,
                        "inputs": inputs,
                        "output": output,
                    }
                    logger.debug(f"Registered function node '{func_name}' with output '{output}'")
                elif decorator_name == "llm_node":
                    llm_config = {
                        key: value
                        for key, value in kwargs.items()
                        if key in [
                            "model",
                            "system_prompt",
                            "system_prompt_file",
                            "prompt_template",
                            "prompt_file",
                            "temperature",
                            "max_tokens",
                            "top_p",
                            "presence_penalty",
                            "frequency_penalty",
                            "output",
                        ]
                    }
                    self.nodes[func_name] = {
                        "type": "llm",
                        "llm_config": llm_config,
                        "inputs": inputs,
                        "output": llm_config.get("output"),
                    }
                    logger.debug(f"Registered LLM node '{func_name}' with model '{llm_config.get('model')}'")
                elif decorator_name == "validate_node":
                    output = kwargs.get("output")
                    self.nodes[func_name] = {
                        "type": "function",
                        "function": func_name,
                        "inputs": inputs,
                        "output": output,
                    }
                    logger.debug(f"Registered validate node '{func_name}' with output '{output}'")
                elif decorator_name == "structured_llm_node":
                    llm_config = {
                        key: value
                        for key, value in kwargs.items()
                        if key in [
                            "model",
                            "system_prompt",
                            "system_prompt_file",
                            "prompt_template",
                            "prompt_file",
                            "temperature",
                            "max_tokens",
                            "top_p",
                            "presence_penalty",
                            "frequency_penalty",
                            "output",
                            "response_model",
                        ]
                    }
                    self.nodes[func_name] = {
                        "type": "structured_llm",
                        "llm_config": llm_config,
                        "inputs": inputs,
                        "output": llm_config.get("output"),
                    }
                    logger.debug(f"Registered structured LLM node '{func_name}' with model '{llm_config.get('model')}'")
                elif decorator_name == "template_node":
                    template_config = {
                        "template": kwargs.get("template", ""),
                        "template_file": kwargs.get("template_file"),
                    }
                    if "rendered_content" not in inputs:
                        inputs.insert(0, "rendered_content")
                    self.nodes[func_name] = {
                        "type": "template",
                        "template_config": template_config,
                        "inputs": inputs,
                        "output": kwargs.get("output"),
                    }
                    logger.debug(f"Registered template node '{func_name}' with config: {template_config}")
                elif decorator_name == "transform_node":
                    output = kwargs.get("output")
                    self.nodes[func_name] = {
                        "type": "function",
                        "function": func_name,
                        "inputs": inputs,
                        "output": output,
                    }
                    logger.debug(f"Registered transform node '{func_name}' with output '{output}'")
                else:
                    logger.warning(f"Unsupported decorator 'Nodes.{decorator_name}' in function '{func_name}'")

                func_code = ast.unparse(node)
                self.functions[func_name] = {
                    "type": "embedded",
                    "code": func_code,
                }
            else:
                logger.debug(f"No recognized 'Nodes' decorator found for '{node.name}'")

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        """Extract node information from asynchronous function definitions."""
        logger.debug(f"Visiting asynchronous function definition: '{node.name}'")
        for decorator in node.decorator_list:
            decorator_name = None
            kwargs = {}
            logger.debug(f"Examining decorator for '{node.name}': {ast.dump(decorator)}")

            if (
                isinstance(decorator, ast.Attribute)
                and isinstance(decorator.value, ast.Name)
                and decorator.value.id == "Nodes"
            ):
                decorator_name = decorator.attr
                logger.debug(f"Found simple decorator 'Nodes.{decorator_name}' for '{node.name}'")

            elif (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "Nodes"
            ):
                decorator_name = decorator.func.attr
                logger.debug(f"Found call decorator 'Nodes.{decorator_name}' for '{node.name}'")
                for kw in decorator.keywords:
                    if kw.arg is None and isinstance(kw.value, ast.Name):  # Handle **kwargs
                        var_name = kw.value.id
                        if var_name in self.global_vars:
                            kwargs.update(self.global_vars[var_name])
                            logger.debug(f"Unpacked '{var_name}' into kwargs: {self.global_vars[var_name]}")
                    elif isinstance(kw.value, ast.Constant):
                        kwargs[kw.arg] = kw.value.value
                    elif isinstance(kw.value, ast.Name):
                        # Handle variable references (e.g., model=MODEL_NAME)  
                        var_name = kw.value.id
                        if var_name in self.global_vars:
                            kwargs[kw.arg] = self.global_vars[var_name]
                            logger.debug(f"Resolved variable '{var_name}' to value '{self.global_vars[var_name]}' for '{kw.arg}'")
                        elif kw.arg == "response_model":
                            kwargs[kw.arg] = ast.unparse(kw.value)
                        else:
                            kwargs[kw.arg] = var_name  # Keep as variable name if not in global_vars
                    elif kw.arg == "response_model" and isinstance(kw.value, ast.Name):
                        kwargs[kw.arg] = ast.unparse(kw.value)
                    elif kw.arg == "transformer" and isinstance(kw.value, ast.Lambda):
                        kwargs[kw.arg] = ast.unparse(kw.value)
                    elif kw.arg == "response_model":
                        # Handle complex response model expressions (e.g., List[str], custom types)
                        kwargs[kw.arg] = ast.unparse(kw.value)
                    else:
                        # Handle any other complex expressions by unparsing them
                        if not isinstance(kw.value, (ast.Constant, ast.Name)):
                            kwargs[kw.arg] = ast.unparse(kw.value)

            if decorator_name:
                func_name = node.name
                inputs = [arg.arg for arg in node.args.args]

                if decorator_name == "define":
                    output = kwargs.get("output")
                    self.nodes[func_name] = {
                        "type": "function",
                        "function": func_name,
                        "inputs": inputs,
                        "output": output,
                    }
                    logger.debug(f"Registered function node '{func_name}' with output '{output}'")
                elif decorator_name == "llm_node":
                    llm_config = {
                        key: value
                        for key, value in kwargs.items()
                        if key in [
                            "model",
                            "system_prompt",
                            "system_prompt_file",
                            "prompt_template",
                            "prompt_file",
                            "temperature",
                            "max_tokens",
                            "top_p",
                            "presence_penalty",
                            "frequency_penalty",
                            "output",
                        ]
                    }
                    self.nodes[func_name] = {
                        "type": "llm",
                        "llm_config": llm_config,
                        "inputs": inputs,
                        "output": llm_config.get("output"),
                    }
                    logger.debug(f"Registered LLM node '{func_name}' with model '{llm_config.get('model')}'")
                elif decorator_name == "validate_node":
                    output = kwargs.get("output")
                    self.nodes[func_name] = {
                        "type": "function",
                        "function": func_name,
                        "inputs": inputs,
                        "output": output,
                    }
                    logger.debug(f"Registered validate node '{func_name}' with output '{output}'")
                elif decorator_name == "structured_llm_node":
                    llm_config = {
                        key: value
                        for key, value in kwargs.items()
                        if key in [
                            "model",
                            "system_prompt",
                            "system_prompt_file",
                            "prompt_template",
                            "prompt_file",
                            "temperature",
                            "max_tokens",
                            "top_p",
                            "presence_penalty",
                            "frequency_penalty",
                            "output",
                            "response_model",
                        ]
                    }
                    self.nodes[func_name] = {
                        "type": "structured_llm",
                        "llm_config": llm_config,
                        "inputs": inputs,
                        "output": llm_config.get("output"),
                    }
                    logger.debug(f"Registered structured LLM node '{func_name}' with model '{llm_config.get('model')}'")
                elif decorator_name == "template_node":
                    template_config = {
                        "template": kwargs.get("template", ""),
                        "template_file": kwargs.get("template_file"),
                    }
                    if "rendered_content" not in inputs:
                        inputs.insert(0, "rendered_content")
                    self.nodes[func_name] = {
                        "type": "template",
                        "template_config": template_config,
                        "inputs": inputs,
                        "output": kwargs.get("output"),
                    }
                    logger.debug(f"Registered template node '{func_name}' with config: {template_config}")
                elif decorator_name == "transform_node":
                    output = kwargs.get("output")
                    self.nodes[func_name] = {
                        "type": "function",
                        "function": func_name,
                        "inputs": inputs,
                        "output": output,
                    }
                    logger.debug(f"Registered transform node '{func_name}' with output '{output}'")
                else:
                    logger.warning(f"Unsupported decorator 'Nodes.{decorator_name}' in function '{func_name}'")

                func_code = ast.unparse(node)
                self.functions[func_name] = {
                    "type": "embedded",
                    "code": func_code,
                }
            else:
                logger.debug(f"No recognized 'Nodes' decorator found for '{node.name}'")

        self.generic_visit(node)

    def visit_Expr(self, node):
        """Handle expression statements, particularly workflow method calls."""
        if isinstance(node.value, ast.Call):
            # Check if this is a workflow method call
            if isinstance(node.value.func, ast.Attribute):
                # Look for calls like workflow.then(), workflow.parallel(), etc.
                attr_name = node.value.func.attr
                if attr_name in ["start", "then", "parallel", "branch", "converge", "add_observer", "node", "start_loop", "end_loop"]:
                    # Find the workflow variable name by checking if the object is a Name node
                    if isinstance(node.value.func.value, ast.Name):
                        workflow_var = node.value.func.value.id
                        logger.debug(f"Processing workflow method call: {workflow_var}.{attr_name}()")
                        # Process the method call as part of the workflow
                        self.process_workflow_method_call(node.value, workflow_var)
        
        self.generic_visit(node)

    def process_workflow_method_call(self, call_node, workflow_var):
        """Process individual workflow method calls like workflow.then(), etc."""
        method_name = call_node.func.attr
        
        if method_name == "start":
            start_node = call_node.args[0].value if call_node.args else None
            if start_node:
                self.start_node = start_node
                self.current_node = start_node  # Initialize current node for chaining
                logger.debug(f"Workflow start node set to '{start_node}' for workflow variable '{workflow_var}'")
        
        elif method_name == "then":
            next_node = call_node.args[0].value if call_node.args else None
            condition = None
            for keyword in call_node.keywords:
                if keyword.arg == "condition" and keyword.value:
                    condition = ast.unparse(keyword.value)
            
            # Use current_node if available, otherwise use start_node
            from_node = self.current_node if self.current_node else self.start_node
            if from_node and next_node:
                self.transitions.append(TransitionDefinition(
                    from_node=from_node, 
                    to_node=next_node, 
                    condition=condition
                ))
                logger.debug(f"Added transition: {from_node} -> {next_node} (condition: {condition})")
                # Update the current node for chaining (but keep start_node intact)
                self.current_node = next_node
                
                # Add node to all active loops if inside any loop
                if self._is_in_loop() and next_node:
                    for loop_data in self.loop_stack:
                        if next_node not in loop_data["nodes"]:
                            loop_data["nodes"].append(next_node)
                    logger.debug(f"Added '{next_node}' to active loops")
        
        elif method_name == "parallel":
            to_nodes = [arg.value for arg in call_node.args]
            from_node = self.current_node if self.current_node else self.start_node
            if from_node and to_nodes:
                self.transitions.append(TransitionDefinition(
                    from_node=from_node, 
                    to_node=to_nodes
                ))
                logger.debug(f"Added parallel transition: {from_node} -> {to_nodes}")
        
        elif method_name == "branch":
            # Handle branch with conditions
            if call_node.args and isinstance(call_node.args[0], ast.List):
                branches = []
                for branch_tuple in call_node.args[0].elts:
                    if isinstance(branch_tuple, ast.Tuple) and len(branch_tuple.elts) >= 2:
                        target_node = branch_tuple.elts[0].value if isinstance(branch_tuple.elts[0], ast.Constant) else None
                        condition = ast.unparse(branch_tuple.elts[1]) if len(branch_tuple.elts) > 1 else None
                        if target_node:
                            branches.append((target_node, condition))
                
                if self.current_node and branches:
                    for target_node, condition in branches:
                        self.transitions.append(TransitionDefinition(
                            from_node=self.current_node,
                            to_node=target_node,
                            condition=condition
                        ))
                        logger.debug(f"Added branch transition: {self.current_node} -> {target_node} (condition: {condition})")
                        
                        # Add branch target nodes to all active loops
                        if self._is_in_loop() and target_node:
                            for loop_data in self.loop_stack:
                                if target_node not in loop_data["nodes"]:
                                    loop_data["nodes"].append(target_node)
                            logger.debug(f"Added '{target_node}' to active loops")
        
        elif method_name == "converge":
            converge_node = call_node.args[0].value if call_node.args else None
            if converge_node:
                self.convergence_nodes.append(converge_node)
                logger.debug(f"Added convergence node: {converge_node}")
                
                # Add convergence node to all active loops
                if self._is_in_loop() and converge_node:
                    for loop_data in self.loop_stack:
                        if converge_node not in loop_data["nodes"]:
                            loop_data["nodes"].append(converge_node)
                    logger.debug(f"Added convergence node '{converge_node}' to active loops")
        
        elif method_name == "add_observer":
            observer = None
            if call_node.args:
                if isinstance(call_node.args[0], ast.Name):
                    observer = call_node.args[0].id
                elif isinstance(call_node.args[0], ast.Constant):
                    observer = call_node.args[0].value
            
            if observer:
                self.observers.append(observer)
                logger.debug(f"Added observer: {observer}")
        
        elif method_name == "node":
            node_name = call_node.args[0].value if call_node.args else None
            inputs_mapping = {}
            
            for keyword in call_node.keywords:
                if keyword.arg == "inputs_mapping" and isinstance(keyword.value, ast.Dict):
                    for k, v in zip(keyword.value.keys, keyword.value.values):
                        if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                            inputs_mapping[k.value] = v.value
            
            if node_name:
                self.nodes[node_name] = {
                    "type": "workflow_node",
                    "inputs_mapping": inputs_mapping
                }
                logger.debug(f"Added workflow node: {node_name} with inputs_mapping: {inputs_mapping}")
        
        elif method_name == "start_loop":
            from_node = self.current_node if self.current_node else self.start_node
            if from_node is None:
                logger.warning(f"start_loop called without a previous node in '{workflow_var}'")
                return
            
            # Generate unique loop ID
            loop_id = self._generate_loop_id()
            
            # Create loop data structure for tracking
            loop_data = {
                "loop_id": loop_id,
                "entry_node": from_node,
                "nodes": [],
                "condition": None,
                "exit_node": None,
                "nested_loops": []
            }
            
            # If we're already in a loop, this is a nested loop
            parent_loop = self._get_current_loop()
            if parent_loop:
                parent_loop["nested_loops"].append(loop_id)
                logger.debug(f"Started nested loop '{loop_id}' inside loop '{parent_loop['loop_id']}'")
            else:
                logger.debug(f"Started top-level loop '{loop_id}' after node '{from_node}'")
            
            # Push to loop stack
            self.loop_stack.append(loop_data)
        
        elif method_name == "end_loop":
            if not self._is_in_loop():
                logger.warning(f"end_loop called but no active loop in '{workflow_var}'")
                return
            
            # Get condition and next_node from arguments
            cond = None
            next_node = None
            for keyword in call_node.keywords:
                if keyword.arg == "condition":
                    # If condition is a string literal, extract the string value
                    if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                        cond = keyword.value.value
                    else:
                        cond = ast.unparse(keyword.value)
                elif keyword.arg == "next_node":
                    next_node = (keyword.value.value 
                               if isinstance(keyword.value, ast.Constant) 
                               else ast.unparse(keyword.value))
            
            if not cond or not next_node:
                logger.warning(f"end_loop in '{workflow_var}' missing condition or next_node")
                return
            
            # Pop the current loop from stack
            current_loop = self.loop_stack.pop()
            loop_nodes = current_loop["nodes"]
            
            # Update loop data with exit information
            current_loop["condition"] = cond
            current_loop["exit_node"] = next_node
            
            if loop_nodes:
                first_loop_node = loop_nodes[0]
                last_loop_node = loop_nodes[-1]
                
                # Create loop-back transition: last node to first node when condition is false
                negated_cond = f"not ({cond})"
                self.transitions.append(
                    TransitionDefinition(
                        from_node=last_loop_node,
                        to_node=first_loop_node,
                        condition=negated_cond
                    )
                )
                
                # Create exit transition: last node to next_node when condition is true
                self.transitions.append(
                    TransitionDefinition(
                        from_node=last_loop_node,
                        to_node=next_node,
                        condition=cond
                    )
                )
                
                logger.debug(f"Added loop transitions for '{current_loop['loop_id']}' to '{next_node}': "
                           f"'{last_loop_node}' -> '{first_loop_node}' (not {cond}), "
                           f"'{last_loop_node}' -> '{next_node}' ({cond})")
            
            # Create LoopDefinition and add to completed loops
            from quantalogic_flow.flow.flow_manager_schema import LoopDefinition
            loop_def = LoopDefinition(
                loop_id=current_loop["loop_id"],
                entry_node=current_loop["entry_node"],
                nodes=loop_nodes,
                condition=cond,
                exit_node=next_node,
                nested_loops=[]  # Will be populated later when all loops are processed
            )
            
            # Store loop with its nested loop IDs for later resolution
            self.loop_definitions[current_loop["loop_id"]] = {
                "definition": loop_def,
                "nested_loop_ids": current_loop["nested_loops"]
            }
            
            # Also add to completed loops list for immediate access
            self.loops.append(loop_def)
            
            logger.debug(f"Created LoopDefinition for '{current_loop['loop_id']}' with {len(loop_nodes)} nodes")
            
            # Update current node
            self.current_node = next_node

            logger.debug(f"Ended loop '{current_loop['loop_id']}' and transitioned to '{next_node}'")

        else:
            logger.warning(f"Unsupported Workflow method '{method_name}' in variable '{workflow_var}'")
        return None

    def process_workflow_expr(self, expr, var_name):
        """
        Recursively process Workflow method chaining to build transitions, structure, and observers.

        Args:
            expr: The AST expression to process.
            var_name: The variable name to which the workflow is assigned (for logging/context).

        Returns:
            str or None: The current node name or None if no specific node is returned.
        """
        if not isinstance(expr, ast.Call):
            logger.debug(f"Skipping non-Call node in workflow processing for '{var_name}'")
            return None

        func = expr.func
        logger.debug(f"Processing Call node with func type: {type(func).__name__} for '{var_name}'")

        if isinstance(func, ast.Name) and func.id == "Workflow":
            self.start_node = expr.args[0].value if expr.args else None
            self.current_node = self.start_node  # Initialize current node
            logger.debug(f"Workflow start node set to '{self.start_node}' for variable '{var_name}'")
            return self.start_node
        elif isinstance(func, ast.Attribute):
            method_name = func.attr
            obj = func.value
            previous_node = self.process_workflow_expr(obj, var_name)

            if method_name == "start":
                start_node = expr.args[0].value if expr.args else None
                if start_node:
                    self.start_node = start_node
                    self.current_node = start_node  # Initialize current node for chaining
                    logger.debug(f"Workflow start node set to '{start_node}' for variable '{var_name}'")
                return start_node

            elif method_name == "then":
                next_node = expr.args[0].value if expr.args else None
                condition = None
                for keyword in expr.keywords:
                    if keyword.arg == "condition" and keyword.value:
                        condition = ast.unparse(keyword.value)
                if previous_node and next_node:
                    self.transitions.append(TransitionDefinition(from_node=previous_node, to_node=next_node, condition=condition))
                    logger.debug(f"Added transition: {previous_node} -> {next_node} (condition: {condition})")
                    
                    # Add node to all active loops if inside any loop
                    if self._is_in_loop() and next_node:
                        for loop_data in self.loop_stack:
                            if next_node not in loop_data["nodes"]:
                                loop_data["nodes"].append(next_node)
                        logger.debug(f"Added '{next_node}' to active loops")
                return next_node

            elif method_name == "sequence":
                nodes = [arg.value for arg in expr.args]
                if previous_node and nodes:
                    self.transitions.append(TransitionDefinition(from_node=previous_node, to_node=nodes[0]))
                    logger.debug(f"Added sequence start transition: {previous_node} -> {nodes[0]}")
                for i in range(len(nodes) - 1):
                    self.transitions.append(TransitionDefinition(from_node=nodes[i], to_node=nodes[i + 1]))
                    logger.debug(f"Added sequence transition: {nodes[i]} -> {nodes[i + 1]}")
                    
                # Add sequence nodes to all active loops if inside any loop
                if self._is_in_loop():
                    for loop_data in self.loop_stack:
                        for node in nodes:
                            if node not in loop_data["nodes"]:
                                loop_data["nodes"].append(node)
                    logger.debug(f"Added sequence nodes {nodes} to active loops")
                return nodes[-1] if nodes else previous_node

            elif method_name == "parallel":
                to_nodes = [arg.value for arg in expr.args]
                if previous_node:
                    self.transitions.append(TransitionDefinition(from_node=previous_node, to_node=to_nodes))
                    logger.debug(f"Added parallel transition: {previous_node} -> {to_nodes}")
                    
                    # Add parallel nodes to all active loops if inside any loop
                    if self._is_in_loop():
                        for loop_data in self.loop_stack:
                            for node in to_nodes:
                                if node not in loop_data["nodes"]:
                                    loop_data["nodes"].append(node)
                        logger.debug(f"Added parallel nodes {to_nodes} to active loops")
                return None

            elif method_name == "branch":
                branches = []
                if expr.args and isinstance(expr.args[0], ast.List):
                    for elt in expr.args[0].elts:
                        if isinstance(elt, ast.Tuple) and len(elt.elts) == 2:
                            to_node = elt.elts[0].value
                            cond = ast.unparse(elt.elts[1]) if elt.elts[1] else None
                            branches.append(BranchCondition(to_node=to_node, condition=cond))
                            logger.debug(f"Added branch: {previous_node} -> {to_node} (condition: {cond})")
                if previous_node and branches:
                    self.transitions.append(TransitionDefinition(from_node=previous_node, to_node=branches))
                    
                    # Add branch nodes to all active loops if inside any loop
                    if self._is_in_loop():
                        for loop_data in self.loop_stack:
                            for branch in branches:
                                if branch.to_node not in loop_data["nodes"]:
                                    loop_data["nodes"].append(branch.to_node)
                        logger.debug("Added branch nodes to active loops")
                return None

            elif method_name == "converge":
                conv_node = expr.args[0].value if expr.args else None
                if conv_node and conv_node not in self.convergence_nodes:
                    self.convergence_nodes.append(conv_node)
                    logger.debug(f"Added convergence node: {conv_node}")
                    
                    # Add convergence node to all active loops if inside any loop
                    if self._is_in_loop() and conv_node:
                        for loop_data in self.loop_stack:
                            if conv_node not in loop_data["nodes"]:
                                loop_data["nodes"].append(conv_node)
                        logger.debug(f"Added convergence node '{conv_node}' to active loops")
                return conv_node

            elif method_name == "node":
                node_name = expr.args[0].value if expr.args else None
                inputs_mapping = None
                for keyword in expr.keywords:
                    if keyword.arg == "inputs_mapping" and isinstance(keyword.value, ast.Dict):
                        inputs_mapping = {}
                        for k, v in zip(keyword.value.keys, keyword.value.values):
                            key = k.value if isinstance(k, ast.Constant) else ast.unparse(k)
                            if isinstance(v, ast.Constant):
                                inputs_mapping[key] = v.value
                            elif isinstance(v, ast.Lambda):
                                inputs_mapping[key] = f"lambda ctx: {ast.unparse(v.body)}"
                            else:
                                inputs_mapping[key] = ast.unparse(v)
                if node_name:
                    if node_name in self.nodes and inputs_mapping:
                        self.nodes[node_name]["inputs_mapping"] = inputs_mapping
                        logger.debug(f"Added inputs_mapping to node '{node_name}': {inputs_mapping}")
                    if previous_node:
                        self.transitions.append(TransitionDefinition(from_node=previous_node, to_node=node_name))
                        logger.debug(f"Added node transition: {previous_node} -> {node_name}")
                    
                    # Add node to all active loops if inside any loop
                    if self._is_in_loop() and node_name:
                        for loop_data in self.loop_stack:
                            if node_name not in loop_data["nodes"]:
                                loop_data["nodes"].append(node_name)
                        logger.debug(f"Added '{node_name}' to active loops in '{var_name}'")
                return node_name

            elif method_name == "add_sub_workflow":
                sub_wf_name = expr.args[0].value if expr.args else None
                sub_wf_obj = expr.args[1] if len(expr.args) > 1 else None
                inputs = {}
                inputs_mapping = None
                output = None
                if len(expr.args) > 2 and isinstance(expr.args[2], ast.Dict):
                    inputs_mapping = {}
                    for k, v in zip(expr.args[2].keys, expr.args[2].values):
                        key = k.value if isinstance(k, ast.Constant) else ast.unparse(k)
                        if isinstance(v, ast.Constant):
                            inputs_mapping[key] = v.value
                        elif isinstance(v, ast.Lambda):
                            inputs_mapping[key] = f"lambda ctx: {ast.unparse(v.body)}"
                        else:
                            inputs_mapping[key] = ast.unparse(v)
                    inputs = list(inputs_mapping.keys())
                if len(expr.args) > 3:
                    output = expr.args[3].value
                if sub_wf_name and sub_wf_obj:
                    sub_extractor = WorkflowExtractor()
                    sub_extractor.process_workflow_expr(sub_wf_obj, f"{var_name}_{sub_wf_name}")
                    self.nodes[sub_wf_name] = {
                        "type": "sub_workflow",
                        "sub_workflow": WorkflowStructure(
                            start=sub_extractor.start_node,
                            transitions=sub_extractor.transitions,
                            convergence_nodes=sub_extractor.convergence_nodes,
                        ),
                        "inputs": inputs,
                        "inputs_mapping": inputs_mapping,
                        "output": output,
                    }
                    self.observers.extend(sub_extractor.observers)
                    logger.debug(f"Added sub-workflow node '{sub_wf_name}' with start '{sub_extractor.start_node}' and inputs_mapping: {inputs_mapping}")
                    if previous_node:
                        self.transitions.append(TransitionDefinition(from_node=previous_node, to_node=sub_wf_name))
                return sub_wf_name

            elif method_name == "add_observer":
                if expr.args and isinstance(expr.args[0], (ast.Name, ast.Constant)):
                    observer_name = expr.args[0].id if isinstance(expr.args[0], ast.Name) else expr.args[0].value
                    if observer_name not in self.observers:
                        self.observers.append(observer_name)
                        logger.debug(f"Added observer '{observer_name}' to workflow '{var_name}'")
                else:
                    logger.warning(f"Unsupported observer argument in 'add_observer' for '{var_name}'")
                return previous_node

            elif method_name == "start_loop":
                if previous_node is None:
                    logger.warning(f"start_loop called without a previous node in '{var_name}'")
                    return None
                
                # Generate unique loop ID
                loop_id = self._generate_loop_id()
                
                # Create loop data structure for tracking
                loop_data = {
                    "loop_id": loop_id,
                    "entry_node": previous_node,
                    "nodes": [],
                    "condition": None,
                    "exit_node": None,
                    "nested_loops": []
                }
                
                # If we're already in a loop, this is a nested loop
                parent_loop = self._get_current_loop()
                if parent_loop:
                    parent_loop["nested_loops"].append(loop_id)
                    logger.debug(f"Started nested loop '{loop_id}' inside loop '{parent_loop['loop_id']}'")
                else:
                    logger.debug(f"Started top-level loop '{loop_id}' after node '{previous_node}'")
                
                # Push to loop stack
                self.loop_stack.append(loop_data)
                return previous_node

            elif method_name == "end_loop":
                if not self._is_in_loop():
                    logger.warning(f"end_loop called but no active loop in '{var_name}'")
                    return None
                
                # Get condition and next_node from arguments and keywords
                cond = None
                next_node = None
                
                # Check if first argument is the next_node
                if expr.args:
                    if isinstance(expr.args[0], ast.Constant):
                        next_node = expr.args[0].value
                    else:
                        next_node = ast.unparse(expr.args[0])
                
                for keyword in expr.keywords:
                    if keyword.arg in ["condition", "exit_condition"]:
                        # If condition is a string literal, extract the string value
                        if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                            cond = keyword.value.value
                        else:
                            cond = ast.unparse(keyword.value)
                    elif keyword.arg == "next_node":
                        next_node = (keyword.value.value 
                                   if isinstance(keyword.value, ast.Constant) 
                                   else ast.unparse(keyword.value))
                
                # If no explicit condition, use a default condition to end the loop
                if not cond and next_node:
                    cond = "True"  # Default exit condition
                
                if not next_node:
                    logger.warning(f"end_loop in '{var_name}' missing next_node")
                    return None
                
                # Pop the current loop from stack
                current_loop = self.loop_stack.pop()
                loop_nodes = current_loop["nodes"]
                
                # Update loop data with exit information
                current_loop["condition"] = cond
                current_loop["exit_node"] = next_node
                
                if loop_nodes:
                    first_loop_node = loop_nodes[0]
                    last_loop_node = loop_nodes[-1]
                    
                    # Create loop-back transition: last node to first node when condition is false
                    negated_cond = f"not ({cond})"
                    self.transitions.append(
                        TransitionDefinition(
                            from_node=last_loop_node,
                            to_node=first_loop_node,
                            condition=negated_cond
                        )
                    )
                    
                    # Create exit transition: last node to next_node when condition is true
                    self.transitions.append(
                        TransitionDefinition(
                            from_node=last_loop_node,
                            to_node=next_node,
                            condition=cond
                        )
                    )
                    
                    logger.debug(f"Added loop transitions for '{current_loop['loop_id']}' to '{next_node}': "
                               f"'{last_loop_node}' -> '{first_loop_node}' (not {cond}), "
                               f"'{last_loop_node}' -> '{next_node}' ({cond})")
                
                # Create LoopDefinition and add to completed loops
                from quantalogic_flow.flow.flow_manager_schema import LoopDefinition
                loop_def = LoopDefinition(
                    loop_id=current_loop["loop_id"],
                    entry_node=current_loop["entry_node"],
                    nodes=loop_nodes,
                    condition=cond,
                    exit_node=next_node,
                    nested_loops=[]  # Will be populated later when all loops are processed
                )
                
                # Store loop with its nested loop IDs for later resolution
                self.loop_definitions[current_loop["loop_id"]] = {
                    "definition": loop_def,
                    "nested_loop_ids": current_loop["nested_loops"]
                }
                
                # Also add to completed loops list for immediate access
                self.loops.append(loop_def)
                
                logger.debug(f"Created LoopDefinition for '{current_loop['loop_id']}' with {len(loop_nodes)} nodes")
                
                return next_node

            else:
                logger.warning(f"Unsupported Workflow method '{method_name}' in variable '{var_name}'")
        return None

    def _resolve_nested_loops(self):
        """
        Resolve nested loop structure by replacing string IDs with actual LoopDefinition objects.
        This should be called after all loops have been processed.
        """
        # First pass: collect all top-level loops (loops with no parent)
        all_loop_ids = set(self.loop_definitions.keys())
        nested_loop_ids = set()
        
        # Collect all nested loop IDs
        for loop_data in self.loop_definitions.values():
            nested_loop_ids.update(loop_data["nested_loop_ids"])
        
        # Top-level loops are those not referenced as nested loops
        top_level_loop_ids = all_loop_ids - nested_loop_ids
        
        # Recursively build nested structure
        def build_nested_structure(loop_id):
            loop_data = self.loop_definitions[loop_id]
            loop_def = loop_data["definition"]
            
            # Resolve nested loops recursively
            nested_loops = []
            for nested_id in loop_data["nested_loop_ids"]:
                if nested_id in self.loop_definitions:
                    nested_loop_def = build_nested_structure(nested_id)
                    nested_loops.append(nested_loop_def)
            
            # Update the nested_loops field
            loop_def.nested_loops = nested_loops
            return loop_def
        
        # Build the final list of loops (only top-level loops, with nesting resolved)
        resolved_loops = []
        for loop_id in top_level_loop_ids:
            resolved_loops.append(build_nested_structure(loop_id))
        
        return resolved_loops

def extract_workflow_from_file(file_path):
    """
    Extract a WorkflowDefinition and global variables from a Python file containing a workflow.

    Args:
        file_path (str): Path to the Python file to parse.

    Returns:
        tuple: (WorkflowDefinition, Dict[str, Any]) - The workflow definition and captured global variables.
    """
    with open(file_path) as f:
        source = f.read()
    tree = ast.parse(source)

    extractor = WorkflowExtractor()
    extractor.visit(tree)
    
    # Resolve nested loop structure
    resolved_loops = extractor._resolve_nested_loops()

    functions = {name: FunctionDefinition(**func) for name, func in extractor.functions.items()}

    nodes = {}
    from quantalogic_flow.flow.flow_manager_schema import LLMConfig

    for name, node_info in extractor.nodes.items():
        if node_info["type"] == "function":
            nodes[name] = NodeDefinition(
                function=node_info["function"],
                inputs_mapping=node_info.get("inputs_mapping"),
                output=node_info["output"],
                retries=3,
                delay=1.0,
                timeout=None,
                parallel=False,
            )
        elif node_info["type"] == "llm":
            llm_config = LLMConfig(**node_info["llm_config"])
            nodes[name] = NodeDefinition(
                llm_config=llm_config,
                inputs_mapping=node_info.get("inputs_mapping"),
                output=node_info["output"],
                retries=3,
                delay=1.0,
                timeout=None,
                parallel=False,
            )
        elif node_info["type"] == "structured_llm":
            llm_config = LLMConfig(**node_info["llm_config"])
            nodes[name] = NodeDefinition(
                llm_config=llm_config,
                inputs_mapping=node_info.get("inputs_mapping"),
                output=node_info["output"],
                retries=3,
                delay=1.0,
                timeout=None,
                parallel=False,
            )
        elif node_info["type"] == "template":
            template_config = TemplateConfig(**node_info["template_config"])
            nodes[name] = NodeDefinition(
                template_config=template_config,
                inputs_mapping=node_info.get("inputs_mapping"),
                output=node_info["output"],
                retries=3,
                delay=1.0,
                timeout=None,
                parallel=False,
            )
        elif node_info["type"] == "sub_workflow":
            nodes[name] = NodeDefinition(
                sub_workflow=node_info["sub_workflow"],
                inputs_mapping=node_info.get("inputs_mapping"),
                output=node_info["output"],
                retries=3,
                delay=1.0,
                timeout=None,
                parallel=False,
            )

    workflow_structure = WorkflowStructure(
        start=extractor.start_node,
        transitions=extractor.transitions,
        convergence_nodes=extractor.convergence_nodes,
        loops=resolved_loops,  # Use resolved nested loops
    )

    workflow_def = WorkflowDefinition(
        functions=functions,
        nodes=nodes,
        workflow=workflow_structure,
        observers=extractor.observers,
    )

    return workflow_def, extractor.global_vars


def print_workflow_definition(workflow_def):
    """
    Utility function to print a WorkflowDefinition in a human-readable format.

    Args:
        workflow_def (WorkflowDefinition): The workflow definition to print.
    """
    print("### Workflow Definition ###")
    print("\n#### Functions:")
    for name, func in workflow_def.functions.items():
        print(f"- {name}:")
        print(f"  Type: {func.type}")
        print(f"  Code (first line): {func.code.splitlines()[0][:50]}..." if func.code else "  Code: None")

    print("\n#### Nodes:")
    for name, node in workflow_def.nodes.items():
        print(f"- {name}:")
        if node.function:
            print("  Type: Function")
            print(f"  Function: {node.function}")
        elif node.llm_config:
            if node.llm_config.response_model:
                print("  Type: Structured LLM")
                print(f"  Response Model: {node.llm_config.response_model}")
            else:
                print("  Type: LLM")
            print(f"  Model: {node.llm_config.model}")
            print(f"  Prompt Template: {node.llm_config.prompt_template}")
            if node.llm_config.prompt_file:
                print(f"  Prompt File: {node.llm_config.prompt_file}")
        elif node.template_config:
            print("  Type: Template")
            print(f"  Template: {node.template_config.template}")
            if node.template_config.template_file:
                print(f"  Template File: {node.template_config.template_file}")
        elif node.sub_workflow:
            print("  Type: Sub-Workflow")
            print(f"  Start Node: {node.sub_workflow.start}")
        if node.inputs_mapping:
            print(f"  Inputs Mapping: {node.inputs_mapping}")
        print(f"  Output: {node.output or 'None'}")

    print("\n#### Workflow Structure:")
    print(f"Start Node: {workflow_def.workflow.start}")
    print("Transitions:")
    for trans in workflow_def.workflow.transitions:
        if isinstance(trans.to_node, list):
            if all(isinstance(tn, BranchCondition) for tn in trans.to_node):
                for branch in trans.to_node:
                    cond_str = f" [Condition: {branch.condition}]" if branch.condition else ""
                    print(f"- {trans.from_node} -> {branch.to_node}{cond_str}")
            else:
                print(f"- {trans.from_node} -> {trans.to_node} (parallel)")
        else:
            cond_str = f" [Condition: {trans.condition}]" if trans.condition else ""
            print(f"- {trans.from_node} -> {trans.to_node}{cond_str}")
    print("Convergence Nodes:")
    for conv_node in workflow_def.workflow.convergence_nodes:
        print(f"- {conv_node}")
    
    print("Loops:")
    if workflow_def.workflow.loops:
        for loop in workflow_def.workflow.loops:
            print(f"- {loop.loop_id}:")
            print(f"  Entry Node: {loop.entry_node}")
            print(f"  Nodes: {loop.nodes}")
            print(f"  Condition: {loop.condition}")
            print(f"  Exit Nodes: {loop.exit_nodes}")
            if loop.nested_loops:
                print(f"  Nested Loops: {loop.nested_loops}")
    else:
        print("- None")

    print("\n#### Observers:")
    for observer in workflow_def.observers:
        print(f"- {observer}")


def main():
    """Demonstrate extracting a workflow from a Python file and saving it to YAML."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Extract workflow from a Python file')
    parser.add_argument('file_path', nargs='?', default="examples/flow/simple_story_generator/story_generator_agent.py",
                        help='Path to the Python file containing the workflow')
    parser.add_argument('--output', '-o', default="./generated_workflow.py",
                        help='Output path for the executable Python script')
    parser.add_argument('--yaml', '-y', default="workflow_definition.yaml",
                        help='Output path for the YAML workflow definition')

    args = parser.parse_args()
    file_path = args.file_path
    output_file_python = args.output
    yaml_output_path = args.yaml

    if not os.path.exists(file_path):
        logger.error(f"File '{file_path}' not found. Please provide a valid file path.")
        logger.info("Example usage: python -m quantalogic.flow.flow_extractor path/to/your/workflow_file.py")
        sys.exit(1)

    try:
        workflow_def, global_vars = extract_workflow_from_file(file_path)
        logger.info(f"Successfully extracted workflow from '{file_path}'")
        print_workflow_definition(workflow_def)
        generate_executable_script(workflow_def, global_vars, output_file_python)
        logger.info(f"Executable script generated at '{output_file_python}'")

        manager = WorkflowManager(workflow_def)
        manager.save_to_yaml(yaml_output_path)
        logger.info(f"Workflow saved to YAML file '{yaml_output_path}'")
    except Exception as e:
        logger.error(f"Failed to parse or save workflow from '{file_path}': {e}")


if __name__ == "__main__":
    main()