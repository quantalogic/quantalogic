"""
Template engine module.

This module contains the template rendering functionality.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound
from loguru import logger


class TemplateEngine:
    """Template rendering engine using Jinja2."""
    
    @staticmethod
    def load_prompt_from_file(prompt_file: str, context: Dict[str, Any]) -> str:
        """Load and render a Jinja2 template from an external file."""
        try:
            file_path = Path(prompt_file).resolve()
            directory = file_path.parent
            filename = file_path.name
            env = Environment(loader=FileSystemLoader(directory))
            template = env.get_template(filename)
            return template.render(**context)
        except TemplateNotFound as e:
            logger.error(f"Jinja2 template file '{prompt_file}' not found: {e}")
            raise ValueError(f"Prompt file '{prompt_file}' not found") from e
        except Exception as e:
            logger.error(f"Error loading or rendering prompt file '{prompt_file}': {e}")
            raise

    @staticmethod
    def render_template(template: str, template_file: Optional[str], context: Dict[str, Any]) -> str:
        """Render a Jinja2 template from either a string or an external file."""
        if template_file:
            return TemplateEngine.load_prompt_from_file(template_file, context)
        try:
            return Template(template).render(**context)
        except Exception as e:
            logger.error(f"Error rendering template: {e}")
            raise
