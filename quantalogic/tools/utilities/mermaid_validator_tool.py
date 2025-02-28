"""Tool for validating Mermaid diagram syntax."""

import re
from typing import Dict, List, Optional

from loguru import logger

from quantalogic.tools.tool import Tool, ToolArgument


class MermaidValidatorTool(Tool):
    """Tool for validating Mermaid diagram syntax."""

    name: str = "mermaid_validator_tool"
    description: str = "Validates Mermaid diagram syntax and returns any errors found."
    need_validation: bool = False
    arguments: list = [
        ToolArgument(
            name="mermaid_code",
            arg_type="string",
            description="The Mermaid diagram code to validate.",
            required=True,
            example="flowchart TD\n    A[Start] --> B[End]",
        )
    ]

    def _validate_flowchart(self, code: str) -> List[str]:
        """Validate flowchart diagram syntax."""
        errors = []
        lines = code.strip().split('\n')
        
        # Check if starts with flowchart
        if not lines[0].strip().startswith('flowchart'):
            errors.append("Flowchart must start with 'flowchart' keyword")
            
        # Check node definitions and connections
        node_ids = set()
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
                
            # Check for node definitions
            node_matches = re.findall(r'([A-Za-z0-9_]+)(?:\[|\(|\{)(.+?)(?:\]|\)|\})', line)
            for node_id, _ in node_matches:
                node_ids.add(node_id)
            
            # Check connections
            if '-->' in line or '---' in line:
                parts = re.split(r'-->|---', line)
                for part in parts:
                    node_id = part.strip().split('[')[0].strip()
                    if node_id and node_id not in node_ids:
                        errors.append(f"Node '{node_id}' is used in connection but not defined")
        
        return errors

    def _validate_sequence(self, code: str) -> List[str]:
        """Validate sequence diagram syntax."""
        errors = []
        lines = code.strip().split('\n')
        
        # Check if starts with sequenceDiagram
        if not lines[0].strip() == 'sequenceDiagram':
            errors.append("Sequence diagram must start with 'sequenceDiagram' keyword")
            
        # Track participants
        participants = set()
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
                
            # Check participant definitions
            if line.startswith('participant'):
                participant = line.split()[1]
                participants.add(participant)
                
            # Check message syntax
            elif any(op in line for op in ['->>','-->>','->','-->']):
                parts = re.split(r'[-]+>>|[-]+>', line)
                if len(parts) == 2:
                    sender = parts[0].strip()
                    receiver = parts[1].split(':')[0].strip()
                    
                    if sender not in participants:
                        errors.append(f"Undefined participant '{sender}' in message")
                    if receiver not in participants:
                        errors.append(f"Undefined participant '{receiver}' in message")
                else:
                    errors.append(f"Invalid message syntax in line: {line}")
        
        return errors

    def _validate_gantt(self, code: str) -> List[str]:
        """Validate Gantt chart syntax."""
        errors = []
        lines = code.strip().split('\n')
        
        # Check if starts with gantt
        if not lines[0].strip() == 'gantt':
            errors.append("Gantt chart must start with 'gantt' keyword")
            
        has_title = False
        has_date_format = False
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('title'):
                has_title = True
            elif line.startswith('dateFormat'):
                has_date_format = True
            elif line.startswith('section'):
                section_name = line.replace('section', '').strip()
                if not section_name:
                    errors.append("Section must have a name")
            elif ':' in line:
                # Task definition
                parts = line.split(':')
                if len(parts) < 2:
                    errors.append(f"Invalid task definition in line: {line}")
                    
                # Validate date format if present
                dates = re.findall(r'\d{4}-\d{2}-\d{2}', parts[1])
                for date in dates:
                    try:
                        from datetime import datetime
                        datetime.strptime(date, '%Y-%m-%d')
                    except ValueError:
                        errors.append(f"Invalid date format in line: {line}")
        
        if not has_title:
            errors.append("Gantt chart should have a title")
        if not has_date_format:
            errors.append("Gantt chart should specify dateFormat")
            
        return errors

    def _validate_class(self, code: str) -> List[str]:
        """Validate class diagram syntax."""
        errors = []
        lines = code.strip().split('\n')
        
        # Check if starts with classDiagram
        if not lines[0].strip().startswith('classDiagram'):
            errors.append("Class diagram must start with 'classDiagram' keyword")
        
        class_names = set()
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
                
            # Check class definitions
            if 'class' in line and '{' not in line:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == 'class':
                    class_names.add(parts[1])
            
            # Check relationships
            relationship_symbols = ['-->', '<--', '--', '..>', '<..', '..', '--|>', '<|--', '<|..', '..|>']
            for symbol in relationship_symbols:
                if symbol in line:
                    parts = line.split(symbol)
                    if len(parts) == 2:
                        class1 = parts[0].strip().split()[0]
                        class2 = parts[1].strip().split()[0]
                        
                        if class1 not in class_names and not class1.startswith('"'):
                            errors.append(f"Undefined class '{class1}' in relationship")
                        if class2 not in class_names and not class2.startswith('"'):
                            errors.append(f"Undefined class '{class2}' in relationship")
            
            # Check method and property syntax in class definitions
            if ':' in line and '--' not in line and '.' not in line:
                parts = line.split(':')
                if len(parts) != 2:
                    errors.append(f"Invalid method/property syntax in line: {line}")
                    
        return errors

    def _validate_state(self, code: str) -> List[str]:
        """Validate state diagram syntax."""
        errors = []
        lines = code.strip().split('\n')
        
        # Check if starts with stateDiagram
        if not (lines[0].strip().startswith('stateDiagram') or lines[0].strip().startswith('stateDiagram-v2')):
            errors.append("State diagram must start with 'stateDiagram' or 'stateDiagram-v2' keyword")
        
        state_names = set()
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
                
            # Check state definitions
            if line.startswith('state'):
                parts = line.split()
                if len(parts) >= 2:
                    state_names.add(parts[1].strip('{}[]()'))
            
            # Check transitions
            if '-->' in line:
                parts = line.split('-->')
                if len(parts) == 2:
                    state1 = parts[0].strip().split()[0].strip('{}[]()""')
                    state2 = parts[1].strip().split()[0].strip('{}[]()""')
                    
                    if state1 not in state_names and state1 != '[*]':
                        errors.append(f"Undefined state '{state1}' in transition")
                    if state2 not in state_names and state2 != '[*]':
                        errors.append(f"Undefined state '{state2}' in transition")
            
            # Check composite states
            if '{' in line and '}' not in line:
                errors.append(f"Unclosed composite state in line: {line}")
                
        return errors

    def _validate_er(self, code: str) -> List[str]:
        """Validate ER diagram syntax."""
        errors = []
        lines = code.strip().split('\n')
        
        # Check if starts with erDiagram
        if not lines[0].strip() == 'erDiagram':
            errors.append("ER diagram must start with 'erDiagram' keyword")
        
        entity_names = set()
        relationship_types = {'one_to_one', 'one_to_many', 'many_to_one', 'many_to_many'}
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
                
            # Check entity definitions and relationships
            if '||' in line or 'o{' in line or '}o' in line or '||' in line:
                parts = line.split()
                if len(parts) >= 3:
                    entity1 = parts[0]
                    entity2 = parts[2]
                    entity_names.add(entity1)
                    entity_names.add(entity2)
                    
                    # Check relationship syntax
                    if len(parts) < 4:
                        errors.append(f"Missing relationship type in line: {line}")
                    elif not any(rel_type in line for rel_type in ['||--||', '||--o{', '}o--||', '}o--o{']):
                        errors.append(f"Invalid relationship syntax in line: {line}")
            
            # Check attribute definitions
            if '{' in line and '}' in line and '--' not in line:
                entity = line.split('{')[0].strip()
                if entity not in entity_names:
                    errors.append(f"Undefined entity '{entity}' has attributes")
                
                # Check attribute syntax
                attributes = line[line.find('{')+1:line.find('}')].split(',')
                for attr in attributes:
                    attr = attr.strip()
                    if not attr or ' ' not in attr:
                        errors.append(f"Invalid attribute syntax in line: {line}")
                    
        return errors

    def _validate_journey(self, code: str) -> List[str]:
        """Validate journey diagram syntax."""
        errors = []
        lines = code.strip().split('\n')
        
        # Check if starts with journey
        if not lines[0].strip() == 'journey':
            errors.append("Journey diagram must start with 'journey' keyword")
        
        has_title = False
        valid_scores = {'1', '2', '3', '4', '5'}
        current_section = None
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
                
            # Check title
            if line.startswith('title'):
                has_title = True
                title = line.replace('title', '').strip()
                if not title:
                    errors.append("Journey title cannot be empty")
            
            # Check sections
            elif line.startswith('section'):
                current_section = line.replace('section', '').strip()
                if not current_section:
                    errors.append("Section must have a name")
            
            # Check tasks
            elif ':' in line and not line.startswith('title'):
                if not current_section:
                    errors.append(f"Task must be within a section: {line}")
                    
                parts = line.split(':')
                if len(parts) != 2:
                    errors.append(f"Invalid task syntax in line: {line}")
                else:
                    # Check task score
                    score = parts[1].strip().split()[0]
                    if score not in valid_scores:
                        errors.append(f"Invalid task score in line: {line}. Must be between 1-5")
        
        if not has_title:
            errors.append("Journey diagram should have a title")
            
        return errors

    def _validate_pie(self, code: str) -> List[str]:
        """Validate pie chart syntax."""
        errors = []
        lines = code.strip().split('\n')
        
        # Check if starts with pie
        if not lines[0].strip() == 'pie':
            errors.append("Pie chart must start with 'pie' keyword")
        
        has_title = False
        has_data = False
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
                
            # Check title
            if line.startswith('title'):
                has_title = True
                title = line.replace('title', '').strip()
                if not title:
                    errors.append("Pie chart title cannot be empty")
            
            # Check data entries
            elif ':' in line:
                has_data = True
                parts = line.split(':')
                if len(parts) != 2:
                    errors.append(f"Invalid data entry syntax in line: {line}")
                else:
                    # Check if value is numeric
                    try:
                        float(parts[1].strip())
                    except ValueError:
                        errors.append(f"Value must be numeric in line: {line}")
        
        if not has_title:
            errors.append("Pie chart should have a title")
        if not has_data:
            errors.append("Pie chart must have at least one data entry")
            
        return errors

    def _validate_mindmap(self, code: str) -> List[str]:
        """Validate mindmap syntax."""
        errors = []
        lines = code.strip().split('\n')
        
        # Check if starts with mindmap
        if not lines[0].strip() == 'mindmap':
            errors.append("Mindmap must start with 'mindmap' keyword")
        
        has_root = False
        current_level = 0
        previous_level = 0
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            
            # Count leading spaces to determine level
            indent_level = len(line) - len(line.lstrip())
            current_level = indent_level // 2  # Each level is 2 spaces
            
            # First non-empty line should be root
            if not has_root:
                has_root = True
                if current_level != 0:
                    errors.append("Root node must not be indented")
                continue
            
            # Check indentation consistency
            if current_level > previous_level + 1:
                errors.append(f"Invalid indentation in line: {line}")
            
            # Check node syntax
            if line.lstrip().startswith('::'):
                errors.append(f"Node text missing in line: {line}")
            elif '::' in line:
                parts = line.split('::')
                if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                    errors.append(f"Invalid node format in line: {line}")
            
            previous_level = current_level
        
        if not has_root:
            errors.append("Mindmap must have a root node")
            
        return errors

    def _validate_timeline(self, code: str) -> List[str]:
        """Validate timeline syntax."""
        errors = []
        lines = code.strip().split('\n')
        
        # Check if starts with timeline
        if not lines[0].strip() == 'timeline':
            errors.append("Timeline must start with 'timeline' keyword")
        
        has_title = False
        current_section = None
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
                
            # Check title
            if line.startswith('title'):
                has_title = True
                title = line.replace('title', '').strip()
                if not title:
                    errors.append("Timeline title cannot be empty")
            
            # Check sections
            elif line.startswith('section'):
                current_section = line.replace('section', '').strip()
                if not current_section:
                    errors.append("Section must have a name")
            
            # Check events
            elif ':' in line and not line.startswith('title'):
                if not current_section:
                    errors.append(f"Event must be within a section: {line}")
                    
                parts = line.split(':')
                if len(parts) != 2:
                    errors.append(f"Invalid event syntax in line: {line}")
                else:
                    # Check date format if present
                    date_str = parts[0].strip()
                    if date_str:
                        try:
                            # Support various date formats
                            from dateutil import parser
                            parser.parse(date_str)
                        except (ValueError, ImportError):
                            errors.append(f"Invalid date format in line: {line}")
        
        if not has_title:
            errors.append("Timeline should have a title")
            
        return errors

    def _validate_git_graph(self, code: str) -> List[str]:
        """Validate git graph syntax."""
        errors = []
        lines = code.strip().split('\n')
        
        # Check if starts with gitGraph
        if not lines[0].strip() == 'gitGraph':
            errors.append("Git graph must start with 'gitGraph' keyword")
        
        valid_commands = {'commit', 'branch', 'checkout', 'merge', 'reset', 'cherry-pick'}
        branches = {'main'}  # main/master is always available
        current_branch = 'main'
        commit_ids = set()
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split()
            if not parts:
                continue
                
            command = parts[0]
            
            if command not in valid_commands:
                errors.append(f"Invalid command '{command}' in line: {line}")
                continue
                
            # Check branch operations
            if command == 'branch':
                if len(parts) < 2:
                    errors.append(f"Branch name missing in line: {line}")
                else:
                    branch_name = parts[1]
                    if branch_name in branches:
                        errors.append(f"Branch '{branch_name}' already exists")
                    else:
                        branches.add(branch_name)
                        
            elif command == 'checkout':
                if len(parts) < 2:
                    errors.append(f"Branch name missing in line: {line}")
                else:
                    branch_name = parts[1]
                    if branch_name not in branches:
                        errors.append(f"Cannot checkout non-existent branch '{branch_name}'")
                    else:
                        current_branch = branch_name
                        
            # Check commit operations
            elif command == 'commit':
                if len(parts) > 1 and parts[1].startswith('id:'):
                    commit_id = parts[1].split(':')[1]
                    if commit_id in commit_ids:
                        errors.append(f"Duplicate commit ID '{commit_id}'")
                    else:
                        commit_ids.add(commit_id)
                        
            # Check merge operations
            elif command == 'merge':
                if len(parts) < 2:
                    errors.append(f"Merge target missing in line: {line}")
                else:
                    target_branch = parts[1]
                    if target_branch not in branches:
                        errors.append(f"Cannot merge non-existent branch '{target_branch}'")
                    elif target_branch == current_branch:
                        errors.append(f"Cannot merge branch '{target_branch}' into itself")
        
        return errors

    def _validate_general(self, code: str) -> List[str]:
        """General validator for any Mermaid diagram type.
        
        Performs basic syntax validation that applies to all diagram types:
        - Non-empty content
        - Balanced brackets and quotes
        - Basic syntax elements
        """
        errors = []
        lines = code.strip().split('\n')
        
        if not lines:
            errors.append("Diagram cannot be empty")
            return errors
            
        # Get diagram type from first line
        diagram_type = lines[0].strip()
        if not diagram_type:
            errors.append("First line must specify diagram type")
            
        # Track brackets and quotes
        brackets = {
            '(': ')', 
            '[': ']', 
            '{': '}', 
            '"': '"', 
            "'": "'"
        }
        stack = []
        
        for i, line in enumerate(lines, 1):
            # Skip empty lines
            if not line.strip():
                continue
                
            # Check for unmatched quotes and brackets
            for char in line:
                if char in brackets:
                    stack.append((char, i))
                elif char in brackets.values():
                    if not stack:
                        errors.append(f"Unmatched closing character '{char}' at line {i}")
                    else:
                        opening, _ = stack.pop()
                        if char != brackets[opening]:
                            errors.append(f"Mismatched brackets: expected '{brackets[opening]}' but found '{char}' at line {i}")
            
            # Check for common syntax errors
            if line.count('--') % 2 != 0:
                errors.append(f"Unmatched connector '--' at line {i}")
            
            if '>>' in line and not any(x in line for x in ['->', '-->>']):
                errors.append(f"Invalid arrow syntax at line {i}")
                
            # Check for incomplete statements
            if line.strip().endswith(':') and i == len(lines):
                errors.append(f"Incomplete statement at line {i}")
        
        # Check for any remaining unclosed brackets or quotes
        while stack:
            char, line_num = stack.pop()
            errors.append(f"Unclosed '{char}' from line {line_num}")
            
        return errors

    def execute(self, mermaid_code: str) -> str:
        """Validates the Mermaid diagram syntax.
        
        Args:
            mermaid_code: The Mermaid diagram code to validate.
            
        Returns:
            A string containing validation results.
        """
        logger.info("Validating Mermaid diagram")
        
        # Remove markdown code block markers if present
        mermaid_code = mermaid_code.replace('```mermaid', '').replace('```', '').strip()
        
        # First run general validation
        errors = self._validate_general(mermaid_code)
        if errors:
            return "Validation errors found:\n" + "\n".join(f"- {error}" for error in errors)
        
        # Then run specific validation based on diagram type
        if mermaid_code.startswith('flowchart'):
            errors = self._validate_flowchart(mermaid_code)
        elif mermaid_code.startswith('sequenceDiagram'):
            errors = self._validate_sequence(mermaid_code)
        elif mermaid_code.startswith('gantt'):
            errors = self._validate_gantt(mermaid_code)
        elif mermaid_code.startswith('classDiagram'):
            errors = self._validate_class(mermaid_code)
        elif mermaid_code.startswith('stateDiagram'):
            errors = self._validate_state(mermaid_code)
        elif mermaid_code.startswith('erDiagram'):
            errors = self._validate_er(mermaid_code)
        elif mermaid_code.startswith('journey'):
            errors = self._validate_journey(mermaid_code)
        elif mermaid_code.startswith('pie'):
            errors = self._validate_pie(mermaid_code)
        elif mermaid_code.startswith('mindmap'):
            errors = self._validate_mindmap(mermaid_code)
        elif mermaid_code.startswith('timeline'):
            errors = self._validate_timeline(mermaid_code)
        elif mermaid_code.startswith('gitGraph'):
            errors = self._validate_git_graph(mermaid_code)
        else:
            # For unknown diagram types, we've already done general validation
            return "Mermaid diagram syntax is valid! (Note: Using general validation as specific diagram type is not recognized)"
            
        if errors:
            return "Validation errors found:\n" + "\n".join(f"- {error}" for error in errors)
        
        return "Mermaid diagram syntax is valid!"


if __name__ == "__main__":
    tool = MermaidValidatorTool()
    print(tool.to_markdown())
