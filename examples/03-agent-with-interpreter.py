import os

from quantalogic import Agent
from quantalogic.console_print_events import console_print_events
from quantalogic.console_print_token import console_print_token
from quantalogic.tools import (
    PythonTool,
)

# Verify API key is set - required for authentication with DeepSeek's API
# This preemptive check prevents runtime failures and ensures secure API access
# We validate credentials early to maintain system reliability
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

# Initialize agent with DeepSeek model and Python tool
agent = Agent(model_name="deepseek/deepseek-chat", tools=[PythonTool()])

# Configure comprehensive event monitoring system
# This system is crucial for:
# - Real-time debugging and issue diagnosis
# - Performance analysis and optimization
# - Maintaining audit trails of agent activities
# The specific events tracked were chosen to provide maximum observability
agent.event_emitter.on(
    [
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
    console_print_events,
)

# Register stream_chunk event listener with string instead of list
agent.event_emitter.on("stream_chunk", console_print_token)

# Execute a precision mathematics task to demonstrate:
# - The system's ability to handle complex computations
# - Seamless integration with PythonTool
# - Real-time monitoring capabilities for debugging
# This serves as both a functional test and capability demonstration
result = agent.solve_task("1. Calculate PI with 10000 decimal places.",streaming=True)
print(result)
