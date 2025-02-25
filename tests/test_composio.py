"""Test module for Composio tool integration with QuantaLogic agent."""

import os
from dotenv import load_dotenv

from quantalogic.agent import Agent
from quantalogic.console_print_token import console_print_token
from quantalogic.event_emitter import EventEmitter
from quantalogic.memory import AgentMemory
from quantalogic.tools.composio import ComposioTool 

from typing import Any
from dotenv import load_dotenv

from quantalogic.agent import Agent
from quantalogic.console_print_token import console_print_token
from quantalogic.event_emitter import EventEmitter
from quantalogic.memory import AgentMemory
from quantalogic.tools import (
    AgentTool,
    DownloadHttpFileTool,
    DuckDuckGoSearchTool,
    EditWholeContentTool,
    ExecuteBashCommandTool,
    InputQuestionTool,
    ListDirectoryTool,
    LLMImageGenerationTool,
    LLMTool,
    LLMVisionTool,
    MarkitdownTool,
    NodeJsTool,
    PythonTool,
    ReadFileBlockTool,
    ReadFileTool,
    ReadHTMLTool,
    ReplaceInFileTool,
    RipgrepTool,
    SafePythonInterpreterTool, 
    SearchDefinitionNames,
    TaskCompleteTool,
    WikipediaSearchTool,
    WriteFileTool,
    GoogleNewsTool,
    PresentationLLMTool,
    SequenceTool,
    SQLQueryTool,
    SQLQueryToolAdvanced
)


# Load environment variables
load_dotenv()


def create_basic_composio_agent(
    model_name: str, 
    vision_model_name: str | None = None, 
    no_stream: bool = False, 
    compact_every_n_iteration: int | None = None,
    max_tokens_working_memory: int | None = None
) -> Agent:
    """Create an agent with the specified model and tools.

    Args:
        model_name (str): Name of the model to use
        vision_model_name (str | None): Name of the vision model to use
        no_stream (bool, opional): If True, the agent will not stream results.
        compact_every_n_iteration (int | None, optional): Frequency of memory compaction.
        max_tokens_working_memory (int | None, optional): Maximum tokens for working memory.

    Returns:
        Agent: An agent with the specified model and tools
    """
    # Rebuild AgentTool to resolve forward references
    AgentTool.model_rebuild()

    composio_tool = ComposioTool(action="WEATHERMAP_WEATHER")

    tools = [
        TaskCompleteTool(),
        composio_tool, 
    ]

    return Agent(
        model_name=model_name,
        tools=tools,
        compact_every_n_iterations=compact_every_n_iteration,
        max_tokens_working_memory=max_tokens_working_memory,
    )



def test_composio_weather():
    """Test Composio weather integration with the agent."""
    # Create agent with Composio tool
    agent = create_basic_composio_agent(
        model_name="openai/gpt-4o-mini", 
        vision_model_name=None
    )
    
    # Test weather query
    task = "What's the current weather in Paris?"
    response = agent.solve_task(task)
    
    print(f"\nTask: {task}")
    print(f"Response: {response}")
    
    assert response is not None
    assert isinstance(response, str)
    assert len(response) > 0


if __name__ == "__main__":
    test_composio_weather()
