"""Tool for interacting with Composio API services.

This tool provides a wrapper around Composio's API functionality, allowing
integration with various Composio services while maintaining type safety
and proper error handling.
"""

import os
from typing import Any, Dict, Optional, List, Callable

from loguru import logger
from pydantic import ConfigDict, Field

from composio import Action, ComposioToolSet
from composio.client.collections import ConnectedAccountModel
from composio.constants import DEFAULT_ENTITY_ID
from composio.utils.shared import json_schema_to_model
from quantalogic.tools.tool import Tool, ToolArgument


class ComposioTool(Tool):
    """Tool for executing Composio actions with proper validation and error handling."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    need_validation: bool = False
    name: str = Field(default="composio_tool")
    description: str = Field(
        default="Executes Composio actions with proper validation and error handling"
    )
    arguments: list = Field(
        default=[
            ToolArgument(
                name="action_name",
                arg_type="string",
                description="Name of the Composio action to execute",
                required=True,
                example="name",
            ),
            ToolArgument(
                name="parameters",
                arg_type="string",
                description="JSON string of parameters for the action",
                required=True,
                example='{"city": "Paris"}, {"query": "SELECT * FROM table"} ... etc',
            ),
        ]
    )

    api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("COMPOSIO_API_KEY"),
        description="Composio API key for authentication",
    )
    toolset: Optional[ComposioToolSet] = None
    actions: List[str] = Field(default_factory=list)
    composio_action: Optional[Callable] = None

    def __init__(self, action: str | None = None, **data: Any):
        """Initialize the Composio tool with a specific action.
        
        Args:
            action: Name of the Composio action to initialize with
            **data: Additional data for tool initialization
        """
        logger.info(f"Initializing ComposioTool with action: {action}")
        logger.debug(f"Additional data: {data}")
        
        super().__init__(**data)
        if not self.api_key:
            logger.error("COMPOSIO_API_KEY environment variable is missing")
            raise ValueError("COMPOSIO_API_KEY environment variable is required")
        
        logger.info("Creating ComposioToolSet with API key")
        self.toolset = ComposioToolSet(api_key=self.api_key)
        
        if action:
            logger.info(f"Setting up action: {action}")
            self._setup_action(action)

    def _setup_action(self, action_name: str) -> None:
        """Set up a specific Composio action.
        
        Args:
            action_name: Name of the action to set up
        """
        logger.info(f"Setting up Composio action: {action_name}")
        
        # Convert to Action if string
        action = Action(action_name) if isinstance(action_name, str) else action_name
        logger.debug(f"Action object: {action}")
        
        # Check connected account
        if not action.no_auth:
            logger.info(f"Checking connected accounts for app: {action.app}")
            connections = self.toolset.client.connected_accounts.get()
            connected_apps = [conn.appUniqueId.lower() for conn in connections]
            logger.debug(f"Found connected accounts: {connected_apps}")
            
            if action.app.lower() not in connected_apps:
                logger.error(f"No connected account found for app: {action.app}")
                raise RuntimeError(
                    f"No connected account found for app `{action.app}`; "
                    f"Run `composio add {action.app}` to fix this"
                )
            logger.info(f"Found connected account for app: {action.app}")

        # Get action schema
        logger.info("Fetching action schema")
        try:
            (action_schema,) = self.toolset.get_action_schemas(actions=[action])
            schema = action_schema.model_dump(exclude_none=True)
            logger.debug(f"Action schema: {schema}")
        except Exception as e:
            logger.error(f"Error getting action schema: {str(e)}")
            raise RuntimeError(f"Failed to get action schema. Make sure the action name is correct: {str(e)}")
        
        # Update tool properties
        logger.info("Updating tool properties")
        self.name = schema["name"]
        self.description = schema["description"]
        self.actions = [action_name]
        logger.debug(f"Updated tool properties - name: {self.name}, actions: {self.actions}")
        
        # Create function wrapper
        logger.info("Creating action execution wrapper")
        def execute_action(**kwargs: Any) -> Dict:
            """Execute the Composio action."""
            logger.debug(f"Executing action with parameters: {kwargs}")
            return self.toolset.execute_action(
                action=Action(schema["name"]),
                params=kwargs
            )
        
        self.composio_action = execute_action
        logger.info("Action setup completed successfully")

    def execute(self, **kwargs: Any) -> str:
        """Execute a Composio action with the given parameters.

        Args:
            action_name: Name of the Composio action to execute
            parameters: JSON string containing action parameters

        Returns:
            Response from the Composio action execution

        Raises:
            ValueError: If required parameters are missing or invalid
            RuntimeError: If action execution fails
        """
        logger.info(f"Executing Composio action with kwargs: {kwargs}")
        
        try:
            action_name = kwargs.get("action_name", "").lower()
            parameters = kwargs.get("parameters")
            logger.info(f"Action name: {action_name}")
            logger.debug(f"Parameters: {parameters}")

            if not action_name or not parameters:
                logger.error("Missing required parameters")
                raise ValueError("Both action_name and parameters are required")

            # Action name mapping for common aliases
            action_mapping = {
                'send_email': 'gmail_send_email',
                'email': 'gmail_send_email',
                'email': 'gmail_send_email',
                'googlecalendar': 'googlecalendar_create_event'
            }
            
            # Try to map the action name if it's an alias
            if action_name in action_mapping:
                original_name = action_name
                action_name = action_mapping[action_name]
                logger.info(f"Mapped action name from '{original_name}' to '{action_name}'")

            allowed_actions = [a.lower() for a in self.actions]
            if action_name not in allowed_actions:
                logger.error(f"Invalid action name. Allowed actions: {self.actions}")
                suggestions = [a for a in self.actions if action_name in a.lower()]
                suggestion_msg = f" Did you mean '{suggestions[0]}'?" if suggestions else ""
                raise ValueError(
                    f"Action '{action_name}' not in allowed actions: {self.actions}.{suggestion_msg}"
                )

            logger.info(f"Executing Composio action: {action_name}")
            
            # Set up action if not already set
            if not self.composio_action or action_name not in [a.lower() for a in self.actions]:
                logger.info("Action not set up, initializing...")
                self._setup_action(action_name)
            
            # Execute action
            logger.info("Executing action with parameters")
            parameters_dict = eval(parameters)
            logger.debug(f"Evaluated parameters: {parameters_dict}")
            
            result = self.composio_action(**parameters_dict)
            logger.info("Action executed successfully")
            logger.debug(f"Action result: {result}")
            
            return str(result)

        except Exception as e:
            logger.error(f"Error executing Composio action: {str(e)}", exc_info=True)
            raise RuntimeError(f"Failed to execute Composio action: {str(e)}")


if __name__ == "__main__":
    # Example usage
    tool = ComposioTool(action="WEATHERMAP_WEATHER")
    print(tool.to_markdown())