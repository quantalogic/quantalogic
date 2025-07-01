import ast
import re
from collections import defaultdict
from typing import Dict, List, Set, Union

from pydantic import BaseModel

from quantalogic_flow.flow.flow_manager import WorkflowManager
from quantalogic_flow.flow.flow_manager_schema import (
    BranchCondition,
    NodeDefinition,
    TransitionDefinition,
    WorkflowDefinition,
    WorkflowStructure,
)


class ValidationError(BaseModel):
    """Represents a validation error."""
    message: str
    node_name: str | None = None
    error_type: str


class ValidationResult(BaseModel):
    """Result of workflow validation."""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]


class WorkflowValidator:
    """Validator for workflows with comprehensive validation features."""
    
    def validate(self, workflow_def: WorkflowDefinition) -> ValidationResult:
        """Validate a workflow definition."""
        errors = []
        warnings = []
        
        # Run existing validation
        node_errors = validate_workflow_definition(workflow_def)
        errors.extend([
            ValidationError(
                message=error.description,
                node_name=error.node_name,
                error_type="validation_error"
            )
            for error in node_errors
        ])
        
        # Run advanced validation features
        self._validate_unreachable_nodes(workflow_def, warnings)
        self._validate_circular_dependencies(workflow_def, errors, warnings)
        self._validate_transition_references(workflow_def, errors)
        self._validate_branch_conditions(workflow_def, errors)
        self._validate_convergence_nodes(workflow_def, errors)
        self._validate_condition_syntax(workflow_def, warnings)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _validate_unreachable_nodes(self, workflow_def: WorkflowDefinition, warnings: List[ValidationError]):
        """Detect unreachable nodes and add warnings."""
        if not workflow_def.workflow.start:
            return
            
        # Build graph of all transitions
        reachable = set()
        to_visit = [workflow_def.workflow.start]
        
        while to_visit:
            current = to_visit.pop()
            if current in reachable:
                continue
            reachable.add(current)
            
            # Find all transitions from current node
            for trans in workflow_def.workflow.transitions:
                if trans.from_node == current:
                    if isinstance(trans.to_node, str):
                        if trans.to_node not in reachable:
                            to_visit.append(trans.to_node)
                    elif isinstance(trans.to_node, list):
                        for target in trans.to_node:
                            target_node = target if isinstance(target, str) else target.to_node
                            if target_node not in reachable:
                                to_visit.append(target_node)
        
        # Check for unreachable nodes
        all_nodes = set(workflow_def.nodes.keys())
        unreachable = all_nodes - reachable
        
        for node in unreachable:
            warnings.append(ValidationError(
                message=f"Node '{node}' is unreachable from the start node",
                node_name=node,
                error_type="unreachable_node"
            ))
    
    def _validate_circular_dependencies(self, workflow_def: WorkflowDefinition, errors: List[ValidationError], warnings: List[ValidationError]):
        """Validate circular dependencies - warn for conditional cycles, error for unconditional."""
        # Build adjacency list
        graph = defaultdict(list)
        edge_conditions = {}
        
        for trans in workflow_def.workflow.transitions:
            from_node = trans.from_node
            
            if isinstance(trans.to_node, str):
                graph[from_node].append(trans.to_node)
                edge_conditions[(from_node, trans.to_node)] = trans.condition is not None
            elif isinstance(trans.to_node, list):
                for target in trans.to_node:
                    if isinstance(target, str):
                        graph[from_node].append(target)
                        edge_conditions[(from_node, target)] = trans.condition is not None
                    elif hasattr(target, 'to_node'):  # BranchCondition
                        graph[from_node].append(target.to_node)
                        edge_conditions[(from_node, target.to_node)] = True  # Branch conditions are conditional
        
        def detect_cycle_dfs(node: str, path: List[str], visited: Set[str]) -> tuple[bool, List[str], bool]:
            """Returns (has_cycle, cycle_path, has_conditions)"""
            if node in path:
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                
                # Check if cycle has conditions
                has_conditions = False
                for i in range(len(cycle) - 1):
                    if edge_conditions.get((cycle[i], cycle[i+1]), False):
                        has_conditions = True
                        break
                
                return True, cycle, has_conditions
            
            if node in visited:
                return False, [], False
                
            visited.add(node)
            path.append(node)
            
            for neighbor in graph[node]:
                has_cycle, cycle, has_conditions = detect_cycle_dfs(neighbor, path, visited)
                if has_cycle:
                    return has_cycle, cycle, has_conditions
            
            path.pop()
            return False, [], False
        
        visited = set()
        for node in workflow_def.nodes.keys():
            if node not in visited:
                has_cycle, cycle, has_conditions = detect_cycle_dfs(node, [], visited)
                if has_cycle:
                    cycle_str = " -> ".join(cycle)
                    if has_conditions:
                        warnings.append(ValidationError(
                            message=f"Circular dependency detected (might be valid for loops): {cycle_str}",
                            node_name=cycle[0],
                            error_type="circular_dependency"
                        ))
                    else:
                        errors.append(ValidationError(
                            message=f"Circular transition detected without conditions: {cycle_str}",
                            node_name=cycle[0],
                            error_type="circular_dependency"
                        ))
                    break  # Only report first cycle found
    
    def _validate_transition_references(self, workflow_def: WorkflowDefinition, errors: List[ValidationError]):
        """Validate that all transition references point to existing nodes."""
        all_nodes = set(workflow_def.nodes.keys())
        
        for trans in workflow_def.workflow.transitions:
            # Check from_node
            if trans.from_node not in all_nodes:
                errors.append(ValidationError(
                    message=f"Transition references nonexistent from_node '{trans.from_node}'",
                    node_name=trans.from_node,
                    error_type="invalid_transition"
                ))
            
            # Check to_node(s)
            if isinstance(trans.to_node, str):
                if trans.to_node not in all_nodes:
                    errors.append(ValidationError(
                        message=f"Transition references nonexistent to_node '{trans.to_node}'",
                        node_name=trans.to_node,
                        error_type="invalid_transition"
                    ))
            elif isinstance(trans.to_node, list):
                for target in trans.to_node:
                    target_node = target if isinstance(target, str) else target.to_node
                    if target_node not in all_nodes:
                        errors.append(ValidationError(
                            message=f"Transition references nonexistent target_node '{target_node}'",
                            node_name=target_node,
                            error_type="invalid_transition"
                        ))
    
    def _validate_branch_conditions(self, workflow_def: WorkflowDefinition, errors: List[ValidationError]):
        """Validate branch conditions and their referenced nodes."""
        all_nodes = set(workflow_def.nodes.keys())
        
        for trans in workflow_def.workflow.transitions:
            if isinstance(trans.to_node, list):
                for target in trans.to_node:
                    if hasattr(target, 'to_node') and hasattr(target, 'condition'):  # BranchCondition
                        # Check if target node exists
                        if target.to_node not in all_nodes:
                            errors.append(ValidationError(
                                message=f"Branch condition references nonexistent node '{target.to_node}'",
                                node_name=target.to_node,
                                error_type="invalid_branch_condition"
                            ))
                        
                        # Validate condition syntax
                        if target.condition:
                            try:
                                compile(target.condition, "<string>", "eval")
                            except SyntaxError as e:
                                errors.append(ValidationError(
                                    message=f"Invalid branch condition syntax: '{target.condition}' - {e}",
                                    node_name=trans.from_node,
                                    error_type="invalid_branch_condition"
                                ))
    
    def _validate_convergence_nodes(self, workflow_def: WorkflowDefinition, errors: List[ValidationError]):
        """Validate convergence nodes exist and have multiple incoming transitions."""
        all_nodes = set(workflow_def.nodes.keys())
        
        for conv_node in workflow_def.workflow.convergence_nodes:
            # Check if convergence node exists
            if conv_node not in all_nodes:
                errors.append(ValidationError(
                    message=f"Convergence node '{conv_node}' is not defined in nodes",
                    node_name=conv_node,
                    error_type="invalid_convergence_node"
                ))
            
            # Count incoming transitions
            incoming_count = 0
            for trans in workflow_def.workflow.transitions:
                if isinstance(trans.to_node, str) and trans.to_node == conv_node:
                    incoming_count += 1
                elif isinstance(trans.to_node, list):
                    for target in trans.to_node:
                        target_node = target if isinstance(target, str) else target.to_node
                        if target_node == conv_node:
                            incoming_count += 1
            
            if incoming_count < 2:
                errors.append(ValidationError(
                    message=f"Convergence node '{conv_node}' has fewer than 2 incoming transitions",
                    node_name=conv_node,
                    error_type="invalid_convergence_node"
                ))
    
    def _validate_condition_syntax(self, workflow_def: WorkflowDefinition, warnings: List[ValidationError]):
        """Validate syntax of all conditions in the workflow."""
        for trans in workflow_def.workflow.transitions:
            # Check transition condition
            if trans.condition:
                try:
                    compile(trans.condition, "<string>", "eval")
                except SyntaxError as e:
                    warnings.append(ValidationError(
                        message=f"Invalid condition syntax in transition: '{trans.condition}' - {e}",
                        node_name=trans.from_node,
                        error_type="malformed_condition"
                    ))
            
            # Check branch conditions
            if isinstance(trans.to_node, list):
                for target in trans.to_node:
                    if hasattr(target, 'condition') and target.condition:
                        try:
                            compile(target.condition, "<string>", "eval")
                        except SyntaxError as e:
                            warnings.append(ValidationError(
                                message=f"Invalid branch condition syntax: '{target.condition}' - {e}",
                                node_name=trans.from_node,
                                error_type="malformed_condition"
                            ))
    
    def validate_nodes(self, workflow_def: WorkflowDefinition) -> List[ValidationError]:
        """Validate nodes in the workflow."""
        return []
    
    def validate_transitions(self, workflow_def: WorkflowDefinition) -> List[ValidationError]:
        """Validate transitions in the workflow."""
        return []


def validate_workflow(workflow_def: WorkflowDefinition) -> ValidationResult:
    """Validate a workflow definition and return a ValidationResult."""
    validator = WorkflowValidator()
    return validator.validate(workflow_def)


class NodeError(BaseModel):
    """Represents an error associated with a specific node or workflow component."""
    node_name: str | None = None  # None if the error isn't tied to a specific node
    description: str


def get_function_params(code: str, func_name: str) -> List[str]:
    """Extract parameter names from an embedded function's code."""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return [arg.arg for arg in node.args.args]
        raise ValueError(f"Function '{func_name}' not found in code")
    except SyntaxError as e:
        raise ValueError(f"Invalid syntax in code: {e}")


def validate_loops(workflow_def: WorkflowDefinition) -> List[NodeError]:
    """Validate loop structures including nested loops."""
    issues: List[NodeError] = []
    
    # Check if workflow has explicit loop definitions
    if not hasattr(workflow_def.workflow, 'loops') or not workflow_def.workflow.loops:
        return issues
    
    all_nodes = set(workflow_def.nodes.keys())
    
    for i, loop_def in enumerate(workflow_def.workflow.loops):
        loop_id = f"loop_{i}"
        
        # Validate all nodes in loop exist
        for node in loop_def.nodes:
            if node not in all_nodes:
                issues.append(NodeError(
                    node_name=None,
                    description=f"Loop {loop_id} references undefined node '{node}'"
                ))
        
        # Validate exit node exists
        if loop_def.exit_node not in all_nodes:
            issues.append(NodeError(
                node_name=None,
                description=f"Loop {loop_id} exit_node '{loop_def.exit_node}' is not defined"
            ))
        
        # Validate loop condition syntax
        try:
            # Test if condition can be compiled as a lambda
            test_condition = f"lambda ctx: {loop_def.condition}"
            compile(test_condition, "<string>", "eval")
        except SyntaxError:
            issues.append(NodeError(
                node_name=None,
                description=f"Loop {loop_id} has invalid condition syntax: '{loop_def.condition}'"
            ))
        
        # Check for empty loops
        if not loop_def.nodes:
            issues.append(NodeError(
                node_name=None,
                description=f"Loop {loop_id} has no nodes defined"
            ))
    
    # Validate nested loop structure (check for overlapping but not nested loops)
    for i, loop1 in enumerate(workflow_def.workflow.loops):
        for j, loop2 in enumerate(workflow_def.workflow.loops):
            if i >= j:
                continue
            
            set1 = set(loop1.nodes)
            set2 = set(loop2.nodes)
            
            # Check for partial overlap (indicates potential structure issues)
            if set1 & set2 and not (set1.issubset(set2) or set2.issubset(set1)):
                issues.append(NodeError(
                    node_name=None,
                    description=f"Loops loop_{i} and loop_{j} have overlapping nodes but neither is fully nested: {set1 & set2}"
                ))
    
    return issues


def detect_circular_dependencies(workflow_def: WorkflowDefinition) -> List[NodeError]:
    """Detect circular dependencies in workflow structure."""
    issues: List[NodeError] = []
    
    # Build adjacency list from transitions
    graph = defaultdict(list)
    for trans in workflow_def.workflow.transitions:
        if isinstance(trans.to_node, str):
            graph[trans.from_node].append(trans.to_node)
        elif isinstance(trans.to_node, list):
            for target in trans.to_node:
                if isinstance(target, str):
                    graph[trans.from_node].append(target)
                elif hasattr(target, 'to_node'):  # BranchCondition
                    graph[trans.from_node].append(target.to_node)
    
    def has_cycle_dfs(node: str, visited: Set[str], rec_stack: Set[str]) -> bool:
        """DFS to detect cycles."""
        visited.add(node)
        rec_stack.add(node)
        
        for neighbor in graph[node]:
            if neighbor not in visited:
                if has_cycle_dfs(neighbor, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                return True
        
        rec_stack.remove(node)
        return False
    
    visited = set()
    for node in workflow_def.nodes.keys():
        if node not in visited:
            if has_cycle_dfs(node, visited, set()):
                issues.append(NodeError(
                    node_name=node,
                    description=f"Circular dependency detected starting from node '{node}'"
                ))
                break  # One circular dependency report is enough
    
    return issues


def validate_workflow_definition(workflow_def: WorkflowDefinition) -> List[NodeError]:
    """Validate a workflow definition and return a list of NodeError objects."""
    issues: List[NodeError] = []
    output_names: Set[str] = set()

    # Validate function definitions
    for name, func_def in workflow_def.functions.items():
        if func_def.type == "embedded" and not func_def.code:
            issues.append(NodeError(node_name=None, description=f"Embedded function '{name}' is missing 'code'"))
        elif func_def.type == "external" and (not func_def.module or not func_def.function):
            issues.append(NodeError(node_name=None, description=f"External function '{name}' is missing 'module' or 'function'"))

    # Validate nodes
    for name, node_def in workflow_def.nodes.items():
        if node_def.function and node_def.function not in workflow_def.functions:
            issues.append(NodeError(node_name=name, description=f"References undefined function '{node_def.function}'"))

        if node_def.output:
            if not node_def.output.isidentifier():
                issues.append(NodeError(node_name=name, description=f"Has invalid output name '{node_def.output}'"))
            elif node_def.output in output_names:
                issues.append(NodeError(node_name=name, description=f"Has duplicate output name '{node_def.output}'"))
            output_names.add(node_def.output)

        if node_def.sub_workflow:
            sub_issues = validate_workflow_structure(node_def.sub_workflow, workflow_def.nodes)
            issues.extend(
                NodeError(node_name=f"{name}/{issue.node_name}" if issue.node_name else name, description=issue.description)
                for issue in sub_issues
            )

        if node_def.llm_config:
            llm = node_def.llm_config
            if not llm.model:
                issues.append(NodeError(node_name=name, description="Missing 'model' in llm_config"))
            if not llm.prompt_template and not llm.prompt_file:
                issues.append(NodeError(node_name=name, description="Missing 'prompt_template' or 'prompt_file' in llm_config"))
            if llm.temperature < 0 or llm.temperature > 1:
                issues.append(NodeError(node_name=name, description=f"Has invalid temperature: {llm.temperature}"))

        if node_def.template_config:
            template = node_def.template_config
            if not template.template and not template.template_file:
                issues.append(NodeError(node_name=name, description="Missing 'template' or 'template_file' in template_config"))

    # Validate main workflow structure
    issues.extend(validate_workflow_structure(workflow_def.workflow, workflow_def.nodes, is_main=True))
    issues.extend(check_circular_transitions(workflow_def))

    # Build the unified graph for main workflow and sub-workflows
    successors = defaultdict(list)
    predecessors = defaultdict(list)
    all_nodes = set(workflow_def.nodes.keys())

    # Add main workflow transitions
    for trans in workflow_def.workflow.transitions:
        from_node = trans.from_node
        to_nodes = [trans.to_node] if isinstance(trans.to_node, str) else [tn if isinstance(tn, str) else tn.to_node for tn in trans.to_node]
        for to_node in to_nodes:
            successors[from_node].append(to_node)
            predecessors[to_node].append(from_node)
            all_nodes.add(to_node)

    # Add sub-workflow transitions with namespaced node names
    for parent_name, node_def in workflow_def.nodes.items():
        if node_def.sub_workflow:
            for trans in node_def.sub_workflow.transitions:
                from_node = f"{parent_name}/{trans.from_node}"
                to_nodes = [trans.to_node] if isinstance(trans.to_node, str) else [tn if isinstance(tn, str) else tn.to_node for tn in trans.to_node]
                namespaced_to_nodes = [f"{parent_name}/{to_node}" for to_node in to_nodes]
                all_nodes.add(from_node)
                all_nodes.update(namespaced_to_nodes)
                successors[from_node].extend(namespaced_to_nodes)
                for to_node in namespaced_to_nodes:
                    predecessors[to_node].append(from_node)

    # Define function to get ancestors, handling cycles with a visited set
    def get_ancestors(node: str, visited: Set[str] = None) -> Set[str]:
        if visited is None:
            visited = set()
        if node in visited or node not in all_nodes:
            return set()
        visited.add(node)
        ancestors = set(predecessors[node])
        for pred in predecessors[node]:
            ancestors.update(get_ancestors(pred, visited.copy()))
        return ancestors

    # Create output-to-node mapping, including sub-workflow nodes
    output_to_node = {}
    for node_name, node_def in workflow_def.nodes.items():
        if node_def.output:
            output_to_node[node_def.output] = node_name
        if node_def.sub_workflow:
            for sub_node_name, sub_node_def in workflow_def.nodes.items():
                if sub_node_def.output:
                    output_to_node[sub_node_def.output] = f"{node_name}/{sub_node_name}"

    # Check each node's inputs against ancestors' outputs, including sub-workflows
    for node_name, node_def in workflow_def.nodes.items():
        required_inputs = set()
        full_node_name = node_name

        # Handle inputs_mapping
        if node_def.inputs_mapping:
            for input_name, mapping in node_def.inputs_mapping.items():
                if mapping.startswith("lambda ctx:"):
                    try:
                        # Basic syntax check for lambda
                        compile(mapping, "<string>", "eval")
                    except SyntaxError:
                        issues.append(NodeError(
                            node_name=node_name,
                            description=f"Invalid lambda expression in inputs_mapping for '{input_name}': {mapping}"
                        ))
                elif not mapping.isidentifier():
                    issues.append(NodeError(
                        node_name=node_name,
                        description=f"Invalid context key in inputs_mapping for '{input_name}': {mapping}"
                    ))

        if node_def.function:
            maybe_func_def = workflow_def.functions.get(node_def.function)
            if maybe_func_def is None:
                issues.append(NodeError(
                    node_name=node_name,
                    description=f"Function '{node_def.function}' not found in workflow functions"
                ))
            else:
                func_def = maybe_func_def
                if func_def.type == "embedded" and func_def.code:
                    try:
                        params = get_function_params(func_def.code, node_def.function)
                        required_inputs = set(params)
                    except ValueError as e:
                        issues.append(NodeError(node_name=node_name, description=f"Failed to parse function '{node_def.function}': {e}"))
        elif node_def.llm_config:
            prompt_template = node_def.llm_config.prompt_template or ""
            input_vars = set(re.findall(r"{{\s*([^}]+?)\s*}}", prompt_template))
            cleaned_inputs = set()
            for var in input_vars:
                base_var = re.split(r"\s*[\+\-\*/]\s*", var.strip())[0].strip()
                if base_var.isidentifier():
                    cleaned_inputs.add(base_var)
            required_inputs = cleaned_inputs
        elif node_def.template_config:
            template = node_def.template_config.template or ""
            input_vars = set(re.findall(r"{{\s*([^}]+?)\s*}}", template))
            cleaned_inputs = set()
            for var in input_vars:
                base_var = re.split(r"\s*[\+\-\*/]\s*", var.strip())[0].strip()
                if base_var.isidentifier():
                    cleaned_inputs.add(base_var)
            required_inputs = cleaned_inputs
        elif node_def.sub_workflow:
            for sub_node_name, sub_node_def in workflow_def.nodes.items():
                full_node_name = f"{node_name}/{sub_node_name}"
                if sub_node_def.function:
                    maybe_func_def = workflow_def.functions.get(sub_node_def.function)
                    if maybe_func_def is None:
                        issues.append(NodeError(
                            node_name=full_node_name,
                            description=f"Function '{sub_node_def.function}' not found in workflow functions"
                        ))
                    else:
                        func_def = maybe_func_def
                        if func_def.type == "embedded" and func_def.code:
                            try:
                                params = get_function_params(func_def.code, sub_node_def.function)
                                required_inputs = set(params)
                            except ValueError as e:
                                issues.append(NodeError(
                                    node_name=full_node_name,
                                    description=f"Failed to parse function '{sub_node_def.function}': {e}"
                                ))
                elif sub_node_def.llm_config:
                    prompt_template = sub_node_def.llm_config.prompt_template or ""
                    input_vars = set(re.findall(r"{{\s*([^}]+?)\s*}}", prompt_template))
                    cleaned_inputs = set()
                    for var in input_vars:
                        base_var = re.split(r"\s*[\+\-\*/]\s*", var.strip())[0].strip()
                        if base_var.isidentifier():
                            cleaned_inputs.add(base_var)
                    required_inputs = cleaned_inputs
                elif sub_node_def.template_config:
                    template = sub_node_def.template_config.template or ""
                    input_vars = set(re.findall(r"{{\s*([^}]+?)\s*}}", template))
                    cleaned_inputs = set()
                    for var in input_vars:
                        base_var = re.split(r"\s*[\+\-\*/]\s*", var.strip())[0].strip()
                        if base_var.isidentifier():
                            cleaned_inputs.add(base_var)
                    required_inputs = cleaned_inputs

                if required_inputs:
                    ancestors = get_ancestors(full_node_name)
                    for input_name in required_inputs:
                        # Check if input is mapped
                        if node_def.inputs_mapping and input_name in node_def.inputs_mapping:
                            mapping = node_def.inputs_mapping[input_name]
                            if not mapping.startswith("lambda ctx:") and mapping in output_to_node:
                                producer_node = output_to_node.get(mapping)
                                if producer_node not in ancestors:
                                    issues.append(NodeError(
                                        node_name=full_node_name,
                                        description=f"inputs_mapping for '{input_name}' maps to '{mapping}', but it is not produced by an ancestor"
                                    ))
                            continue
                        producer_node = output_to_node.get(input_name)
                        if producer_node is None or producer_node not in ancestors:
                            issues.append(NodeError(
                                node_name=full_node_name,
                                description=f"Requires input '{input_name}', but it is not produced by any ancestor"
                            ))
            continue

        if not required_inputs:
            continue

        # Skip input validation for start nodes
        if full_node_name == workflow_def.workflow.start:
            continue

        ancestors = get_ancestors(full_node_name)
        for input_name in required_inputs:
            # Check if input is mapped
            if node_def.inputs_mapping and input_name in node_def.inputs_mapping:
                mapping = node_def.inputs_mapping[input_name]
                if not mapping.startswith("lambda ctx:") and mapping in output_to_node:
                    producer_node = output_to_node.get(mapping)
                    if producer_node not in ancestors:
                        issues.append(NodeError(
                            node_name=full_node_name,
                            description=f"inputs_mapping for '{input_name}' maps to '{mapping}', but it is not produced by an ancestor"
                        ))
                continue
            producer_node = output_to_node.get(input_name)
            if producer_node is None or producer_node not in ancestors:
                issues.append(NodeError(
                    node_name=full_node_name,
                    description=f"Requires input '{input_name}', but it is not produced by any ancestor"
                ))

    # Validate observers
    for observer in workflow_def.observers:
        if observer not in workflow_def.functions:
            issues.append(NodeError(node_name=None, description=f"Observer '{observer}' references undefined function"))

    # Validate convergence nodes
    for conv_node in workflow_def.workflow.convergence_nodes:
        if conv_node not in workflow_def.nodes:
            issues.append(NodeError(node_name=conv_node, description="Convergence node is not defined in nodes"))
        # Check if the convergence node has multiple incoming transitions
        incoming = [t for t in workflow_def.workflow.transitions if
                    (isinstance(t.to_node, str) and t.to_node == conv_node) or
                    (isinstance(t.to_node, list) and any(isinstance(tn, str) and tn == conv_node or
                                                        isinstance(tn, BranchCondition) and tn.to_node == conv_node
                                                        for tn in t.to_node))]
        if len(incoming) < 2:
            issues.append(NodeError(node_name=conv_node, description="Convergence node has fewer than 2 incoming transitions"))

    return issues


def validate_workflow_structure(structure: WorkflowStructure, nodes: Dict[str, NodeDefinition],
                              is_main: bool = False) -> List[NodeError]:
    """Validate a WorkflowStructure for consistency, including branch and converge support."""
    issues: List[NodeError] = []

    if is_main and not structure.start:
        issues.append(NodeError(node_name=None, description="Main workflow is missing a start node"))
    elif structure.start and structure.start not in nodes:
        issues.append(NodeError(node_name=structure.start, description="Start node is not defined in nodes"))

    for trans in structure.transitions:
        if trans.from_node not in nodes:
            issues.append(NodeError(node_name=trans.from_node, description="Transition from undefined node"))

        to_nodes: List[Union[str, BranchCondition]] = [trans.to_node] if isinstance(trans.to_node, str) else trans.to_node
        for to_node in to_nodes:
            target_node = to_node if isinstance(to_node, str) else to_node.to_node
            if target_node not in nodes:
                issues.append(NodeError(node_name=target_node, description=f"Transition to undefined node from '{trans.from_node}'"))
            if isinstance(to_node, BranchCondition) and to_node.condition:
                try:
                    compile(to_node.condition, "<string>", "eval")
                except SyntaxError:
                    issues.append(NodeError(node_name=trans.from_node, description=f"Invalid branch condition syntax: {to_node.condition}"))

        if trans.condition and isinstance(trans.to_node, str):
            try:
                compile(trans.condition, "<string>", "eval")
            except SyntaxError:
                issues.append(NodeError(node_name=trans.from_node, description=f"Invalid condition syntax in transition: {trans.condition}"))

    return issues


def check_circular_transitions(workflow_def: WorkflowDefinition) -> List[NodeError]:
    """Detect circular transitions in the workflow using DFS, allowing cycles with conditions."""
    issues: List[NodeError] = []

    def dfs(node: str, visited: Set[str], path: Set[str], transitions: List[TransitionDefinition], path_transitions: List[TransitionDefinition]) -> None:
        if node in path:
            cycle_nodes = list(path)[list(path).index(node):] + [node]
            cycle = " -> ".join(cycle_nodes)
            cycle_transitions = [
                t for t in path_transitions
                if t.from_node in cycle_nodes and
                   ((isinstance(t.to_node, str) and t.to_node in cycle_nodes) or
                    (isinstance(t.to_node, list) and any((isinstance(tn, str) and tn in cycle_nodes) or
                                                        (isinstance(tn, BranchCondition) and tn.to_node in cycle_nodes)
                                                        for tn in t.to_node)))
            ]
            # Check if all transitions in the cycle are unconditional
            has_conditions = any(
                t.condition or (isinstance(t.to_node, list) and any(isinstance(tn, BranchCondition) and tn.condition for tn in t.to_node))
                for t in cycle_transitions
            )
            if not has_conditions:
                issues.append(NodeError(node_name=node, description=f"Circular transition detected without conditions: {cycle}"))
            return

        if node in visited:
            return

        visited.add(node)
        path.add(node)

        for trans in transitions:
            if trans.from_node == node:
                path_transitions.append(trans)
                to_nodes = [trans.to_node] if isinstance(trans.to_node, str) else trans.to_node
                for to_node in to_nodes:
                    next_node = to_node if isinstance(to_node, str) else to_node.to_node
                    dfs(next_node, visited, path, transitions, path_transitions)
                path_transitions.pop()

        path.remove(node)

    if workflow_def.workflow.start:
        dfs(workflow_def.workflow.start, set(), set(), workflow_def.workflow.transitions, [])

    for node_name, node_def in workflow_def.nodes.items():
        if node_def.sub_workflow and node_def.sub_workflow.start:
            dfs(node_def.sub_workflow.start, set(), set(), node_def.sub_workflow.transitions, [])

    # Validate loop structures
    loop_issues = validate_loops(workflow_def)
    issues.extend(loop_issues)
    
    # Validate for circular dependencies
    circular_issues = detect_circular_dependencies(workflow_def)
    issues.extend(circular_issues)

    return issues


def main():
    """Build a sample workflow with branch, converge, template node, and input mapping using WorkflowManager and validate it."""
    manager = WorkflowManager()

    # Define functions
    manager.add_function(
        name="say_hello",
        type_="embedded",
        code="def say_hello():\n    return 'Hello, World!'"
    )
    manager.add_function(
        name="say_goodbye",
        type_="embedded",
        code="def say_goodbye():\n    return 'Goodbye, World!'"
    )
    manager.add_function(
        name="check_condition",
        type_="embedded",
        code="def check_condition(text: str):\n    return 'yes' if 'Hello' in text else 'no'"
    )
    manager.add_function(
        name="finalize",
        type_="embedded",
        code="def finalize(text: str):\n    return 'Done'"
    )

    # Add nodes for main workflow
    manager.add_node(name="start", function="say_hello", output="text")
    manager.add_node(name="check", function="check_condition", output="result",
                     inputs_mapping={"text": "text"})  # Mapping input to context key
    manager.add_node(name="goodbye", function="say_goodbye", output="farewell")
    manager.add_node(name="finalize", function="finalize", output="status",
                     inputs_mapping={"text": "lambda ctx: ctx['farewell'] if ctx['result'] == 'no' else ctx['ai_result']"})
    manager.add_node(name="outro", function="non_existent")  # Intentional: undefined function

    # Add LLM node with valid temperature
    manager.add_node(
        name="ai_node",
        llm_config={
            "model": "gpt-3.5-turbo",
            "prompt_template": "{{text}}",
            "temperature": 0.7
        },
        output="ai_result"
    )

    # Add template node
    manager.add_node(
        name="template_node",
        template_config={
            "template": "Response: {{text}} - {{result}}"
        },
        output="template_output"
    )

    # Add nodes and sub-workflow
    manager.add_node(name="nested_start", function="say_hello", output="nested_text")
    manager.add_node(name="nested_end", function="say_goodbye")
    sub_workflow = WorkflowStructure(start="nested_start")
    sub_workflow.transitions.append(TransitionDefinition(from_node="nested_start", to_node="nested_end"))
    manager.add_node(name="nested", sub_workflow=sub_workflow)

    # Configure main workflow with branch and converge
    manager.set_start_node("start")
    manager.add_transition(from_node="start", to_node="check")
    manager.add_transition(
        from_node="check",
        to_node=[
            BranchCondition(to_node="ai_node", condition="ctx['result'] == 'yes'"),
            BranchCondition(to_node="goodbye", condition="ctx['result'] == 'no'")
        ]
    )
    manager.add_transition(from_node="ai_node", to_node="finalize")
    manager.add_transition(from_node="goodbye", to_node="finalize")
    manager.add_transition(from_node="finalize", to_node="template_node")
    manager.add_transition(from_node="start", to_node="outro")
    manager.add_transition(from_node="outro", to_node="start")  # Intentional: circular
    manager.add_convergence_node("finalize")

    # Add observer with error handling
    try:
        manager.add_observer("undefined_observer")  # Intentional: undefined observer
    except ValueError:
        pass  # Allow validation to proceed

    # Validate the constructed workflow
    workflow = manager.workflow
    issues = validate_workflow_definition(workflow)

    # Display results
    if issues:
        print("Issues found in workflow definition:")
        for issue in sorted(issues, key=lambda x: (x.node_name or '', x.description)):
            node_part = f"Node '{issue.node_name}'" if issue.node_name else "Workflow"
            print(f"- {node_part}: {issue.description}")
    else:
        print("No issues found in workflow definition.")


if __name__ == "__main__":
    main()
