"""Tool for converting markdown content to Jupyter Notebook format.

Why this tool:
- Provides a standardized way to convert markdown to interactive notebooks
- Creates executable code cells from code blocks
- Supports rich media and interactive elements
- Maintains metadata and cell execution order
- Perfect for tutorials, documentation, and educational content
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import mermaid
import nbformat
from loguru import logger
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

from quantalogic.tools.tool import Tool, ToolArgument


class MarkdownToIpynbTool(Tool):
    """Converts markdown to Jupyter Notebooks with interactive elements."""

    name: str = "markdown_to_ipynb_tool"
    description: str = (
        "Converts markdown to Jupyter Notebook format with support for "
        "executable code cells, rich media, and interactive elements."
    )
    need_validation: bool = False
    
    arguments: list = [
        ToolArgument(
            name="markdown_content",
            arg_type="string",
            description="Markdown content with code blocks and optional cell metadata",
            required=True,
            example='# Title\n\nText\n\n```python\nprint("Hello")\n```',
        ),
        ToolArgument(
            name="output_path",
            arg_type="string",
            description="Path for saving the notebook file",
            required=True,
            example="/path/to/output.ipynb",
        ),
        ToolArgument(
            name="kernel_name",
            arg_type="string",
            description="Jupyter kernel name (e.g., python3, ir)",
            required=False,
            default="python3",
        ),
        ToolArgument(
            name="metadata",
            arg_type="string",
            description="JSON string with notebook metadata",
            required=False,
            example='{"authors": ["John Doe"], "license": "MIT"}',
        ),
    ]

    # Default notebook metadata
    DEFAULT_METADATA: Dict[str, Any] = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "codemirror_mode": {
                "name": "ipython",
                "version": 3
            },
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.8.0"
        }
    }

    def _normalize_path(self, path: str) -> Path:
        """Convert path string to normalized Path object."""
        if path.startswith("~"):
            path = os.path.expanduser(path)
        return Path(path).resolve()

    def _parse_metadata(self, metadata: Optional[str]) -> Dict[str, Any]:
        """Parse and validate notebook metadata."""
        try:
            if not metadata:
                return self.DEFAULT_METADATA.copy()
            
            custom_metadata = json.loads(metadata)
            metadata = self.DEFAULT_METADATA.copy()
            metadata.update(custom_metadata)
            return metadata
        except json.JSONDecodeError as e:
            logger.error(f"Invalid metadata JSON: {e}")
            return self.DEFAULT_METADATA.copy()

    def _process_mermaid_diagrams(self, content: str) -> str:
        """Convert Mermaid diagram code blocks to embedded SVG."""
        def replace_mermaid(match):
            try:
                diagram = mermaid.generate_diagram(match.group(1))
                return f"```html\n<div class='mermaid-diagram'>\n{diagram}\n</div>\n```"
            except Exception as e:
                logger.error(f"Error processing Mermaid diagram: {e}")
                return match.group(0)
        
        pattern = r'```mermaid\n(.*?)\n```'
        return re.sub(pattern, replace_mermaid, content, flags=re.DOTALL)

    def _extract_cell_metadata(self, content: str) -> Dict[str, Any]:
        """Extract cell metadata from special comments."""
        metadata = {}
        lines = content.split('\n')
        
        # Look for metadata in comments at the start of the cell
        for line in lines:
            if line.startswith('# @'):
                try:
                    key, value = line[3:].split(':', 1)
                    metadata[key.strip()] = json.loads(value.strip())
                except Exception:
                    continue
            else:
                break
                
        return metadata

    def _split_into_cells(self, content: str) -> List[Dict[str, Any]]:
        """Split markdown content into notebook cells."""
        cells = []
        current_cell = []
        in_code_block = False
        code_language = None
        
        lines = content.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Check for code block start
            if line.startswith('```'):
                if not in_code_block:
                    # If we have accumulated markdown content, save it
                    if current_cell:
                        cells.append({
                            'type': 'markdown',
                            'content': '\n'.join(current_cell)
                        })
                        current_cell = []
                    
                    # Start new code block
                    in_code_block = True
                    code_language = line[3:].strip()
                    current_cell = []
                    i += 1
                    
                    # Look ahead for metadata comments
                    code_metadata = {}
                    while i < len(lines) and lines[i].startswith('# @'):
                        try:
                            key, value = lines[i][3:].split(':', 1)
                            code_metadata[key.strip()] = json.loads(value.strip())
                        except Exception:
                            current_cell.append(lines[i])
                        i += 1
                    continue
                else:
                    # End of code block
                    in_code_block = False
                    cells.append({
                        'type': 'code',
                        'content': '\n'.join(current_cell),
                        'language': code_language,
                        'metadata': code_metadata if 'code_metadata' in locals() else {}
                    })
                    current_cell = []
                    code_metadata = {}
            else:
                current_cell.append(line)
            
            i += 1
        
        # Add any remaining content
        if current_cell:
            cells.append({
                'type': 'markdown' if not in_code_block else 'code',
                'content': '\n'.join(current_cell),
                'language': code_language if in_code_block else None,
                'metadata': code_metadata if in_code_block and 'code_metadata' in locals() else {}
            })
            
        return cells

    def execute(self, **kwargs) -> str:
        """Execute the markdown to Jupyter Notebook conversion.
        
        Args:
            **kwargs: Tool arguments including markdown_content, output_path,
                     kernel_name, and metadata
        
        Returns:
            Success message with output path
        """
        try:
            markdown_content = kwargs['markdown_content']
            output_path = self._normalize_path(kwargs['output_path'])
            kernel_name = kwargs.get('kernel_name', 'python3')
            metadata_str = kwargs.get('metadata')

            # Create output directory
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Process Mermaid diagrams
            content = self._process_mermaid_diagrams(markdown_content)

            # Split content into cells
            cells = self._split_into_cells(content)

            # Create notebook
            nb = new_notebook()

            # Set notebook metadata
            metadata = self._parse_metadata(metadata_str)
            metadata['kernelspec']['name'] = kernel_name
            metadata['kernelspec']['display_name'] = kernel_name.capitalize()
            nb.metadata = metadata

            # Add cells to notebook
            for cell in cells:
                if cell['type'] == 'markdown':
                    nb.cells.append(new_markdown_cell(
                        cell['content']
                    ))
                else:
                    # Create code cell with metadata
                    code_cell = new_code_cell(
                        cell['content'],
                        metadata=cell['metadata']
                    )
                    nb.cells.append(code_cell)

            # Write notebook file
            with open(output_path, 'w', encoding='utf-8') as f:
                nbformat.write(nb, f)

            return f"Successfully created Jupyter Notebook at: {output_path}"

        except Exception as e:
            error_msg = f"Error converting markdown to notebook: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)


if __name__ == "__main__":
    # Example usage with error handling
    try:
        tool = MarkdownToIpynbTool()
        result = tool.execute(
            markdown_content="""
            # Interactive Python Tutorial
            
            This notebook demonstrates various Python concepts.
            
            ## Basic Operations
            
            Let's start with a simple calculation:
            
            ```python
            # @tags: ["basic-math"]
            # Calculate the sum of numbers
            result = sum(range(10))
            print(f"Sum: {result}")
            ```
            
            ## Data Visualization
            
            Now let's create a simple plot:
            
            ```python
            # @tags: ["visualization"]
            import matplotlib.pyplot as plt
            import numpy as np
            
            x = np.linspace(0, 10, 100)
            y = np.sin(x)
            
            plt.plot(x, y)
            plt.title("Sine Wave")
            plt.show()
            ```
            
            ## System Architecture
            
            Here's a diagram of our system:
            
            ```mermaid
            graph TD
                A[Input] --> B[Process]
                B --> C[Output]
                B --> D[Log]
            ```
            """,
            output_path="tutorial.ipynb",
            metadata='{"authors": ["Jane Doe"], "description": "Interactive Python Tutorial"}'
        )
        print(result)
    except Exception as e:
        print(f"Error: {e}")
