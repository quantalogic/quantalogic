from typing import List
from jinja2 import Environment

import yaml
from rich.console import Console
from rich.panel import Panel

console = Console()

async def config_show(shell, args: List[str]) -> str:
    """Display the current configuration with sanitized values."""
    config = shell.current_agent.config
    # Collect raw attributes (exclude private)
    raw = {k: v for k, v in vars(config).items() if not k.startswith('_')}
    # Recursively sanitize values to serializable primitives or repr
    def sanitize(val):
        # Primitive types
        if isinstance(val, (str, int, float, bool, type(None))):
            return val
        # Special-case Jinja2 Environment
        if isinstance(val, Environment):
            return "<jinja2.Environment>"
        # Nested structures
        if isinstance(val, dict):
            return {sanitize(k): sanitize(v) for k, v in val.items()}
        if isinstance(val, (list, tuple)):
            return [sanitize(v) for v in val]
        # Fallback for other non-serializable objects
        return repr(val)
    sanitized = {k: sanitize(v) for k, v in raw.items()}
    config_str = yaml.safe_dump(sanitized, default_flow_style=False)
    console.print(Panel(config_str, title="Current Configuration", border_style="blue"))
    return ""