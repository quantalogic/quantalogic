"""Tool for interacting with Composio API services.

This tool provides a wrapper around Composio's API functionality, allowing
integration with various Composio services while maintaining type safety
and proper error handling.
"""

import os
from typing import Any, Dict, Optional, List, Callable, Union, Tuple
from functools import lru_cache
import json
from datetime import datetime, timedelta

from loguru import logger
from pydantic import ConfigDict, Field, BaseModel, validator

from composio import Action, ComposioToolSet
from composio.client.collections import ConnectedAccountModel
from composio.constants import DEFAULT_ENTITY_ID
from composio.utils.shared import json_schema_to_model
from quantalogic.tools.tool import Tool, ToolArgument


class ActionSchema(BaseModel):
    """Schema for Composio actions with validation."""
    name: str
    description: str
    parameters: Dict[str, Any]
    response: Dict[str, Any]
    version: str
    enabled: bool = True
    cached_at: datetime = Field(default_factory=datetime.now)

    @validator('parameters')
    def validate_parameters(cls, v):
        if not isinstance(v, dict):
            raise ValueError("Parameters must be a dictionary")
        return v


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
                example="WEATHERMAP_WEATHER",
            ),
            ToolArgument(
                name="parameters",
                arg_type="string",
                description="JSON string of parameters for the action",
                required=True,
                example='{"location": "Paris"}',
            ),
        ]
    )

    api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("COMPOSIO_API_KEY"),
        description="Composio API key for authentication",
    )
    toolset: Optional[ComposioToolSet] = None
    actions: List[str] = Field(default_factory=list)
    action_schemas: Dict[str, ActionSchema] = Field(default_factory=dict)
    composio_action: Optional[Callable] = None
    schema_cache: Dict[str, Tuple[ActionSchema, datetime]] = Field(default_factory=dict)
    cache_duration: timedelta = Field(default=timedelta(hours=1))

    def __init__(self, action: Union[str, List[str], None] = None, **data: Any):
        """Initialize the Composio tool with specific actions.
        
        Args:
            action: Name of the Composio action(s) to initialize with
            **data: Additional data for tool initialization
        """
        logger.info(f"Initializing ComposioTool with action(s): {action}")
        
        super().__init__(**data)
        if not self.api_key:
            logger.error("COMPOSIO_API_KEY environment variable is missing")
            raise ValueError("COMPOSIO_API_KEY environment variable is required")
        
        logger.info("Creating ComposioToolSet with API key")
        self.toolset = ComposioToolSet(api_key=self.api_key)
        
        if action:
            actions = [action] if isinstance(action, str) else action
            for act in actions:
                self._setup_action(act)

    def _get_action_schema(self, action_name: str) -> ActionSchema:
        """Get and cache the schema for a specific action.
        
        Args:
            action_name: Name of the action to get schema for
            
        Returns:
            ActionSchema for the specified action
        """
        logger.debug(f"Getting schema for action: {action_name}")
        
        # Check cache first
        if action_name in self.schema_cache:
            schema, cached_time = self.schema_cache[action_name]
            if datetime.now() - cached_time < self.cache_duration:
                logger.debug(f"Using cached schema for action: {action_name}")
                return schema
        
        # Fetch new schema
        try:
            (action_schema,) = self.toolset.get_action_schemas(actions=[action_name])
            schema_dict = action_schema.model_dump(exclude_none=True)
            schema = ActionSchema(**schema_dict)
            
            # Update cache
            self.schema_cache[action_name] = (schema, datetime.now())
            return schema
            
        except Exception as e:
            logger.error(f"Error getting action schema: {str(e)}")
            raise RuntimeError(f"Failed to get action schema: {str(e)}")

    def _setup_action(self, action_name: str) -> None:
        """Set up a specific Composio action.
        
        Args:
            action_name: Name of the action to set up
        """
        logger.info(f"Setting up Composio action: {action_name}")
        
        # Convert to Action if string
        action = Action(action_name) if isinstance(action_name, str) else action_name
        
        # Check connected account if required
        if not action.no_auth:
            self._verify_connected_account(action.app)
        
        # Get and cache action schema
        schema = self._get_action_schema(action_name)
        self.action_schemas[action_name.lower()] = schema
        
        # Update tool properties
        if action_name not in self.actions:
            self.actions.append(action_name)
            
        logger.debug(f"Updated actions list: {self.actions}")

    def _verify_connected_account(self, app_name: str) -> None:
        """Verify that the required app account is connected.
        
        Args:
            app_name: Name of the app to verify connection for
        """
        logger.info(f"Verifying connected account for app: {app_name}")
        connections = self.toolset.client.connected_accounts.get()
        connected_apps = [conn.appUniqueId.lower() for conn in connections]
        
        if app_name.lower() not in connected_apps:
            logger.error(f"No connected account found for app: {app_name}")
            raise RuntimeError(
                f"No connected account found for app `{app_name}`; "
                f"Run `composio add {app_name}` to fix this"
            )
        logger.info(f"Verified connected account for app: {app_name}")

    def _validate_parameters(self, action_name: str, parameters: Dict[str, Any]) -> None:
        """Validate parameters against action schema.
        
        Args:
            action_name: Name of the action to validate parameters for
            parameters: Parameters to validate
        """
        schema = self.action_schemas.get(action_name.lower())
        if not schema:
            raise ValueError(f"No schema found for action: {action_name}")
            
        required_params = schema.parameters.get("required", [])
        for param in required_params:
            if param not in parameters:
                raise ValueError(f"Missing required parameter: {param}")

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
            action_name = kwargs.get("action_name", "").upper()
            parameters = kwargs.get("parameters")

            if not action_name or not parameters:
                raise ValueError("Both action_name and parameters are required")

            # Convert parameters string to dict
            try:
                parameters_dict = json.loads(parameters) if isinstance(parameters, str) else parameters
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON parameters: {str(e)}")

            # Validate action name
            if action_name not in self.actions:
                logger.error(f"Invalid action name: {action_name}")
                suggestions = [a for a in self.actions if action_name.lower() in a.lower()]
                suggestion_msg = f" Did you mean '{suggestions[0]}'?" if suggestions else ""
                raise ValueError(
                    f"Action '{action_name}' not in allowed actions: {self.actions}.{suggestion_msg}"
                )

            # Validate parameters
            self._validate_parameters(action_name, parameters_dict)
            
            # Execute action
            logger.info(f"Executing action {action_name} with parameters: {parameters_dict}")
            result = self.toolset.execute_action(
                action=Action(action_name),
                params=parameters_dict
            )
            
            logger.info("Action executed successfully")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error executing action: {str(e)}")
            raise RuntimeError(f"Failed to execute action: {str(e)}")


if __name__ == "__main__":
    # Example usage
    tool = ComposioTool(action=["WEATHERMAP_WEATHER", "GMAIL_SEND_EMAIL"])
    
    # Example weather query
    try:
        result = tool.execute(
            action_name="WEATHERMAP_WEATHER",
            parameters='{"location": "Paris,FR"}'
        )
        print(f"Weather result: {result}")
    except Exception as e:
        print(f"Error getting weather: {str(e)}")