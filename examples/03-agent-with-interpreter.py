import os

from quantalogic import Agent, console_print_events
from quantalogic.tools import (
    PythonTool,
)

# Verify API key is set - required for authentication with DeepSeek's API
# This check ensures the agent won't fail during runtime due to missing credentials
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

# Initialize agent with DeepSeek model and Python tool
agent = Agent(model_name="deepseek/deepseek-chat", tools=[PythonTool()])

# Set up event monitoring to track agent's lifecycle
# This helps in debugging and understanding the agent's behavior
agent.event_emitter.on(
    "*",
    console_print_events,
)

# Execute a complex multi-step task demonstrating the agent's capabilities
result = agent.solve_task("1. Calculate PI with 10000 decimal places.")
print(result)
