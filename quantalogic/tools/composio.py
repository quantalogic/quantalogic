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
                example="WEATHERMAP_WEATHER",
            ),
            ToolArgument(
                name="parameters",
                arg_type="string",
                description="JSON string of parameters for the action",
                required=True,
                example='{"city": "Paris"}',
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
        super().__init__(**data)
        if not self.api_key:
            raise ValueError("COMPOSIO_API_KEY environment variable is required")
        
        self.toolset = ComposioToolSet(api_key=self.api_key)
        
        if action:
            self._setup_action(action)

    def _setup_action(self, action_name: str) -> None:
        """Set up a specific Composio action.
        
        Args:
            action_name: Name of the action to set up
        """
        # Convert to Action if string
        action = Action(action_name) if isinstance(action_name, str) else action_name
        
        # Check connected account
        if not action.no_auth:
            connections = self.toolset.client.connected_accounts.get()
            if action.app not in [conn.appUniqueId for conn in connections]:
                raise RuntimeError(
                    f"No connected account found for app `{action.app}`; "
                    f"Run `composio add {action.app}` to fix this"
                )

        # Get action schema
        (action_schema,) = self.toolset.get_action_schemas(actions=[action])
        schema = action_schema.model_dump(exclude_none=True)
        
        # Update tool properties
        self.name = schema["name"]
        self.description = schema["description"]
        self.actions = [action_name]
        
        # Create function wrapper
        def execute_action(**kwargs: Any) -> Dict:
            """Execute the Composio action."""
            return self.toolset.execute_action(
                action=Action(schema["name"]),
                params=kwargs
            )
        
        self.composio_action = execute_action

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
        try:
            action_name = kwargs.get("action_name")
            parameters = kwargs.get("parameters")

            if not action_name or not parameters:
                raise ValueError("Both action_name and parameters are required")

            if self.actions and action_name not in self.actions:
                raise ValueError(f"Action {action_name} not in allowed actions: {self.actions}")

            logger.info(f"Executing Composio action: {action_name}")
            
            # Set up action if not already set
            if not self.composio_action or action_name not in self.actions:
                self._setup_action(action_name)
            
            # Execute action
            result = self.composio_action(**eval(parameters))
            return str(result)

        except Exception as e:
            logger.error(f"Error executing Composio action: {str(e)}")
            raise RuntimeError(f"Failed to execute Composio action: {str(e)}")


if __name__ == "__main__":
    # Example usage
    tool = ComposioTool(action="WEATHERMAP_WEATHER")
    print(tool.to_markdown())
