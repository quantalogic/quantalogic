"""Example usage of the ComposioTool for executing Composio actions."""

import os
from loguru import logger

from quantalogic.tools.composio import ComposioTool

def main():
    """Demonstrate ComposioTool usage with a weather API example."""
    try:
        # Initialize the tool
        tool = ComposioTool(action="WEATHERMAP_WEATHER")
        
        # Example: Get weather for Paris
        action_name = "WEATHERMAP_WEATHER"
        parameters = '{"location": "Paris"}'  # Changed from "city" to "location"
        
        logger.info(f"Getting weather for Paris using Composio action: {action_name}")
        
        # Execute the action
        result = tool.execute(action_name=action_name, parameters=parameters)
        
        # Print the result
        logger.info(f"Weather data: {result}")
        
        if result.get('error'):
            return f"Error: {result['error']}"
        
        return "Weather data retrieved successfully!"
        
    except Exception as e:
        logger.error(f"Error in ComposioTool example: {str(e)}")
        return f"Error: {str(e)}"

if __name__ == "__main__":
    # Ensure COMPOSIO_API_KEY is set
    if not os.getenv("COMPOSIO_API_KEY"):
        print("Please set COMPOSIO_API_KEY environment variable")
    else:
        result = main()
        print(result)