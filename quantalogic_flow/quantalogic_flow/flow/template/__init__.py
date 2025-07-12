"""Template module initialization."""

from .engine import TemplateEngine
from .utils import TEMPLATES_DIR, get_template_path

__all__ = ["TemplateEngine", "TEMPLATES_DIR", "get_template_path"]
