"""Example script demonstrating the WebNavigationTool."""

import asyncio
from dotenv import load_dotenv
from loguru import logger

from quantalogic.tools.web_navigation import WebNavigationTool

# Load environment variables
load_dotenv()

async def main():
    """Run web navigation examples."""
    try:
        # Initialize the tool with a specific model
        web_tool = WebNavigationTool(model_name="gpt-3.5-turbo")
        
        # Example 1: Simple search task
        logger.info("Running search example...")
        task1 = "Go to python.org and find information about the latest Python version"
        result1 = await web_tool.async_execute(task=task1)
        print("\nSearch Result:")
        print(result1)
        
        # Example 2: Navigation task
        logger.info("\nRunning navigation example...")
        task2 = "Visit GitHub's trending page and list the top 3 Python repositories"
        result2 = await web_tool.async_execute(task=task2)
        print("\nNavigation Result:")
        print(result2)

    except Exception as e:
        logger.error(f"Error during web navigation: {e}")
        raise

if __name__ == "__main__":
    try:
        # Run the async examples
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
    except Exception as e:
        logger.error(f"Script failed: {e}")
