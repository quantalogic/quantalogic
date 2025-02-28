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

    def validate_and_convert_arguments(self, tool_name: str, provided_args: dict) -> dict:
        """Validates and converts arguments based on tool definition.

        Args:
            tool_name: Name of the tool to validate against
            provided_args: Dictionary of arguments to validate

        Returns:
            Dictionary of converted arguments with proper types

        Raises:
            ValueError: For missing/invalid arguments or conversion errors
        """
        tool = self.get(tool_name)
        converted_args = {}
        type_conversion = {
            "string": lambda x: str(x),
            "int": lambda x: int(x),
            "float": lambda x: float(x),
            "bool": lambda x: str(x).lower() in ["true", "1", "yes"],
        }

        for arg_def in tool.arguments:
            arg_name = arg_def.name
            arg_type = arg_def.arg_type
            required = arg_def.required
            default = arg_def.default

            # Handle missing arguments
            if arg_name not in provided_args:
                if required:
                    raise ValueError(f"Missing required argument: {arg_name}")
                if default is None:
                    continue  # Skip optional args with no default
                provided_args[arg_name] = default

            value = provided_args[arg_name]

            # Handle empty string for non-string types by replacing with default if available
            if arg_type != "string" and isinstance(value, str) and value.strip() == "" and default is not None:
                logger.debug(f"Replaced empty string for argument {arg_name} with default value {default}")
                value = default
                provided_args[arg_name] = value  # Update to ensure validation uses the default

            # Type conversion
            if arg_type in type_conversion:
                try:
                    converted = type_conversion[arg_type](value)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid value '{value}' for {arg_name} ({arg_type}): {str(e)}")
                converted_args[arg_name] = converted
            else:
                converted_args[arg_name] = value  # Unknown type, pass through

        # Validate extra arguments
        extra_args = set(provided_args.keys()) - {a.name for a in tool.arguments}
        if extra_args:
            raise ValueError(f"Unexpected arguments: {', '.join(extra_args)}")

        return converted_args
        """Validates and converts arguments based on tool definition.
        
        Args:
            tool_name: Name of the tool to validate against
            provided_args: Dictionary of arguments to validate
            
        Returns:
            Dictionary of converted arguments with proper types
            
        Raises:
            ValueError: For missing/invalid arguments or conversion errors
        """
        tool = self.get(tool_name)
        converted_args = {}
        type_conversion = {
            "string": lambda x: str(x),
            "int": lambda x: int(x),
            "float": lambda x: float(x),
            "bool": lambda x: str(x).lower() in ["true", "1", "yes"],
        }

        for arg_def in tool.arguments:
            arg_name = arg_def.name
            arg_type = arg_def.arg_type
            required = arg_def.required
            default = getattr(arg_def, "default", None)

            # Handle missing arguments
            if arg_name not in provided_args:
                if required:
                    raise ValueError(f"Missing required argument: {arg_name}")
                if default is None:
                    continue  # Skip optional args with no default
                provided_args[arg_name] = default

            # Type conversion
            value = provided_args[arg_name]
            if arg_type in type_conversion:
                try:
                    converted = type_conversion[arg_type](value)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid value '{value}' for {arg_name} ({arg_type}): {str(e)}")
                converted_args[arg_name] = converted
            else:
                converted_args[arg_name] = value  # Unknown type, pass through

        # Validate extra arguments
        extra_args = set(provided_args.keys()) - {a.name for a in tool.arguments}
        if extra_args:
            raise ValueError(f"Unexpected arguments: {', '.join(extra_args)}")

        return converted_args
