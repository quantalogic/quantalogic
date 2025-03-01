"""Tool for converting markdown content to well-structured PDF documents.

Why this tool:
- Provides a standardized way to convert markdown to professional PDF documents
- Maintains consistent styling and formatting across documents
- Handles complex elements like diagrams, code blocks, and tables
- Supports customization through style configurations and templates
"""

import json
import os
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Union

import markdown
import mermaid
from bs4 import BeautifulSoup, Tag
from loguru import logger
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from quantalogic.tools.tool import Tool, ToolArgument


class MarkdownToPdfTool(Tool):
    """Converts markdown to professional PDF documents with advanced formatting."""

    model_config = {
        "arbitrary_types_allowed": True
    }
    
    name: str = "markdown_to_pdf_tool"
    description: str = (
        "Converts markdown to PDF with support for images, Mermaid diagrams, "
        "code blocks, tables, and advanced formatting."
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

    DEFAULT_STYLES: ClassVar[Dict[str, Union[str, int, Dict[str, str]]]] = {
        "font_family": "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
        "heading_font": "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
        "code_font": "'Source Code Pro', 'Consolas', monospace",
        "font_size": "12pt",
        "line_height": "1.6",
        "text_color": "#333333",
        "heading_color": "#2c3e50",
        "link_color": "#0366d6",
        "code_bg": "#f6f8fa",
        "code_color": "#24292e",
        "code_border": "#eaecef",
        "page_size": "A4",
        "margins": {
            "top": "2.5cm",
            "right": "2.5cm",
            "bottom": "2.5cm",
            "left": "2.5cm"
        }
    }

    DEFAULT_CSS: ClassVar[str] = """
        @import url('https://fonts.googleapis.com/css2?family=Source+Code+Pro&display=swap');

        @page {
            size: %(page_size)s;
            margin: %(margins_top)s %(margins_right)s %(margins_bottom)s %(margins_left)s;
        }

        body {
            font-family: %(font_family)s;
            font-size: %(font_size)s;
            line-height: %(line_height)s;
            color: %(text_color)s;
        }

        h1, h2, h3, h4, h5, h6 {
            font-family: %(heading_font)s;
            color: %(heading_color)s;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
        }

        a {
            color: %(link_color)s;
            text-decoration: none;
        }

        pre {
            background-color: %(code_bg)s;
            border: 1px solid %(code_border)s;
            border-radius: 6px;
            padding: 16px;
            overflow-x: auto;
            font-size: 85%%;
            line-height: 1.45;
            margin: 1em 0;
        }

        pre code {
            font-family: %(code_font)s;
            color: %(code_color)s;
            background: none;
            padding: 0;
            font-size: inherit;
            white-space: pre;
            word-break: normal;
            word-wrap: normal;
        }

        code {
            font-family: %(code_font)s;
            background-color: %(code_bg)s;
            border-radius: 3px;
            font-size: 85%%;
            margin: 0;
            padding: 0.2em 0.4em;
        }

        .mermaid-container {
            margin: 2em 0;
            padding: 1em;
            border: 1px solid %(code_border)s;
            border-radius: 8px;
            background-color: white;
        }

        .mermaid-code {
            margin-bottom: 1.5em;
        }

        .mermaid-code-header {
            font-weight: bold;
            color: #666;
            margin-bottom: 0.5em;
            font-size: 90%%;
            border-bottom: 1px solid #eee;
            padding-bottom: 0.3em;
        }

        .mermaid-code-content {
            background-color: %(code_bg)s;
            padding: 1em;
            border-radius: 6px;
            border: 1px solid %(code_border)s;
            font-family: %(code_font)s;
            font-size: 85%%;
            line-height: 1.45;
        }

        .mermaid-visualization {
            margin-top: 1.5em;
        }

        .mermaid-visualization-header {
            font-weight: bold;
            color: #666;
            margin-bottom: 0.5em;
            font-size: 90%%;
            border-bottom: 1px solid #eee;
            padding-bottom: 0.3em;
        }

        .mermaid-diagram {
            text-align: center;
            padding: 1em;
            background-color: white;
        }

        .mermaid-diagram img {
            max-width: 100%%;
            height: auto;
            margin: 0 auto;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-radius: 4px;
        }

        .diagram-caption {
            text-align: center;
            color: #666;
            font-style: italic;
            font-size: 90%%;
            margin-top: 0.5em;
        }

        /* Syntax Highlighting Styles */
        .highlight .hll { background-color: #ffc; }
        .highlight .c { color: #998; font-style: italic; }
        .highlight .err { color: #a61717; background-color: #e3d2d2; }
        .highlight .k { color: #000; font-weight: bold; }
        .highlight .o { color: #000; font-weight: bold; }
        .highlight .cm { color: #998; font-style: italic; }
        .highlight .cp { color: #999; font-weight: bold; font-style: italic; }
        .highlight .c1 { color: #998; font-style: italic; }
        .highlight .cs { color: #999; font-weight: bold; font-style: italic; }
        .highlight .gd { color: #000; background-color: #fdd; }
        .highlight .ge { color: #000; font-style: italic; }
        .highlight .gr { color: #a00; }
        .highlight .gh { color: #999; }
        .highlight .gi { color: #000; background-color: #dfd; }
        .highlight .go { color: #888; }
        .highlight .gp { color: #555; }
        .highlight .gs { font-weight: bold; }
        .highlight .gu { color: #aaa; }
        .highlight .gt { color: #a00; }
        .highlight .kc { color: #000; font-weight: bold; }
        .highlight .kd { color: #000; font-weight: bold; }
        .highlight .kn { color: #000; font-weight: bold; }
        .highlight .kp { color: #000; font-weight: bold; }
        .highlight .kr { color: #000; font-weight: bold; }
        .highlight .kt { color: #458; font-weight: bold; }
        .highlight .m { color: #099; }
        .highlight .s { color: #d01040; }
        .highlight .na { color: #008080; }
        .highlight .nb { color: #0086B3; }
        .highlight .nc { color: #458; font-weight: bold; }
        .highlight .no { color: #008080; }
        .highlight .nd { color: #3c5d5d; font-weight: bold; }
        .highlight .ni { color: #800080; }
        .highlight .ne { color: #900; font-weight: bold; }
        .highlight .nf { color: #900; font-weight: bold; }
        .highlight .nl { color: #900; font-weight: bold; }
        .highlight .nn { color: #555; }
        .highlight .nt { color: #000080; }
        .highlight .nv { color: #008080; }
        .highlight .ow { color: #000; font-weight: bold; }
        .highlight .w { color: #bbb; }
        .highlight .mf { color: #099; }
        .highlight .mh { color: #099; }
        .highlight .mi { color: #099; }
        .highlight .mo { color: #099; }
        .highlight .sb { color: #d01040; }
        .highlight .sc { color: #d01040; }
        .highlight .sd { color: #d01040; }
        .highlight .s2 { color: #d01040; }
        .highlight .se { color: #d01040; }
        .highlight .sh { color: #d01040; }
        .highlight .si { color: #d01040; }
        .highlight .sx { color: #d01040; }
        .highlight .sr { color: #009926; }
        .highlight .s1 { color: #d01040; }
        .highlight .ss { color: #990073; }
        .highlight .bp { color: #999; }
        .highlight .vc { color: #008080; }
        .highlight .vg { color: #008080; }
        .highlight .vi { color: #008080; }
        .highlight .il { color: #099; }

        img {
            max-width: 100%%;
            height: auto;
            display: block;
            margin: 1em auto;
        }

        blockquote {
            margin: 1em 0;
            padding-left: 1em;
            border-left: 4px solid #ddd;
            color: #666666;
        }

        table {
            width: 100%%;
            border-collapse: collapse;
            margin: 1em 0;
        }

        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }

        th {
            background-color: #f6f8fa;
        }

        @media print {
            body {
                background-color: white;
            }
            
            pre, code {
                white-space: pre-wrap;
                word-wrap: break-word;
            }
        }
    """

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
        # Unpack margins for CSS template
        if isinstance(styles.get('margins'), dict):
            margins = styles['margins']
            styles.update({
                'margins_top': margins.get('top', '2.5cm'),
                'margins_right': margins.get('right', '2.5cm'),
                'margins_bottom': margins.get('bottom', '2.5cm'),
                'margins_left': margins.get('left', '2.5cm')
            })

        base_css = self.DEFAULT_CSS % styles

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

    def _create_mermaid_code_section(self, soup: BeautifulSoup, code: str) -> Tag:
        """Create the code section of a Mermaid diagram.
        
        Args:
            soup: BeautifulSoup instance for HTML manipulation
            code: The Mermaid diagram code
            
        Returns:
            BeautifulSoup Tag containing the code section
        """
        code_section = soup.new_tag('div')
        code_section['class'] = 'mermaid-code'
        
        # Add header
        header = soup.new_tag('div')
        header['class'] = 'mermaid-code-header'
        header.string = 'Mermaid Diagram Code'
        code_section.append(header)
        
        # Add code content
        content = soup.new_tag('div')
        content['class'] = 'mermaid-code-content'
        code_tag = soup.new_tag('code')
        code_tag['class'] = 'language-mermaid'
        code_tag.string = code
        content.append(code_tag)
        code_section.append(content)
        
        return code_section

    def _create_mermaid_visualization(self, soup: BeautifulSoup, code: str) -> Tag:
        """Create the visualization section of a Mermaid diagram.
        
        Args:
            soup: BeautifulSoup instance for HTML manipulation
            code: The Mermaid diagram code to render
            
        Returns:
            BeautifulSoup Tag containing the visualization section
        """
        viz_section = soup.new_tag('div')
        viz_section['class'] = 'mermaid-visualization'
        
        # Add header
        header = soup.new_tag('div')
        header['class'] = 'mermaid-visualization-header'
        header.string = 'Diagram Visualization'
        viz_section.append(header)
        
        # Create diagram container
        diagram = soup.new_tag('div')
        diagram['class'] = 'mermaid-diagram'
        
        try:
            # Generate diagram
            svg_data = mermaid.generate_diagram(code)
            
            # Create and add image
            img = soup.new_tag('img')
            img['src'] = f"data:image/svg+xml;base64,{svg_data}"
            img['alt'] = 'Mermaid Diagram'
            diagram.append(img)
            
            # Add caption
            caption = soup.new_tag('div')
            caption['class'] = 'diagram-caption'
            caption.string = 'Generated diagram visualization'
            diagram.append(caption)
            
        except Exception as e:
            logger.error(f"Failed to generate Mermaid diagram: {e}")
            error = soup.new_tag('div')
            error['style'] = 'color: red; padding: 1em;'
            error.string = f'Error generating diagram: {str(e)}'
            diagram.append(error)
        
        viz_section.append(diagram)
        return viz_section

    def _process_mermaid_diagrams(self, html_content: str) -> str:
        """Convert Mermaid diagram code blocks to images in HTML while preserving the original code.
        
        Args:
            html_content: HTML content with Mermaid code blocks
            
        Returns:
            HTML content with Mermaid diagrams converted to images while keeping the code
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        mermaid_blocks = soup.find_all('code', class_='language-mermaid')
        
        for block in mermaid_blocks:
            try:
                # Create main container
                container = soup.new_tag('div')
                container['class'] = 'mermaid-container'
                
                # Add code section
                container.append(self._create_mermaid_code_section(soup, block.text))
                
                # Add visualization section
                container.append(self._create_mermaid_visualization(soup, block.text))
                
                # Replace original block
                parent = block.parent
                if parent.name == 'pre':
                    parent.replace_with(container)
                else:
                    block.replace_with(container)
                    
            except Exception as e:
                logger.error(f"Error processing Mermaid diagram block: {e}")
                continue
                
        return str(soup)

    def _process_code_blocks(self, html_content: str) -> str:
        """Process and syntax highlight code blocks.
        
        Args:
            html_content: HTML content with code blocks
            
        Returns:
            HTML content with syntax highlighted code blocks
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        code_blocks = soup.find_all('code', class_=lambda x: x and x.startswith('language-'))
        
        for block in code_blocks:
            try:
                # Get the language from the class
                lang = block['class'][0].replace('language-', '')
                if lang == 'mermaid':
                    continue  # Skip Mermaid blocks as they're handled separately
                
                # Get the appropriate lexer
                try:
                    lexer = get_lexer_by_name(lang)
                except ValueError:
                    lexer = TextLexer()
                
                # Highlight the code
                formatter = HtmlFormatter(style='github', cssclass='highlight')
                highlighted = highlight(block.text, lexer, formatter)
                
                # Create a new tag with the highlighted code
                new_tag = soup.new_tag('div')
                new_tag['class'] = 'highlight-wrapper'
                new_tag.append(BeautifulSoup(highlighted, 'html.parser'))
                
                # Replace the original code block
                if block.parent.name == 'pre':
                    block.parent.replace_with(new_tag)
                else:
                    block.replace_with(new_tag)
                    
            except Exception as e:
                logger.error(f"Error processing code block: {e}")
                continue
                
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

            # Convert markdown to HTML with extensions
            html_content = markdown.markdown(
                markdown_content,
                extensions=[
                    'extra',
                    'codehilite',
                    'tables',
                    'fenced_code',
                    'sane_lists',
                    'nl2br',
                    'attr_list'
                ]
            )

            # Process code blocks with syntax highlighting
            html_content = self._process_code_blocks(html_content)

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
