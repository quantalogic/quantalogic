"""Tool for converting markdown content to well-structured HTML documents.

Why this tool:
- Provides a standardized way to convert markdown to professional HTML documents
- Supports custom themes and styling through CSS
- Handles complex elements like diagrams, code blocks, and tables
- Includes responsive design and modern web features
- Can be used as an intermediate format for other conversions
"""

import json
import os
from pathlib import Path
from typing import ClassVar, Dict, List, Optional

import markdown
from bs4 import BeautifulSoup
from loguru import logger
from pygments.formatters import HtmlFormatter

from quantalogic.tools.tool import Tool, ToolArgument


class MarkdownToHtmlTool(Tool):
    """Converts markdown to professional HTML documents with advanced formatting."""

    model_config = {
        "arbitrary_types_allowed": True
    }
    
    name: str = "markdown_to_html_tool"
    description: str = (
        "Converts markdown to HTML with support for images, Mermaid diagrams, "
        "code blocks, tables, and advanced styling."
    )
    need_validation: bool = False
    
    arguments: List[ToolArgument] = [
        ToolArgument(
            name="markdown_content",
            arg_type="string",
            description="Markdown content with support for Mermaid, images, code blocks, and tables",
            required=True,
            example="# Title\n\nContent with **bold** text\n\n```mermaid\ngraph TD\nA-->B\n```",
        ),
        ToolArgument(
            name="output_path",
            arg_type="string",
            description="Path for saving the HTML file",
            required=True,
            example="/path/to/output.html",
        ),
        ToolArgument(
            name="style_config",
            arg_type="string",
            description="JSON string with style settings (fonts, colors, sizes)",
            required=False,
            example='{"theme": "light", "font_family": "Roboto"}',
        ),
        ToolArgument(
            name="create_assets",
            arg_type="boolean",
            description="Create assets directory for styles and images",
            required=False,
            default="true",
        ),
        ToolArgument(
            name="template",
            arg_type="string",
            description="Optional HTML template path",
            required=False,
            example="path/to/template.html",
        ),
    ]

    # Default style configuration
    DEFAULT_STYLES: ClassVar[Dict[str, str]] = {
        "theme": "light",
        "font_family": "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Ubuntu, sans-serif",
        "code_font": "Consolas, 'Source Code Pro', monospace",
        "primary_color": "#0070C0",
        "background_color": "#ffffff",
        "text_color": "#333333",
        "link_color": "#0366d6",
        "code_background": "#f6f8fa",
        "border_color": "#e1e4e8",
        "max_width": "900px",
    }

    # Default HTML template
    DEFAULT_TEMPLATE: ClassVar[str] = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>{styles}</style>
        {extra_head}
    </head>
    <body>
        <div class="container">
            {content}
        </div>
        {extra_body}
    </body>
    </html>
    """

    def _normalize_path(self, path: str) -> Path:
        """Convert path string to normalized Path object."""
        if path.startswith("~"):
            path = os.path.expanduser(path)
        return Path(path).resolve()

    def _parse_style_config(self, style_config: Optional[str]) -> Dict[str, str]:
        """Parse and validate style configuration."""
        try:
            if not style_config:
                return self.DEFAULT_STYLES.copy()
            
            custom_styles = json.loads(style_config)
            styles = self.DEFAULT_STYLES.copy()
            styles.update(custom_styles)
            return styles
        except json.JSONDecodeError as e:
            logger.error(f"Invalid style configuration JSON: {e}")
            return self.DEFAULT_STYLES.copy()

    def _generate_css(self, styles: Dict[str, str]) -> str:
        """Generate CSS based on style configuration."""
        dark_theme = styles.get('theme', 'light') == 'dark'
        if dark_theme:
            styles.update({
                'background_color': '#0d1117',
                'text_color': '#c9d1d9',
                'code_background': '#161b22',
                'border_color': '#30363d',
            })

        css = f"""
            :root {{
                color-scheme: {styles['theme']};
            }}
            body {{
                font-family: {styles['font_family']};
                line-height: 1.6;
                color: {styles['text_color']};
                background-color: {styles['background_color']};
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: {styles['max_width']};
                margin: 0 auto;
                padding: 2rem;
            }}
            h1, h2, h3, h4, h5, h6 {{
                color: {styles['primary_color']};
                margin-top: 1.5em;
                margin-bottom: 0.5em;
                font-weight: 600;
            }}
            a {{
                color: {styles['link_color']};
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
            pre, code {{
                font-family: {styles['code_font']};
                background-color: {styles['code_background']};
                border-radius: 6px;
            }}
            pre {{
                padding: 1rem;
                overflow-x: auto;
            }}
            code {{
                padding: 0.2em 0.4em;
            }}
            pre code {{
                padding: 0;
            }}
            img {{
                max-width: 100%;
                height: auto;
                border-radius: 6px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 1em 0;
            }}
            th, td {{
                border: 1px solid {styles['border_color']};
                padding: 8px;
                text-align: left;
            }}
            th {{
                background-color: {styles['code_background']};
            }}
            blockquote {{
                margin: 1em 0;
                padding-left: 1em;
                border-left: 4px solid {styles['primary_color']};
                color: {styles['text_color']};
            }}
            hr {{
                border: none;
                border-top: 1px solid {styles['border_color']};
                margin: 2em 0;
            }}
            .mermaid {{
                text-align: center;
            }}
            @media (max-width: 768px) {{
                .container {{
                    padding: 1rem;
                }}
            }}
        """
        
        return css + HtmlFormatter().get_style_defs('.highlight')

    def _process_mermaid_diagrams(self, html_content: str) -> str:
        """Convert Mermaid diagram code blocks to rendered diagrams."""
        soup = BeautifulSoup(html_content, 'html.parser')
        mermaid_blocks = soup.find_all('code', class_='language-mermaid')
        
        for block in mermaid_blocks:
            try:
                diagram_div = soup.new_tag('div')
                diagram_div['class'] = 'mermaid'
                diagram_div.string = block.text
                block.parent.replace_with(diagram_div)
            except Exception as e:
                logger.error(f"Error processing Mermaid diagram: {e}")
                
        return str(soup)

    def _setup_assets_directory(self, output_path: Path) -> Path:
        """Create and setup assets directory for styles and images."""
        assets_dir = output_path.parent / 'assets'
        assets_dir.mkdir(parents=True, exist_ok=True)
        return assets_dir

    def execute(self, **kwargs) -> str:
        """Execute the markdown to HTML conversion.
        
        Args:
            **kwargs: Tool arguments including markdown_content, output_path,
                     style_config, create_assets, and template
        
        Returns:
            Success message with output path
        """
        try:
            markdown_content = kwargs['markdown_content']
            output_path = self._normalize_path(kwargs['output_path'])
            style_config = kwargs.get('style_config')
            create_assets = kwargs.get('create_assets', True)
            template_path = kwargs.get('template')

            # Create output directory
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Setup assets if needed
            assets_dir = self._setup_assets_directory(output_path) if create_assets else None

            # Convert markdown to HTML
            html_content = markdown.markdown(
                markdown_content,
                extensions=[
                    'extra',
                    'codehilite',
                    'tables',
                    'fenced_code',
                    'toc',
                    'sane_lists',
                ]
            )

            # Process Mermaid diagrams
            html_content = self._process_mermaid_diagrams(html_content)

            # Generate styles
            styles = self._parse_style_config(style_config)
            css = self._generate_css(styles)

            # Load custom template if provided
            template = self.DEFAULT_TEMPLATE
            if template_path:
                try:
                    template_path = self._normalize_path(template_path)
                    with open(template_path, 'r') as f:
                        template = f.read()
                except Exception as e:
                    logger.error(f"Error loading template: {e}")

            # Extract title from content
            soup = BeautifulSoup(html_content, 'html.parser')
            title = soup.find('h1')
            title = title.text if title else 'Document'

            # Add Mermaid support
            extra_head = '''
                <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
                <script>
                    document.addEventListener('DOMContentLoaded', function() {
                        mermaid.initialize({startOnLoad: true});
                    });
                </script>
            '''

            # Generate final HTML
            final_html = template.format(
                title=title,
                styles=css,
                content=html_content,
                extra_head=extra_head,
                extra_body=''
            )

            # Write output file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_html)

            return f"Successfully created HTML at: {output_path}"

        except Exception as e:
            error_msg = f"Error converting markdown to HTML: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)


if __name__ == "__main__":
    # Example usage with error handling
    try:
        tool = MarkdownToHtmlTool()
        result = tool.execute(
            markdown_content="""
            # Sample Document
            
            ## Features
            - Modern, responsive design
            - Syntax highlighting
            - Mermaid diagrams
            
            ```mermaid
            graph TD
                A[Start] --> B[Process]
                B --> C[End]
            ```
            """,
            output_path="test_output.html",
            style_config='{"theme": "dark"}'
        )
        print(result)
    except Exception as e:
        print(f"Error: {e}")
