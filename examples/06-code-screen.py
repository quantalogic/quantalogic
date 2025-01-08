import os

from quantalogic import Agent, console_print_events
from quantalogic.tools import (
    ListDirectoryTool,
    LLMTool,
    LLMVisionTool,
    ReadFileBlockTool,
    ReadFileTool,
    ReplaceInFileTool,
    RipgrepTool,
    SearchDefinitionNames,
    WriteFileTool,
)

MODEL_NAME = "openrouter/deepseek/deepseek-chat"
VISION_MODEL_NAME = "openrouter/openai/gpt-4o-mini"


# Verify API keys are set before initialization to prevent runtime failures
# We use separate keys for DeepSeek and OpenAI to maintain service independence
# and allow for future service switching without code changes
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable is not set")


agent = Agent(
    model_name=MODEL_NAME,
    tools=[
        SearchDefinitionNames(),
        RipgrepTool(),
        WriteFileTool(),
        ReadFileTool(),
        ReplaceInFileTool(),
        ReadFileBlockTool(),
        ListDirectoryTool(),
        LLMVisionTool(model_name=VISION_MODEL_NAME),
        LLMTool(model_name=MODEL_NAME, name="product_manager"),
    ],
)

# Event monitoring system tracks all agent activities for observability
# We use a wildcard ('*') listener to capture all events, which:
# 1. Provides complete audit trail for debugging
# 2. Enables real-time progress tracking
# 3. Allows for future analytics integration
agent.event_emitter.on(
    "*",
    console_print_events,
)


# Example task demonstrating full agent capabilities:
# 1. Image analysis for specification extraction
# 2. Frontend code generation
# 3. File system operations
# This showcases the agent's ability to handle complex, multi-step workflows
result = agent.solve_task("""

        Your task is to create a functional screen code for a user interface.

        1. Create a very detailed UX specification based on this screen picture:

            - UI elements layout
            - UI elements labels, text, icons, images
            - UI elements hierarchy
            - UI elements positioning
            - UI elements width, height
            - Color scheme
            - Font styles
            - Animations

           Image: https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR6wVcT9YYGkmnIfMXnubAaHgmM_b8DE4IlFA&s
        
        2. Create a functional specification from the UX specification.
        
        3. Create HTML5, TailwindCSS, and pure JavaScript implementation that follow stricly 

            - The functional specification
            - The UX specification

           Save the code to: ./demo01/

           Save the specification to: ./demo01/doc/ux_specification.md
           Save the functional specification to: ./demo01/doc/functional_specification.md



           Check the work done and update if necessary.
        """)
