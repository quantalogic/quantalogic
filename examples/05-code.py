import os

from quantalogic import Agent, console_print_events
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
        ListDirectoryTool()
    ],
)

# Configure comprehensive event monitoring system
# Tracks all agent activities including:
# - Tool execution
# - File operations
# - Task progress
# Essential for debugging and performance optimization
agent.event_emitter.on(
    "*",
    console_print_events,
)


# Execute a complex file operation task demonstrating:
# - Directory traversal
# - File content analysis
# - Comment updates
# - Integration of multiple tools
result = agent.solve_task("""

1. Update all the files at the first level of the ./examples directory
2. Update the comments of each file to make it more relevant and informative: focus on why

""")
