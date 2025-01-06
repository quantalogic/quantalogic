import os

from quantalogic import Agent, console_print_events
from quantalogic.tools import (
    LLMTool,
)

# Verify API key is set - required for authentication with DeepSeek's API
# This check ensures the agent won't fail during runtime due to missing credentials
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

# Initialize agent with DeepSeek model and LLM tool
# The LLM tool serves dual purpose:
# 1. As a reasoning engine for the agent's cognitive processes
# 2. As a latent space explorer, enabling the agent to:
#    - Discover novel solution paths
#    - Generate creative combinations of concepts
#    - Explore alternative reasoning strategies
# Using the same model ensures consistent behavior across both roles
agent = Agent(model_name="deepseek/deepseek-chat", tools=[LLMTool(model_name="deepseek/deepseek-chat")])

# Set up event monitoring to track agent's lifecycle
# This helps in debugging and understanding the agent's behavior
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

# Execute a multi-step task showcasing agent's capabilities
# Demonstrates:
# 1. Creative content generation
# 2. Language translation
# 3. Style adaptation
# 4. Multi-step reasoning and execution
result = agent.solve_task(
    "1. Write a poem in English about a dog. "
    "2. Translate the poem into French. "
    "3. Choose 2 French authors"
    "4. Rewrite the translated poem with the style of the chosen authors. "
)
print(result)
