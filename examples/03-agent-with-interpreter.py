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

# Configure comprehensive event monitoring system
# Tracks all agent activities including:
# - Code execution steps
# - Tool interactions
# - Error conditions
# Essential for debugging and performance optimization
agent.event_emitter.on(
    "*",
    console_print_events,
)

# Execute a precision mathematics task demonstrating:
# - High-precision calculations
# - PythonTool integration
# - Real-time monitoring capabilities
result = agent.solve_task("1. Calculate PI with 10000 decimal places.")
print(result)
