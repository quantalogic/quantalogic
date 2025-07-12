"""
Template utilities module.

This module contains utility functions and constants for template handling.
"""

import os


# Templates directory path at the module level
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


def get_template_path(template_name: str) -> str:
    """Get the full path to a template file.
    
    Args:
        template_name: Name of the template file.
        
    Returns:
        Full path to the template file.
    """
    return os.path.join(TEMPLATES_DIR, template_name)
