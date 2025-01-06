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

# Set up event monitoring to track agent's lifecycle
# This helps in debugging and understanding the agent's behavior
agent.event_emitter.on(
    "*",
    console_print_events,
)


result = agent.solve_task("""

1. Find all class definitions in quantalogic/tools/quantalogic/tools/language_handlers/*.py
2. Analyze inheritance patterns
3. Generate class diagram using mermaid diagram
4. Write the result in ./demo/report.md

""")
