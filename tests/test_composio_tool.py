"""Example usage of Composio tools with quantalogic agent."""

import os
from loguru import logger

from quantalogic.agent import Agent
from quantalogic.memory import AgentMemory
from quantalogic.tools.composio import ComposioTool, ComposioToolSet
from quantalogic.generative_model import GenerativeModel
from quantalogic.tools import TaskCompleteTool


def main():
    """Test Composio integration with the agent."""
    # Set up logging
    logger.info("Starting Composio tool test")

    try:
        # Initialize Composio toolset
        composio_toolset = ComposioToolSet()  # Will use COMPOSIO_API_KEY from env
        
        # Create Composio tool instance
        weather_tool = ComposioTool(
            toolset=composio_toolset  # Reuse the toolset
        )
        
        # Create the agent with our tools
        agent = Agent(
            model_name="openai/gpt-4o-mini",  # Or your preferred model
            memory=AgentMemory(),
            tools=[weather_tool, TaskCompleteTool()],
            specific_expertise="Weather information expert",
        )

        # Execute the task
        logger.info("Executing weather query task...")
        result = agent.solve_task(
            "Get the current weather in Paris, France and provide a summary "
            "including temperature and conditions."
        )
        
        # Print results
        print("\nTask Result:")
        print("-" * 50)
        print(result)
        print("-" * 50)

    except Exception as e:
        logger.error(f"Error during execution: {str(e)}")
        raise


if __name__ == "__main__":
    if not os.getenv("COMPOSIO_API_KEY"):
        print("Please set COMPOSIO_API_KEY environment variable")
    else:
        main()
