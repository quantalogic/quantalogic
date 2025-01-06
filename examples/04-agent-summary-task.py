import os

from quantalogic import Agent, console_print_events
from quantalogic.tools import LLMTool, MarkitdownTool

MODEL_NAME = "gpt-4o-mini"

# Verify API key is set - required for authentication with DeepSeek's API
# This check ensures the agent won't fail during runtime due to missing credentials
if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable is not set")

# Initialize agent with DeepSeek model and Python tool
agent = Agent(
    model_name=MODEL_NAME,
    tools=[
        MarkitdownTool(),
        LLMTool(model_name=MODEL_NAME),
    ],
)

# Set up event monitoring to track agent's lifecycle
# This helps in debugging and understanding the agent's behavior
agent.event_emitter.on(
    "*",
    console_print_events,
)

# Execute a complex multi-step task demonstrating the agent's capabilities
result = agent.solve_task("""

    1. Read the latest news about AI https://arxiv.org/search/cs?query=artificial+intelligence+survey&searchtype=all&abstracts=show&order=-announced_date_first&size=25 
       You can use MarkitdownTool to read the latest news.
    2. Select the top 5 articles based on their impact on the AI field and summarize their key points as answer.

""")
print(result)
