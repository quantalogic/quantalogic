"""Tool for rendering Jinja templates with inline template string."""

from typing import Any, Dict, Optional

from jinja2 import Template
from loguru import logger
from pydantic import Field

from quantalogic.tools.tool import Tool, ToolArgument


class JinjaTool(Tool):
    """Tool for rendering Jinja templates with inline template string."""

    name: str = "jinja_tool"
    description: str = (
        "Renders an inline Jinja2 template string with a predefined context.\n"
        "You can use the variables in the template just as var1, var2, etc.\n"
        "Useful for simple calculations or string operations.\n"
    )
    arguments: list = [
        ToolArgument(
            name="inline_template",
            arg_type="string",
            description="Inline Jinja2 template string to render. Has access to variables in the context.",
            required=True,
            example="Hello, {{ var1 }}! You have {{ var2|length }} items.",
        ),
    ]
    need_variables: bool = True

    # Add context as a field with a default empty dictionary
    context: Dict[str, Any] = Field(default_factory=dict)

    def __init__(self):
        """
        Initialize JinjaTool with optional context.

        Args:
            context (dict, optional): Context dictionary for template rendering.
        """
        super().__init__()

    def execute(self, inline_template: str, variables: Optional[Dict[str, Any]] = None) -> str:
        """
        Render an inline Jinja2 template with the predefined context.

        Args:
            inline_template (str): Inline template string to render.
            variables (dict, optional): Additional variables to include in the context.

        Returns:
            str: Rendered template content.
        """
        try:
            # Create Jinja2 template
            template = Template(inline_template)

            context = {}
            if variables:
                context.update(variables)

            rendered_content = template.render(**context)

            logger.info("Successfully rendered inline Jinja template")
            return rendered_content

        except Exception as e:
            logger.error(f"Error rendering Jinja template: {e}")
            raise


if __name__ == "__main__":
    # Example of using JinjaTool with variables
    tool = JinjaTool(context={"var1": "World", "var2": 42, "var3": ["apple", "banana", "cherry"]})

    # Inline template demonstrating variable usage
    template = "Hello {{ var1 }}! The answer is {{ var2 }}. Fruits: {% for fruit in var3 %}{{ fruit }}{% if not loop.last %}, {% endif %}{% endfor %}."

    # Render the template
    result = tool.execute(template)
    print("Rendered Template:")
    print(result)

    # Print the tool's markdown representation
    print("\nTool Markdown:")
    print(tool.to_markdown())
