"""Tool for converting markdown content to well-structured DOCX documents.

Why this tool:
- Provides a standardized way to convert markdown to professional DOCX documents
- Maintains consistent styling and formatting across documents
- Handles complex elements like diagrams, code blocks, and tables
- Supports customization through templates and style configurations
"""

import os
from typing import Dict, Optional
import json
from pathlib import Path

from loguru import logger
from pydantic import Field
from python_docx import Document
from python_docx.shared import Pt, Inches, RGBColor
from python_docx.enum.text import WD_ALIGN_PARAGRAPH
from python_docx.enum.style import WD_STYLE_TYPE
import markdown
import mermaid
from bs4 import BeautifulSoup, Tag
import requests
from PIL import Image

from quantalogic.tools.tool import Tool, ToolArgument


class MarkdownToDocxTool(Tool):
    """Converts markdown to professional DOCX documents with advanced formatting."""

    name: str = "markdown_to_docx_tool"
    description: str = (
        "Converts markdown to DOCX with support for images, Mermaid diagrams, "
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
            description="Path for saving the DOCX file",
            required=True,
            example="/path/to/output.docx",
        ),
        ToolArgument(
            name="template_path",
            arg_type="string",
            description="Optional DOCX template path",
            required=False,
            example="/path/to/template.docx",
        ),
        ToolArgument(
            name="style_config",
            arg_type="string",
            description="JSON string with style settings (fonts, colors, sizes)",
            required=False,
            example='{"font_name": "Calibri", "font_size": 11}',
        ),
    ]

    # Default style configuration
    DEFAULT_STYLES: Dict[str, any] = {
        "font_name": "Calibri",
        "font_size": 11,
        "heading_font": "Calibri",
        "code_font": "Consolas",
        "primary_color": [0, 112, 192],
        "link_color": [0, 0, 255],
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

    def _parse_style_config(self, style_config: Optional[str]) -> Dict:
        """Parse and validate style configuration.
        
        Args:
            style_config: JSON style configuration string
            
        Returns:
            Merged style configuration dictionary
        """
        config = self.DEFAULT_STYLES.copy()
        if style_config:
            try:
                custom_styles = json.loads(style_config)
                config.update(custom_styles)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid style config, using defaults: {e}")
        return config

    def _apply_text_style(self, run, style: str, style_config: Dict) -> None:
        """Apply text styling to a run.
        
        Args:
            run: Document run to style
            style: Style to apply ('bold', 'italic', 'code', or 'link')
            style_config: Style configuration dictionary
        """
        if style == 'bold':
            run.bold = True
        elif style == 'italic':
            run.italic = True
        elif style == 'code':
            run.font.name = style_config["code_font"]
        elif style == 'link':
            run.font.color.rgb = RGBColor(*style_config["link_color"])
            run.underline = True

    def _handle_image(self, src: str) -> Optional[str]:
        """Process and save image from source.
        
        Args:
            src: Image source (URL or path)
            
        Returns:
            Path to processed image or None if failed
        """
        try:
            if src.startswith(('http://', 'https://')):
                response = requests.get(src)
                response.raise_for_status()
                path = f"image_{hash(src)}.{src.split('.')[-1]}"
                with open(path, 'wb') as f:
                    f.write(response.content)
                return path
            return src
        except Exception as e:
            logger.error(f"Failed to process image {src}: {e}")
            return None

    def _add_image_to_doc(self, doc: Document, image_path: str) -> None:
        """Add image to document with proper sizing.
        
        Args:
            doc: Target document
            image_path: Path to image file
        """
        try:
            paragraph = doc.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            img = Image.open(image_path)
            width = min(6.0, img.width / 96)  # Max 6 inches, convert from pixels
            doc.add_picture(image_path, width=Inches(width))
        except Exception as e:
            logger.error(f"Failed to add image {image_path}: {e}")

    def _process_mermaid(self, code: str) -> Optional[str]:
        """Generate image from Mermaid diagram code.
        
        Args:
            code: Mermaid diagram code
            
        Returns:
            Path to generated image or None if failed
        """
        try:
            output_file = f"diagram_{hash(code)}.png"
            mermaid.generate(code, output_file)
            return output_file
        except Exception as e:
            logger.error(f"Failed to generate diagram: {e}")
            return None

    def _process_element(self, doc: Document, element: Tag, style_config: Dict) -> None:
        """Process a single HTML element and add it to document.
        
        Args:
            doc: Target document
            element: HTML element to process
            style_config: Style configuration
        """
        try:
            if element.name in ['h1', 'h2', 'h3']:
                level = int(element.name[1])
                doc.add_heading(element.get_text(), level=level)
            
            elif element.name == 'p':
                if element.find('img'):
                    img_src = element.find('img').get('src', '')
                    if img_path := self._handle_image(img_src):
                        self._add_image_to_doc(doc, img_path)
                else:
                    self._process_paragraph(doc, element, style_config)
            
            elif element.name == 'pre':
                self._process_code_block(doc, element, style_config)
            
            elif element.name == 'table':
                self._process_table(doc, element)
                
        except Exception as e:
            logger.error(f"Failed to process element {element.name}: {e}")

    def _process_paragraph(self, doc: Document, element: Tag, style_config: Dict) -> None:
        """Process a paragraph element and add it to document.
        
        Args:
            doc: Target document
            element: HTML paragraph element
            style_config: Style configuration
        """
        try:
            p = doc.add_paragraph()
            for child in element.children:
                if child.name == 'strong':
                    run = p.add_run(child.get_text())
                    run.bold = True
                elif child.name == 'em':
                    run = p.add_run(child.get_text())
                    run.italic = True
                elif child.name == 'code':
                    run = p.add_run(child.get_text())
                    run.font.name = style_config["code_font"]
                elif child.name == 'a':
                    run = p.add_run(child.get_text())
                    run.font.color.rgb = RGBColor(*style_config["link_color"])
                    run.underline = True
                else:
                    p.add_run(str(child))
        except Exception as e:
            logger.error(f"Failed to process paragraph: {e}")

    def _process_code_block(self, doc: Document, element: Tag, style_config: Dict) -> None:
        """Process a code block element and add it to document.
        
        Args:
            doc: Target document
            element: HTML code block element
            style_config: Style configuration
        """
        try:
            code = element.find('code')
            if code:
                language = code.get('class', [None])[0]
                if code.text.strip().startswith('graph') or 'mermaid' in str(language):
                    # Handle Mermaid diagrams
                    diagram_path = self._process_mermaid(code.text)
                    if diagram_path:
                        self._add_image_to_doc(doc, diagram_path)
                else:
                    # Regular code block
                    paragraph = doc.add_paragraph(style='Code')
                    paragraph.add_run(code.text)
        except Exception as e:
            logger.error(f"Failed to process code block: {e}")

    def _process_table(self, doc: Document, element: Tag) -> None:
        """Process a table element and add it to document.
        
        Args:
            doc: Target document
            element: HTML table element
        """
        try:
            rows = element.find_all('tr')
            if rows:
                table = doc.add_table(rows=len(rows), cols=len(rows[0].find_all(['td', 'th'])))
                table.style = 'Table Grid'
                
                for i, row in enumerate(rows):
                    cells = row.find_all(['td', 'th'])
                    for j, cell in enumerate(cells):
                        table.cell(i, j).text = cell.get_text().strip()
        except Exception as e:
            logger.error(f"Failed to process table: {e}")

    def execute(
        self,
        markdown_content: str,
        output_path: str,
        template_path: Optional[str] = None,
        style_config: Optional[str] = None,
    ) -> str:
        """Convert markdown to DOCX format.

        Args:
            markdown_content: Markdown content to convert
            output_path: Output DOCX file path
            template_path: Optional template path
            style_config: Optional style configuration

        Returns:
            Success message with output path

        Raises:
            ValueError: If content is empty or paths invalid
        """
        if not markdown_content.strip():
            raise ValueError("Markdown content cannot be empty")

        try:
            # Setup paths and document
            output_path = self._normalize_path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            doc = Document(template_path) if template_path else Document()
            style_config = self._parse_style_config(style_config)

            # Convert markdown to HTML
            html = markdown.markdown(
                markdown_content,
                extensions=['fenced_code', 'tables', 'attr_list', 'md_in_html']
            )
            
            # Process elements
            soup = BeautifulSoup(html, 'html.parser')
            for element in soup.find_all():
                self._process_element(doc, element, style_config)

            # Save document
            doc.save(str(output_path))
            return f"Successfully created DOCX: {output_path}"
            
        except Exception as e:
            logger.error(f"Failed to convert markdown: {e}")
            raise ValueError(f"Conversion failed: {str(e)}")


if __name__ == "__main__":
    # Example usage with error handling
    try:
        tool = MarkdownToDocxTool()
        
        # Test markdown with various features
        markdown_content = """
        # Document Title
        
        ## Code Example
        ```python
        def greet(name: str) -> str:
            return f"Hello, {name}!"
        ```
        
        ## System Diagram
        ```mermaid
        graph TD
            A[Start] --> B[Process]
            B --> C[End]
        ```
        
        ## Feature Status
        | Feature | Status |
        |---------|--------|
        | Auth    | Done   |
        | API     | WIP    |
        """
        
        result = tool.execute(
            markdown_content=markdown_content,
            output_path="./example.docx",
            style_config='{"font_name": "Arial"}'
        )
        print(result)
        
    except Exception as e:
        logger.error(f"Example failed: {e}")
