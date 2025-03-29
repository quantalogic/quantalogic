from jinja2 import Environment, FileSystemLoader

from .constants import TEMPLATE_DIR

# Centralized Jinja2 environment for template rendering
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), trim_blocks=True, lstrip_blocks=True)