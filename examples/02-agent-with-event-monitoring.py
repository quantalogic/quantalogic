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
    LLMTool,
)

# Verify API key is set - required for authentication with DeepSeek's API
# This early check prevents runtime failures and ensures proper initialization
# We validate credentials before any API calls to maintain system reliability
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")


# Initialize agent with DeepSeek model and LLM tool
# The LLM tool's dual-purpose design was chosen to:
# 1. Maintain cognitive consistency by using the same model for reasoning
# 2. Enable creative exploration through latent space manipulation
# This architecture reduces model switching overhead and ensures
# coherent behavior across different operational modes
agent = Agent(
    model_name="deepseek/deepseek-chat",
    tools=[LLMTool(model_name="deepseek/deepseek-chat", name="deepseek_llm_tool", on_token=console_print_token)],
)

# Set up event monitoring to track agent's lifecycle
# The event system was implemented to:
# 1. Provide real-time observability into the agent's operations
# 2. Enable debugging and performance monitoring
# 3. Support future analytics and optimization efforts
agent.event_emitter.on(
    event=[
        "task_complete",
        "task_think_start",
        "task_think_end",
        "tool_execution_start",
        "tool_execution_end",
        "error_max_iterations_reached",
        "memory_full",
        "memory_compacted",
        "memory_summary",
    ],
    listener=console_print_events,
)

agent.event_emitter.on(event=["stream_chunk"], listener=console_print_token)

# Execute a multi-step task showcasing agent's capabilities
# This example was designed to demonstrate:
# 1. The system's ability to handle complex, multi-domain tasks
# 2. Integration of creative and analytical capabilities
# 3. The agent's capacity for contextual understanding and adaptation
result = agent.solve_task(
    "1. Write a poem in English about a dog. "
    "2. Translate the poem into French. "
    "3. Choose 2 French authors"
    "4. Rewrite the translated poem with the style of the chosen authors. ",
    streaming=True,  # Enable streaming to see token-by-token output
)
print(result)
