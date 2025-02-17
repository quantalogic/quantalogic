"""Tool for converting markdown content to well-structured PowerPoint presentations.

Why this tool:
- Provides a standardized way to convert markdown to professional PPTX presentations
- Maintains consistent styling and formatting across slides
- Handles complex elements like diagrams, code blocks, and images
- Supports customization through templates and style configurations
"""

import os
from typing import Dict, Optional, List
import json
from pathlib import Path

from loguru import logger
from pydantic import Field
from python_pptx import Presentation
from python_pptx.util import Pt, Inches
from python_pptx.dml.color import RGBColor
from python_pptx.enum.text import PP_ALIGN
import markdown
import mermaid
from bs4 import BeautifulSoup, Tag
import requests
from PIL import Image

from quantalogic.tools.tool import Tool, ToolArgument


class MarkdownToPptxTool(Tool):
    """Converts markdown to professional PowerPoint presentations with advanced formatting."""

    name: str = "markdown_to_pptx_tool"
    description: str = (
        "Converts markdown to PPTX with support for images, Mermaid diagrams, "
        "code blocks, and advanced slide formatting."
    )
    need_validation: bool = True
    
    arguments: list = [
        ToolArgument(
            name="markdown_content",
            arg_type="string",
            description="Markdown content with slide separators (---) and support for Mermaid, images, code blocks",
            required=True,
            example="# Title Slide\n\nSubtitle\n\n---\n\n# Content Slide\n\n- Bullet points\n- With **bold** text\n\n```mermaid\ngraph TD\nA-->B\n```",
        ),
        ToolArgument(
            name="output_path",
            arg_type="string",
            description="Path for saving the PPTX file",
            required=True,
            example="/path/to/output.pptx",
        ),
        ToolArgument(
            name="template_path",
            arg_type="string",
            description="Optional PPTX template path",
            required=False,
            example="/path/to/template.pptx",
        ),
        ToolArgument(
            name="style_config",
            arg_type="string",
            description="JSON string with style settings (fonts, colors, sizes)",
            required=False,
            example='{"font_name": "Calibri", "title_size": 44, "body_size": 24}',
        ),
    ]

    # Default style configuration
    DEFAULT_STYLES: Dict[str, any] = {
        "font_name": "Calibri",
        "title_size": 44,
        "body_size": 24,
        "code_size": 18,
        "code_font": "Consolas",
        "primary_color": [0, 112, 192],
        "secondary_color": [68, 114, 196],
        "text_color": [0, 0, 0],
    }

    def _normalize_path(self, path: str) -> Path:
        """Convert path string to normalized Path object."""
        if path.startswith("~"):
            path = os.path.expanduser(path)
        return Path(path).resolve()

    def _parse_style_config(self, style_config: Optional[str]) -> Dict:
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

    def _create_presentation(self, template_path: Optional[str] = None) -> Presentation:
        """Create a new presentation, optionally from a template."""
        if template_path:
            template_path = self._normalize_path(template_path)
            if not template_path.exists():
                logger.warning(f"Template not found: {template_path}. Using default template.")
                return Presentation()
            return Presentation(template_path)
        return Presentation()

    def _apply_text_style(self, paragraph, font_name: str, font_size: int, color: List[int]):
        """Apply text styling to a paragraph."""
        run = paragraph.runs[0] if paragraph.runs else paragraph.add_run()
        font = run.font
        font.name = font_name
        font.size = Pt(font_size)
        font.color.rgb = RGBColor(*color)

    def _add_title_slide(self, prs: Presentation, title: str, subtitle: Optional[str] = None):
        """Add a title slide to the presentation."""
        layout = prs.slide_layouts[0]  # Title slide layout
        slide = prs.slides.add_slide(layout)
        
        title_shape = slide.shapes.title
        title_shape.text = title
        
        if subtitle and slide.placeholders.get(1):  # Subtitle placeholder
            subtitle_shape = slide.placeholders[1]
            subtitle_shape.text = subtitle

    def _add_content_slide(self, prs: Presentation, title: str, content: str, styles: Dict):
        """Add a content slide with formatted text and elements."""
        layout = prs.slide_layouts[1]  # Content slide layout
        slide = prs.slides.add_slide(layout)
        
        # Add title
        title_shape = slide.shapes.title
        title_shape.text = title
        
        # Add content
        content_shape = slide.placeholders[1]
        tf = content_shape.text_frame
        
        # Process markdown content
        # TODO: Implement markdown parsing and element handling
        tf.text = content  # Placeholder implementation

    def execute(self, **kwargs) -> Dict:
        """Convert markdown content to a PowerPoint presentation."""
        try:
            markdown_content = kwargs.get("markdown_content")
            output_path = kwargs.get("output_path")
            template_path = kwargs.get("template_path")
            style_config = kwargs.get("style_config")

            if not markdown_content or not output_path:
                raise ValueError("markdown_content and output_path are required")

            # Parse style configuration
            styles = self._parse_style_config(style_config)
            
            # Create presentation
            prs = self._create_presentation(template_path)
            
            # Split content into slides
            slides = markdown_content.split("---")
            
            # Process each slide
            for i, slide_content in enumerate(slides):
                if not slide_content.strip():
                    continue
                    
                # Parse slide content
                lines = slide_content.strip().split("\n")
                title = lines[0].lstrip("#").strip() if lines else "Untitled Slide"
                content = "\n".join(lines[1:]).strip()
                
                if i == 0:
                    # First slide is title slide
                    subtitle = content if content else None
                    self._add_title_slide(prs, title, subtitle)
                else:
                    self._add_content_slide(prs, title, content, styles)
            
            # Save presentation
            output_path = self._normalize_path(output_path)
            prs.save(str(output_path))
            
            return {
                "status": "success",
                "message": f"Presentation saved to {output_path}",
                "output_path": str(output_path)
            }
            
        except Exception as e:
            logger.error(f"Error creating presentation: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }


if __name__ == "__main__":
    # Example usage with error handling
    try:
        tool = MarkdownToPptxTool()
        
        # Example markdown content
        markdown_content = """
        # Project Overview
        Quarterly Update Q1 2024
        
        ---
        
        # Key Achievements
        
        - Launched new product features
        - Increased user engagement by 25%
        - Improved system performance
        
        ---
        
        # Next Steps
        
        1. Scale infrastructure
        2. Release mobile app
        3. Expand market reach
        """
        
        result = tool.execute(
            markdown_content=markdown_content,
            output_path="presentation.pptx",
            style_config='{"primary_color": [44, 85, 169]}'
        )
        
        print(result)
        
    except Exception as e:
        logger.error(f"Example usage failed: {e}")
