"""Tool for interacting with Composio API services."""

import os
from typing import Any, Dict, Optional, List, Union
from datetime import datetime, timedelta
import json

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from composio import Action, ComposioToolSet
from quantalogic.tools.tool import Tool, ToolArgument


class ActionSchema(BaseModel):
    """Schema for Composio actions with validation."""
    name: str
    description: str
    parameters: Dict[str, Any]
    response: Dict[str, Any]
    version: str
    enabled: bool = True

    model_config = ConfigDict(extra="allow")


class ComposioTool(Tool):
    """Tool for executing Composio actions with proper validation and error handling."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    # Tool configuration
    name: str = Field(default="composio_tool")
    description: str = Field(default="")
    need_validation: bool = False
    arguments: list = Field(default_factory=list)

    # Composio-specific fields
    api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("COMPOSIO_API_KEY"),
        description="Composio API key for authentication",
    )
    action: str = Field(default="")  # Single action per tool instance
    schema: Optional[ActionSchema] = None
    toolset: Optional[ComposioToolSet] = None

    def __init__(
        self,
        action: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        need_validation: Optional[bool] = None,
        **data: Any
    ):
        """Initialize a Composio tool for a specific action.
        
        Args:
            action: Name of the Composio action to handle
            name: Custom name for this tool instance
            description: Custom description for this tool instance
            need_validation: Whether this specific instance needs validation
            **data: Additional data for tool initialization
        """
        logger.info(f"Initializing ComposioTool for action: {action}")
        
        # Set instance-specific attributes
        super().__init__(**data)
        self.action = action.upper()
        
        if name:
            self.name = name
        else:
            self.name = f"composio_{self.action.lower()}"
            
        # Validate API key
        if not self.api_key:
            logger.error("COMPOSIO_API_KEY environment variable is missing")
            raise ValueError("COMPOSIO_API_KEY environment variable is required")
            
        # Initialize toolset and get action schema
        self.toolset = ComposioToolSet(api_key=self.api_key)
        self._setup_action()
        
        # Set description if not provided
        if description:
            self.description = description
        
        if need_validation is not None:
            self.need_validation = need_validation

    def _setup_action(self) -> None:
        """Set up the Composio action with its schema and parameters."""
        try:
            # Get action schema
            (schema,) = self.toolset.get_action_schemas(actions=[self.action])
            schema_dict = schema.model_dump()
            
            # Store schema
            self.schema = ActionSchema(**schema_dict)
            
            # Set up tool description and arguments
            self._update_tool_info()
            
        except Exception as e:
            logger.error(f"Error setting up action {self.action}: {str(e)}")
            raise RuntimeError(f"Failed to set up action: {str(e)}")

    def _update_tool_info(self) -> None:
        """Update tool description and arguments based on the action schema."""
        if not self.schema:
            return
            
        # Get parameters info
        schema_dict = self.schema.model_dump()
        parameters = schema_dict.get("parameters", {})
        required_params = parameters.get("required", [])
        properties = parameters.get("properties", {})
        
        # Build parameter details
        param_details = []
        for param, param_info in properties.items():
            is_required = param in required_params
            param_type = param_info.get("type", "any")
            param_desc = param_info.get("description", "").split(".")[0]
            param_details.append(f"- {param}: ({param_type}{'*' if is_required else ''}) {param_desc}")
        
        # Update description if not explicitly set
        if not self.description:
            self.description = (
                f"Execute Composio action {self.action}:\n"
                f"Description: {self.schema.description}\n"
                f"Parameters:\n    " + "\n    ".join(param_details)
            )
        
        # Update arguments
        example_params = {}
        if properties:
            first_param = next(iter(properties))
            example = properties[first_param].get("examples", [""])[0]
            if example:
                example_params = {first_param: example}
        
        self.arguments = [
            ToolArgument(
                name="action_name",
                arg_type="string",
                description=f"Name of the action to execute (must be {self.action})",
                required=True,
                example=self.action,
            ),
            ToolArgument(
                name="parameters",
                arg_type="string",
                description="JSON string of parameters for the action",
                required=True,
                example=json.dumps(example_params),
            ),
        ]

    def execute(self, **kwargs: Any) -> str:
        """Execute the Composio action with the given parameters."""
        logger.info(f"Executing Composio action with kwargs: {kwargs}")
        
        try:
            action_name = kwargs.get("action_name", "").upper()
            parameters = kwargs.get("parameters")
            
            if not action_name or not parameters:
                raise ValueError("Both action_name and parameters are required")
                
            # Validate action name
            if action_name != self.action:
                raise ValueError(f"This tool only handles the {self.action} action")
            
            # Convert parameters to dict if string
            try:
                parameters_dict = json.loads(parameters) if isinstance(parameters, str) else parameters
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON parameters: {str(e)}")
            
            # Validate parameters if needed
            if self.need_validation and self.schema:
                schema_dict = self.schema.model_dump()
                parameters_data = schema_dict.get("parameters", {})
                required_params = parameters_data.get("required", [])
                missing_params = [p for p in required_params if p not in parameters_dict]
                if missing_params:
                    raise ValueError(f"Missing required parameters: {', '.join(missing_params)}")
            
            # Execute action
            logger.info(f"Executing {self.action} with parameters: {parameters_dict}")
            result = self.toolset.execute_action(
                action=Action(self.action),
                params=parameters_dict
            )
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error executing action: {str(e)}")
            raise RuntimeError(f"Failed to execute action: {str(e)}")


if __name__ == "__main__":
    # Example usage with custom settings
    weather_tool = ComposioTool(
        action="WEATHERMAP_WEATHER",
        name="weather_tool",
        description="Get weather information for a location"
    )
    
    email_tool = ComposioTool(
        action="GMAIL_SEND_EMAIL",
        name="email_tool",
        description="Send emails via Gmail",
        need_validation=True
    )