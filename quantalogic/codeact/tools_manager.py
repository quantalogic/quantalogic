import asyncio
from contextlib import AsyncExitStack
from typing import List

import litellm
from loguru import logger

from quantalogic.tools import (
    EditWholeContentTool,
    ExecuteBashCommandTool,
    GrepAppTool,
    InputQuestionTool,
    JinjaTool,
    ListDirectoryTool,
    ReadFileBlockTool,
    ReadFileTool,
    ReadHTMLTool,
    ReplaceInFileTool,
    RipgrepTool,
    SearchDefinitionNamesTool,
    TaskCompleteTool,
    Tool,
    ToolArgument,
    WriteFileTool,
    create_tool,
)

from .utils import log_async_tool, log_tool_method


@create_tool
@log_async_tool("Adding")
async def add_tool(a: int, b: int) -> str:
    """Adds two numbers and returns the sum as a string."""
    return str(a + b)

@create_tool
@log_async_tool("Multiplying")
async def multiply_tool(x: int, y: int) -> str:
    """Multiplies two numbers and returns the product as a string."""
    return str(x * y)

@create_tool
@log_async_tool("Concatenating")
async def concat_tool(s1: str, s2: str) -> str:
    """Concatenates two strings and returns the result."""
    return s1 + s2

class AgentTool(Tool):
    """Tool for generating text using a language model."""
    def __init__(self, model: str = "gemini/gemini-2.0-flash"):
        super().__init__(
            name="agent_tool",
            description="Generates text using a language model.",
            arguments=[
                ToolArgument(name="system_prompt", arg_type="string", 
                           description="System prompt to guide the model", required=True),
                ToolArgument(name="prompt", arg_type="string", 
                           description="User prompt to generate a response", required=True),
                ToolArgument(name="temperature", arg_type="float", 
                           description="Temperature for generation (0 to 1)", required=True)
            ],
            return_type="string"
        )
        self.model = model

    @log_tool_method
    async def async_execute(self, **kwargs) -> str:
        system_prompt = kwargs["system_prompt"]
        prompt = kwargs["prompt"]
        temperature = float(kwargs["temperature"])

        if not 0 <= temperature <= 1:
            raise ValueError("Temperature must be between 0 and 1")

        logger.info(f"Generating with {self.model}, temp={temperature}")
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(asyncio.timeout(30))
            response = await litellm.acompletion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=1000
            )
            return response.choices[0].message.content.strip()

class RetrieveStepTool(Tool):
    """Tool to retrieve information from a specific previous step."""
    def __init__(self, history_store: List[dict]):
        super().__init__(
            name="retrieve_step",
            description="Retrieve the thought, action, and result from a specific step.",
            arguments=[
                ToolArgument(name="step_number", arg_type="int", 
                            description="The step number to retrieve (1-based)", required=True)
            ],
            return_type="string"
        )
        self.history_store = history_store

    @log_tool_method
    async def async_execute(self, **kwargs) -> str:
        step_number = kwargs["step_number"]
        if step_number < 1 or step_number > len(self.history_store):
            return f"Error: Step {step_number} does not exist."
        step = self.history_store[step_number - 1]
        return (
            f"Step {step_number}:\n"
            f"Thought: {step['thought']}\n"
            f"Action: {step['action']}\n"
            f"Result: {step['result']}"
        )

def get_default_tools(model: str) -> List[Tool]:
    """Return list of default tools."""
    return [
        #EditWholeContentTool(), 
        #ExecuteBashCommandTool(), 
        GrepAppTool(),
        InputQuestionTool(), 
        JinjaTool(), 
        ListDirectoryTool(),
        ReadFileBlockTool(), 
        ReadFileTool(), 
        ReadHTMLTool(),
        #ReplaceInFileTool(), 
        # RipgrepTool(), 
        # SearchDefinitionNamesTool(),
        #TaskCompleteTool(), 
        WriteFileTool(), 
        AgentTool(model=model),
    ]