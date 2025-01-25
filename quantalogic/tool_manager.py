"""Tool dictionary for the agent."""

from loguru import logger
from pydantic import BaseModel

from quantalogic.tools.tool import Tool


class ToolManager(BaseModel):
    """Tool dictionary for the agent."""

    tools: dict[str, Tool] = {}

    def tool_names(self) -> list[str]:
        """Get the names of all tools in the tool dictionary."""
        logger.debug("Getting tool names")
        return list(self.tools.keys())

    def add(self, tool: Tool):
        """Add a tool to the tool dictionary."""
        logger.debug(f"Adding tool: {tool.name} to tool dictionary")
        self.tools[tool.name] = tool

    def add_list(self, tools: list[Tool]):
        """Add a list of tools to the tool dictionary."""
        logger.debug(f"Adding {len(tools)} tools to tool dictionary")
        for tool in tools:
            self.add(tool)

    def remove(self, tool_name: str) -> bool:
        """Remove a tool from the tool dictionary."""
        logger.debug(f"Removing tool: {tool_name} from tool dictionary")
        del self.tools[tool_name]
        return True

    def get(self, tool_name: str) -> Tool:
        """Get a tool from the tool dictionary."""
        logger.debug(f"Getting tool: {tool_name} from tool dictionary")
        return self.tools[tool_name]

    def list(self):
        """List all tools in the tool dictionary."""
        logger.debug("Listing all tools")
        return list(self.tools.keys())

    def execute(self, tool_name: str, **kwargs) -> str:
        """Execute a tool from the tool dictionary."""
        logger.debug(f"Executing tool: {tool_name} with arguments: {kwargs}")
        try:
            result = self.tools[tool_name].execute(**kwargs)
            logger.debug(f"Tool {tool_name} execution completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            raise

    def to_markdown(self):
        """Create a comprehensive Markdown representation of the tool dictionary."""
        logger.debug("Creating Markdown representation of tool dictionary")
        markdown = ""
        index: int = 1
        for tool_name, tool in self.tools.items():
            # use the tool's to_markdown method
            markdown += f"### {index}. {tool_name}\n"
            markdown += tool.to_markdown()
            markdown += "\n"
            index += 1
        return markdown

    def _convert_kwargs_types(self, tool_name: str, **kwargs) -> dict:
        """Convert kwargs values to their expected types based on tool definition.
        
        Args:
            tool_name: Name of the tool to get argument types from
            **kwargs: Input arguments to convert
            
        Returns:
            Dictionary of converted arguments
            
        Raises:
            ValueError: If type conversion fails for a required argument
        """
        tool = self.tools[tool_name]
        converted = {}
        
        for arg in tool.arguments:
            if arg.name in kwargs:
                try:
                    if arg.arg_type == "int":
                        converted[arg.name] = int(kwargs[arg.name])
                    elif arg.arg_type == "float":
                        converted[arg.name] = float(kwargs[arg.name])
                    elif arg.arg_type == "boolean":
                        val = str(kwargs[arg.name]).lower()
                        converted[arg.name] = val in ("true", "1", "yes", "y")
                    else:  # string
                        converted[arg.name] = str(kwargs[arg.name])
                except (ValueError, TypeError) as e:
                    if arg.required:
                        raise ValueError(
                            f"Failed to convert required argument '{arg.name}' to {arg.arg_type}: {str(e)}"
                        )
                    logger.warning(
                        f"Failed to convert optional argument '{arg.name}' to {arg.arg_type}: {str(e)}"
                    )
                    converted[arg.name] = kwargs[arg.name]  # keep original value
                
        return converted
