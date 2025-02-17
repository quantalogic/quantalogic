"""Tool for converting markdown content to well-structured PDF documents.

Why this tool:
- Provides a standardized way to convert markdown to professional PDF documents
- Maintains consistent styling and formatting across documents
- Handles complex elements like diagrams, code blocks, and tables
- Supports customization through style configurations and templates
"""

import os
from typing import Dict, Optional
import json
from pathlib import Path

from loguru import logger
from pydantic import Field
import markdown
import mermaid
from bs4 import BeautifulSoup, Tag
import requests
from PIL import Image
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from quantalogic.tools.tool import Tool, ToolArgument


class MarkdownToPdfTool(Tool):
    """Converts markdown to professional PDF documents with advanced formatting."""

    name: str = "markdown_to_pdf_tool"
    description: str = (
        "Converts markdown to PDF with support for images, Mermaid diagrams, "
        "code blocks, tables, and advanced formatting."
    )
    need_validation: bool = True
    
    arguments: list = [
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
            description="Path for saving the PDF file",
            required=True,
            example="/path/to/output.pdf",
        ),
        ToolArgument(
            name="style_config",
            arg_type="string",
            description="JSON string with style settings (fonts, colors, sizes)",
            required=False,
            example='{"font_family": "Calibri", "font_size": "11pt"}',
        ),
        ToolArgument(
            name="css_template",
            arg_type="string",
            description="Optional CSS template for custom styling",
            required=False,
            example="path/to/custom.css",
        ),
    ]

    # Default style configuration
    DEFAULT_STYLES: Dict[str, str] = {
        "font_family": "Calibri, Arial, sans-serif",
        "font_size": "11pt",
        "heading_font": "Calibri, Arial, sans-serif",
        "code_font": "Consolas, monospace",
        "primary_color": "#0070C0",
        "link_color": "#0000FF",
        "line_height": "1.5",
        "margin": "2cm",
    }

    def _normalize_path(self, path: str) -> Path:
        """Convert path string to normalized Path object.
        
        Args:
            path: Input path string
            
        Returns:
            Normalized Path object
        """
        if path.startswith("~"):
            path = os.path.expanduser(path)
        return Path(path).resolve()

    def _parse_style_config(self, style_config: Optional[str]) -> Dict[str, str]:
        """Parse and validate style configuration.
        
        Args:
            style_config: JSON style configuration string
            
        Returns:
            Merged style configuration dictionary
        """
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

    def _generate_css(self, styles: Dict[str, str], css_template: Optional[str] = None) -> CSS:
        """Generate CSS for PDF styling.
        
        Args:
            styles: Style configuration dictionary
            css_template: Optional path to CSS template file
            
        Returns:
            WeasyPrint CSS object
        """
        base_css = f"""
            @page {{
                margin: {styles['margin']};
                @top-right {{
                    content: counter(page);
                }}
            }}
            body {{
                font-family: {styles['font_family']};
                font-size: {styles['font_size']};
                line-height: {styles['line_height']};
                color: #000000;
            }}
            h1, h2, h3, h4, h5, h6 {{
                font-family: {styles['heading_font']};
                color: {styles['primary_color']};
                margin-top: 1em;
                margin-bottom: 0.5em;
            }}
            pre, code {{
                font-family: {styles['code_font']};
                background-color: #f5f5f5;
                padding: 0.2em 0.4em;
                border-radius: 3px;
            }}
            a {{
                color: {styles['link_color']};
                text-decoration: none;
            }}
            img {{
                max-width: 100%;
                height: auto;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 1em 0;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }}
            th {{
                background-color: {styles['primary_color']};
                color: white;
            }}
        """

        font_config = FontConfiguration()
        css_list = [CSS(string=base_css, font_config=font_config)]
        
        if css_template:
            try:
                template_path = self._normalize_path(css_template)
                if template_path.exists():
                    css_list.append(CSS(filename=str(template_path), font_config=font_config))
            except Exception as e:
                logger.error(f"Error loading CSS template: {e}")

        return css_list

    def _process_mermaid_diagrams(self, html_content: str) -> str:
        """Convert Mermaid diagram code blocks to images in HTML.
        
        Args:
            html_content: HTML content with Mermaid code blocks
            
        Returns:
            HTML content with Mermaid diagrams converted to images
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        mermaid_blocks = soup.find_all('code', class_='language-mermaid')
        
        for block in mermaid_blocks:
            try:
                diagram = mermaid.generate_diagram(block.text)
                img_tag = soup.new_tag('img')
                img_tag['src'] = f"data:image/svg+xml;base64,{diagram}"
                block.parent.replace_with(img_tag)
            except Exception as e:
                logger.error(f"Error processing Mermaid diagram: {e}")
                
        return str(soup)

    def execute(self, **kwargs) -> str:
        """Execute the markdown to PDF conversion.
        
        Args:
            **kwargs: Tool arguments including markdown_content, output_path,
                     style_config, and css_template
        
        Returns:
            Success message with output path
        """
        try:
            markdown_content = kwargs['markdown_content']
            output_path = self._normalize_path(kwargs['output_path'])
            style_config = kwargs.get('style_config')
            css_template = kwargs.get('css_template')

            # Create output directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert markdown to HTML
            html_content = markdown.markdown(
                markdown_content,
                extensions=['extra', 'codehilite', 'tables', 'fenced_code']
            )

            # Process Mermaid diagrams
            html_content = self._process_mermaid_diagrams(html_content)

            # Generate CSS
            styles = self._parse_style_config(style_config)
            css_list = self._generate_css(styles, css_template)

            # Convert to PDF
            html = HTML(string=html_content)
            html.write_pdf(
                str(output_path),
                stylesheets=css_list,
                optimize_size=('fonts', 'images')
            )

            return f"Successfully created PDF at: {output_path}"

        except Exception as e:
            error_msg = f"Error converting markdown to PDF: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)


if __name__ == "__main__":
    # Example usage with error handling
    try:
        tool = MarkdownToPdfTool()
        result = tool.execute(
            markdown_content="# Test Document\n\nThis is a test.",
            output_path="test_output.pdf"
        )
        print(result)
    except Exception as e:
        print(f"Error: {e}")
