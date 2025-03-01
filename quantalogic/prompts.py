import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from quantalogic.version import get_version


def system_prompt(tools: str, environment: str, expertise: str = ""):
    """System prompt for the ReAct chatbot with enhanced cognitive architecture.
    
    Uses a Jinja2 template from the prompts directory.
    
    Args:
        tools: Available tools for the agent
        environment: Environment information
        expertise: Domain expertise information
        
    Returns:
        str: The rendered system prompt
    """
    # Get the directory where this file is located
    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    
    # Set up Jinja2 environment
    template_dir = current_dir / 'prompts'
    env = Environment(loader=FileSystemLoader(template_dir))
    
    # Load the template
    template = env.get_template('system_prompt.j2')
    
    # Render the template with the provided variables
    return template.render(
        version=get_version(),
        tools=tools,
        environment=environment,
        expertise=expertise
    )
