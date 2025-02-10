"""Test module for Composio tool integration with QuantaLogic agent."""

import os
import asyncio
from dotenv import load_dotenv 

from typing import Any, Dict
from dotenv import load_dotenv

from quantalogic.agent import Agent
from quantalogic.console_print_token import console_print_token
from quantalogic.event_emitter import EventEmitter
from quantalogic.tools import (
    AgentTool, 
    TaskCompleteTool, 
    ComposioTool
)
from quantalogic.tools.llm_tool import LLMTool
# Load environment variables
load_dotenv()


def create_basic_composio_agent(
    model_name: str,   
    no_stream: bool = False, 
    compact_every_n_iteration: int | None = None,
    max_tokens_working_memory: int | None = None, 
) -> Agent:
    """Create an agent with the specified model and tools.

    Args:
        model_name (str): Name of the model to use
        tools (list | None): Optional list of tools to add
        no_stream (bool): If True, the agent will not stream results
        compact_every_n_iteration (int | None): Frequency of memory compaction
        max_tokens_working_memory (int | None): Maximum tokens for working memory

    Returns:
        Agent: An agent with the specified model and tools
    """
    # Rebuild AgentTool to resolve forward references
    AgentTool.model_rebuild()

    composio_tool = ComposioTool(action="WEATHERMAP_WEATHER") 
    composio_tool.name = "weather_tool"
    composio_tool.description = "This tool allows you to get the weather in a given location."

    # Create base tools list
    base_tools = [
        TaskCompleteTool(),
        LLMTool(
            model_name=model_name, 
            on_token=console_print_token if not no_stream else None, 
        ),
        composio_tool
    ] 
    return Agent(
        model_name=model_name,
        tools=base_tools, 
        compact_every_n_iterations=compact_every_n_iteration,
        max_tokens_working_memory=max_tokens_working_memory,
    )


def test_composio_weather():
    """Test Composio weather integration with the agent."""
    # Create agent with Composio tool
    agent = create_basic_composio_agent(
        model_name="openai/gpt-4o-mini",  
    )
    
    # Test weather query
    task = "What's the current weather in ALGERIA?"
    try:
        response = agent.solve_task(task)
        print(f"\nTask: {task}")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error occurred: {e}")


if __name__ == "__main__":
    try:
        test_composio_weather()
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed with error: {e}")
