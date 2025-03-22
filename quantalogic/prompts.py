import os
from pathlib import Path
from typing import Dict

from jinja2 import Environment, FileSystemLoader
from loguru import logger

from quantalogic.version import get_version

# Map agent modes to their system prompt templates
SYSTEM_PROMPTS: Dict[str, str] = {
    "react": "system_prompt.j2",
    "chat": "chat_prompt.j2",
    "code": "code_system_prompt.j2",
    "code_enhanced": "code_2_system_prompt.j2",
    "legal": "legal_system_prompt.j2",
    "legal_enhanced": "legal_2_system_prompt.j2",
    "doc": "doc_system_prompt.j2",
    "default": "system_prompt.j2"  # Fallback template
}

def system_prompt(tools: str, environment: str, expertise: str = "", agent_mode: str = "react"):
    """System prompt for the ReAct chatbot with enhanced cognitive architecture.
    
    Uses a Jinja2 template from the prompts directory based on agent_mode.
    
    Args:
        tools: Available tools for the agent
        environment: Environment information
        expertise: Domain expertise information
        agent_mode: Mode to determine which system prompt to use
        
    Returns:
        str: The rendered system prompt
    """
    # Get the directory where this file is located
    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    
    # Set up Jinja2 environment
    template_dir = current_dir / 'prompts'
    env = Environment(loader=FileSystemLoader(template_dir))
    
    # Get template name based on agent mode, fallback to default if not found
    template_name = SYSTEM_PROMPTS.get(agent_mode, "system_prompt.j2")
    try:
        template = env.get_template(template_name)
    except Exception as e:
        logger.warning(f"Template {template_name} not found, using default")
        template = env.get_template("system_prompt.j2")
    
    # Render the template with the provided variables
    return template.render(
        version=get_version(),
        tools=tools,
        environment=environment,
        expertise=expertise
    )
