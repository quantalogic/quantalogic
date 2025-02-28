"""Tool for interacting with Composio API services."""

import json
import os
import traceback
from datetime import datetime
from typing import Any, Dict, Optional

from composio import Action, ComposioToolSet
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from quantalogic.tools.tool import Tool, ToolArgument


def setup_logger():
    """Configure Loguru logger with custom format and levels."""
    config = {
        "handlers": [
            {
                "sink": os.path.join(os.path.dirname(__file__), "composio_tool.log"),
                "format": "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
                "level": "DEBUG",
                "rotation": "1 day",
                "retention": "7 days",
                "compression": "zip",
            },
            {
                "sink": lambda msg: print(msg),
                "format": "<blue>{time:HH:mm:ss}</blue> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
                "level": "INFO",
            }
        ],
    }
    logger.configure(**config)


setup_logger()


class ActionSchema(BaseModel):
    """Schema for Composio actions with validation."""
    name: str
    description: str
    parameters: Dict[str, Any]
    response: Dict[str, Any]
    version: str
    enabled: bool = True

    model_config = ConfigDict(extra="allow")

    def __str__(self) -> str:
        """String representation for logging purposes."""
        return f"ActionSchema(name={self.name}, version={self.version}, enabled={self.enabled})"


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
    action_schema: Optional[ActionSchema] = None
    toolset: Optional[ComposioToolSet] = None
    
    # Performance tracking
    _last_execution_time: Optional[datetime] = None
    _execution_count: int = 0
    _error_count: int = 0

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
        start_time = datetime.now()
        
        try:
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
            logger.debug(f"Setting up toolset with API key: {'*' * len(self.api_key)}")
            self.toolset = ComposioToolSet(api_key=self.api_key)
            self._setup_action()
            
            # Set description if provided
            if description:
                self.description = description
            
            if need_validation is not None:
                self.need_validation = need_validation

            init_time = datetime.now() - start_time
            logger.info(f"ComposioTool initialization completed in {init_time.total_seconds():.2f}s")
            logger.debug(f"Tool configuration: {self._get_tool_info()}")

        except Exception as e:
            logger.error(f"Failed to initialize ComposioTool: {str(e)}")
            logger.debug(f"Stack trace:\n{traceback.format_exc()}")
            raise

    def _get_tool_info(self) -> Dict[str, Any]:
        """Get tool configuration for logging purposes."""
        return {
            "name": self.name,
            "action": self.action,
            "need_validation": self.need_validation,
            "schema_loaded": self.action_schema is not None,
            "toolset_initialized": self.toolset is not None,
            "execution_count": self._execution_count,
            "error_count": self._error_count,
            "last_execution": self._last_execution_time.isoformat() if self._last_execution_time else None
        }

    def _setup_action(self) -> None:
        """Set up the Composio action with its schema and parameters."""
        logger.debug(f"Setting up action: {self.action}")
        start_time = datetime.now()
        
        try:
            # Get action schema
            logger.debug("Fetching action schema from Composio")
            (schema,) = self.toolset.get_action_schemas(actions=[self.action])
            schema_dict = schema.model_dump()
            
            # For GOOGLECALENDAR_CREATE_EVENT, ensure summary is a required parameter
            if self.action == "GOOGLECALENDAR_CREATE_EVENT":
                parameters = schema_dict.get("parameters", {})
                properties = parameters.get("properties", {})
                required_params = parameters.get("required", [])
                
                # Add summary to properties if not present
                if "summary" not in properties:
                    properties["summary"] = {
                        "type": "string",
                        "description": "Title of the calendar event"
                    }
                
                # Add summary to required parameters if not present
                if "summary" not in required_params:
                    required_params.append("summary")
                
                # Update the schema
                parameters["properties"] = properties
                parameters["required"] = required_params
                schema_dict["parameters"] = parameters
            
            # Store schema
            self.action_schema = ActionSchema(**schema_dict)
            logger.debug(f"Loaded schema: {self.action_schema}")
            
            # Log schema version and metadata
            logger.debug(f"Schema version: {schema_dict.get('version', 'unknown')}")
            logger.debug(f"Schema description: {schema_dict.get('description', 'No description')}")
            
            # Set up tool description and arguments
            self._update_tool_info()
            
            setup_time = datetime.now() - start_time
            logger.info(f"Action setup completed in {setup_time.total_seconds():.2f}s")
            
        except Exception as e:
            logger.error(f"Error setting up action {self.action}: {str(e)}")
            logger.debug(f"Stack trace:\n{traceback.format_exc()}")
            raise RuntimeError(f"Failed to set up action: {str(e)}")

    def _update_tool_info(self) -> None:
        """Update tool description and arguments based on the action schema."""
        logger.debug("Updating tool information from schema")
        
        if not self.action_schema:
            logger.warning("No schema available for tool info update")
            return
            
        try:
            # Get parameters info
            schema_dict = self.action_schema.model_dump()
            parameters = schema_dict.get("parameters", {})
            required_params = parameters.get("required", [])
            properties = parameters.get("properties", {})
            
            logger.debug(f"Found {len(properties)} parameters in schema")
            logger.debug(f"Required parameters: {required_params}")
            
            # Build parameter details
            param_details = []
            total_required = 0
            total_optional = 0
            
            logger.info(f"Processing parameters for action {self.action}")
            for param, param_info in properties.items():
                is_required = param in required_params
                param_type = param_info.get("type", "any")
                param_desc = param_info.get("description", "").split(".")[0]
                default_value = param_info.get("default", "Not specified")
                examples = param_info.get("examples", [])
                
                # Track parameter counts
                if is_required:
                    total_required += 1
                    # Create detailed parameter description
                    param_detail = (
                        f"- `{param}`: ({param_type}*) {param_desc}\n"
                        f"  - Default: {default_value}\n"
                    )
                    if examples:
                        param_detail += f"  - Examples: {examples}\n"
                    param_details.append(param_detail)
                else:
                    total_optional += 1
                
                # Log detailed parameter information
                logger.debug(
                    f"Parameter '{param}':\n"
                    f"  - Type: {param_type}\n"
                    f"  - Required: {is_required}\n"
                    f"  - Description: {param_desc}\n"
                    f"  - Default: {default_value}\n"
                    f"  - Examples: {examples}"
                )
            
            logger.info(f"Parameter summary: {total_required} required, {total_optional} optional")
            
            # Update description if not explicitly set
            if not self.description:
                # Create example parameters object with all required parameters
                example_params = {}
                for param, param_info in properties.items():
                    if param in required_params:
                        if param_info.get("examples"):
                            example_params[param] = param_info["examples"][0]
                        else:
                            # Generate a sensible example based on type
                            param_type = param_info.get("type", "string")
                            example_params[param] = self._get_example_value(param_type)

                new_description = (
                    f"Execute Composio action {self.action}:\n"
                    f"Description: {self.action_schema.description}\n\n"
                    f"Required Parameters:\n" + 
                    "".join(param_details) + "\n"
                    f"Example usage:\n"
                    f"```json\n"
                    f"{json.dumps(example_params, indent=2)}\n"
                    f"```"
                )
                self.description = new_description
                logger.debug(f"Updated tool description:\n{new_description}")
            else:
                logger.debug("Tool description already set, skipping update")
            
            # Update arguments with better examples
            example_params = {}
            for param, param_info in properties.items():
                if param in required_params:
                    if param_info.get("examples"):
                        example_params[param] = param_info["examples"][0]
                    else:
                        param_type = param_info.get("type", "string")
                        example_params[param] = self._get_example_value(param_type)
            
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
                    description="JSON string of parameters for the action. Required parameters:\n" + 
                              "\n".join([f"- {p}: {properties[p].get('description', '')}" for p in required_params]),
                    required=True,
                    example=json.dumps(example_params),
                ),
            ]
            
            logger.debug(f"Updated tool description and {len(self.arguments)} arguments")
            
            # Validate parameters if needed
            if self.need_validation and self.action_schema:
                logger.debug("Validating parameters against schema")
                schema_dict = self.action_schema.model_dump()
                parameters_data = schema_dict.get("parameters", {})
                required_params = parameters_data.get("required", [])
                missing_params = [p for p in required_params if p not in example_params]
                if missing_params:
                    logger.error(f"Missing required parameters: {missing_params}")
                    raise ValueError(f"Missing required parameters: {', '.join(missing_params)}")

        except Exception as e:
            logger.error(f"Error updating tool info: {str(e)}")
            logger.debug(f"Stack trace:\n{traceback.format_exc()}")
            raise

    def _get_example_value(self, param_type: str) -> Any:
        """Generate a sensible example value based on parameter type."""
        type_examples = {
            "string": "example_value",
            "integer": 42,
            "number": 3.14,
            "boolean": True,
            "array": [],
            "object": {},
        }
        return type_examples.get(param_type, "example_value")

    def execute(self, **kwargs: Any) -> str:
        """Execute the Composio action with the given parameters."""
        start_time = datetime.now()
        self._execution_count += 1
        self._last_execution_time = start_time
        
        logger.info(f"Executing Composio action {self.action}")
        logger.debug(f"Execution parameters: {json.dumps(kwargs, indent=2)}")
        
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
                logger.debug(f"Parsed parameters: {json.dumps(parameters_dict, indent=2)}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON parameters: {str(e)}")
                raise ValueError(f"Invalid JSON parameters: {str(e)}")
            
            # Validate parameters if needed
            if self.need_validation and self.action_schema:
                logger.debug("Validating parameters against schema")
                schema_dict = self.action_schema.model_dump()
                parameters_data = schema_dict.get("parameters", {})
                required_params = parameters_data.get("required", [])
                missing_params = [p for p in required_params if p not in parameters_dict]
                if missing_params:
                    logger.error(f"Missing required parameters: {missing_params}")
                    raise ValueError(f"Missing required parameters: {', '.join(missing_params)}")
            
            # Execute action
            logger.info(f"Executing {self.action} with validated parameters")
            result = self.toolset.execute_action(
                action=Action(self.action),
                params=parameters_dict
            )
            
            execution_time = datetime.now() - start_time
            logger.info(f"Action executed successfully in {execution_time.total_seconds():.2f}s")
            logger.debug(f"Action result: {json.dumps(result, indent=2)}")
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            self._error_count += 1
            logger.error(f"Error executing action: {str(e)}")
            logger.debug(f"Stack trace:\n{traceback.format_exc()}")
            logger.debug(f"Tool state at error: {self._get_tool_info()}")
            raise RuntimeError(f"Failed to execute action: {str(e)}")


if __name__ == "__main__":
    # Example usage
    try:
        tool = ComposioTool(action="EXAMPLE_ACTION")
        result = tool.execute(
            action_name="EXAMPLE_ACTION",
            parameters=json.dumps({"param1": "value1"})
        )
        print(f"Result: {result}")
    except Exception as e:
        logger.error(f"Example failed: {str(e)}")