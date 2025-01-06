import os

from quantalogic import Agent, console_print_events
from quantalogic.tools import LLMTool, MarkitdownTool

MODEL_NAME = "gpt-4o-mini"

# Verify API key is set - required for authentication with OpenAI's API
# This check ensures the agent won't fail during runtime due to missing credentials
if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable is not set")

# Initialize agent with OpenAI model and integrated tools
# Tools include:
# - MarkitdownTool: For web content parsing and analysis
# - LLMTool: For language model operations and reasoning
agent = Agent(
    model_name=MODEL_NAME,
    tools=[
        MarkitdownTool(),
        LLMTool(model_name=MODEL_NAME),
    ],
)

# Configure comprehensive event monitoring system
# Tracks all agent activities including:
# - Web content processing
# - Article selection logic
# - Summary generation
# Essential for debugging and performance optimization
agent.event_emitter.on(
    "*",
    console_print_events,
)

# Execute a complex AI news analysis task demonstrating:
# - Web content processing with MarkitdownTool
# - Article impact assessment
# - Multi-document summarization
# - Integration of multiple tools
result = agent.solve_task("""

    1. Read the latest news about AI https://arxiv.org/search/cs?query=artificial+intelligence+survey&searchtype=all&abstracts=show&order=-announced_date_first&size=25 
       You can use MarkitdownTool to read the latest news.
    2. Select the top 5 articles based on their impact on the AI field and summarize their key points as answer.

""")
print(result)
