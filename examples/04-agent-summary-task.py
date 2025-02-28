#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "quantalogic",
# ]
# ///

import os
import asyncio

from quantalogic import Agent
from quantalogic.console_print_events import console_print_events
from quantalogic.console_print_token import console_print_token
from quantalogic.tools import LLMTool, MarkitdownTool

# MODEL_NAME = "gpt-4o-mini"
MODEL_NAME = "openrouter/openai/gpt-4o-mini"

# Verify API key is set - prevents runtime errors and ensures proper authentication
if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable is not set")

# Initialize agent with core tools for web content processing and language operations
# MarkitdownTool enables article analysis while LLMTool handles reasoning tasks
agent = Agent(
    model_name=MODEL_NAME,
    tools=[
        MarkitdownTool(),
        LLMTool(model_name=MODEL_NAME, on_token=console_print_token),
    ],
)

# Event monitoring tracks key operations for debugging and performance tuning
agent.event_emitter.on(
    [
        "task_complete",
        "task_think_start",
        "task_think_end",
        "tool_execution_start",
        "tool_execution_end",
    ],
    console_print_events,
)

agent.event_emitter.on(
    event=["stream_chunk"],
    listener=console_print_token,
)


async def main():
    # Execute AI news analysis task showcasing tool integration and content processing
    # Using the async version of solve_task
    result = await agent.async_solve_task(
        """

        1. Read the latest news about AI https://arxiv.org/search/cs?query=artificial+intelligence+survey&searchtype=all&abstracts=show&order=-announced_date_first&size=25 
           You can use MarkitdownTool to read the latest news.
        2. Select the top 5 articles based on their impact on the AI field and summarize their key points as answer.

    """,
        streaming=True,
    )
    print(result)


# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())
