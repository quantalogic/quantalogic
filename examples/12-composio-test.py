#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "streamlit",
#     "pandas",
#     "plotly",
#     "quantalogic",
#     "fastapi",
#     "uvicorn"
# ]
# ///

"""FastAPI application for Composio weather integration with QuantaLogic agent."""

"""Test module for Composio tool integration with QuantaLogic agent."""

import os
from dotenv import load_dotenv

import os
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
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
        no_stream (bool, optional): If True, the agent will not stream results.
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

app = FastAPI(
    title="Weather API",
    description="API for getting weather information using Composio and QuantaLogic",
    version="1.0.0"
)
@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Welcome to the Weather API"}

@app.post("/weather")
async def get_weather():
    response = test_composio_weather()
    return {"location": "Paris", "weather_info": response}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002, reload=True)
