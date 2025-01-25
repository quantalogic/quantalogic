#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "quantalogic",
# ]
# ///

import os

from quantalogic import Agent
from quantalogic.console_print_events import console_print_events
from quantalogic.console_print_token import console_print_token
from quantalogic.tools import (
    ListDirectoryTool,
    ReadFileBlockTool,
    ReadFileTool,
    ReplaceInFileTool,
    RipgrepTool,
    SearchDefinitionNames,
    WriteFileTool,
)

MODEL_NAME = "deepseek/deepseek-chat"

# Verify API key is set - required for authentication with DeepSeek's API
# This check ensures the agent won't fail during runtime due to missing credentials
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")


agent = Agent(
    model_name=MODEL_NAME,
    tools=[
        SearchDefinitionNames(),
        RipgrepTool(),
        WriteFileTool(),
        ReadFileTool(),
        ReplaceInFileTool(),
        ReadFileBlockTool(),
        ListDirectoryTool(),
    ],
)

# Configure comprehensive event monitoring system
# Tracks all agent activities including:
# - Tool execution
# - File operations
# - Task progress
# Essential for debugging and performance optimization
agent.event_emitter.on(
    [
        "task_complete",
        "task_think_start",
        "task_think_end",
        "tool_execution_start",
        "tool_execution_end",
        "error_max_iterations_reached",
    ],
    console_print_events,
)

agent.event_emitter.on(event=["stream_chunk"], listener=console_print_token)


# Execute a complex file operation task demonstrating:
# - Directory traversal
# - File content analysis
# - Comment updates
# - Integration of multiple tools
result = agent.solve_task(
    """

1. Update all the files at the first level of the ./examples directory
2. Update the comments of each file to make it more relevant and informative: focus on why

""",
    streaming=True,
)
