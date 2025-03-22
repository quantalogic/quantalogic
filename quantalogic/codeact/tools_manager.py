import asyncio
from asyncio import TimeoutError
from contextlib import AsyncExitStack
from typing import List

import litellm
from loguru import logger

from quantalogic.tools import (
#    DuckDuckGoSearchTool,
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

from .utils import log_tool_method, logged_tool


@create_tool
@logged_tool("Adding")
async def add_tool(a: int, b: int) -> str:
    """Adds two numbers and returns the sum as a string."""
    return str(a + b)


@create_tool
@logged_tool("Multiplying")
async def multiply_tool(x: int, y: int) -> str:
    """Multiplies two numbers and returns the product as a string."""
    return str(x * y)


@create_tool
@logged_tool("Concatenating")
async def concat_tool(s1: str, s2: str) -> str:
    """Concatenates two strings and returns the result."""
    return s1 + s2


class AgentTool(Tool):
    """Tool for generating text using a language model."""
    def __init__(self, model: str = "gemini/gemini-2.0-flash"):
        super().__init__(
            name="agent_tool",
            description="Generates text using a language model based on a system prompt and user prompt.",
            arguments=[
                ToolArgument(name="system_prompt", arg_type="string", 
                           description="System prompt to guide the model's behavior", required=True),
                ToolArgument(name="prompt", arg_type="string", 
                           description="User prompt to generate a response for", required=True),
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
            logger.error(f"Temperature {temperature} is out of range (0-1)")
            raise ValueError("Temperature must be between 0 and 1")
        
        logger.info(f"Generating text with model {self.model}, temperature {temperature}")
        try:
            async with AsyncExitStack() as stack:
                await stack.enter_async_context(asyncio.timeout(30))
                
                logger.debug(f"Making API call to {self.model}")
                response = await litellm.acompletion(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=temperature,
                    max_tokens=1000
                )
                generated_text = response.choices[0].message.content.strip()
                logger.debug(f"Generated text: {generated_text[:100]}...")
                return generated_text
        except TimeoutError as e: # noqa: UP041
            error_msg = f"API call to {self.model} timed out after 30 seconds"
            logger.error(error_msg)
            raise TimeoutError(error_msg) from e # noqa: UP041
        except Exception as e:
            logger.error(f"Text generation failed: {str(e)}")
            raise RuntimeError(f"Text generation failed: {str(e)}") from e


def get_default_tools(model: str) -> List[Tool]:
    """Return list of default tools."""
    return [
#        DuckDuckGoSearchTool(),
        EditWholeContentTool(),
        ExecuteBashCommandTool(),
        GrepAppTool(),
        InputQuestionTool(),
        JinjaTool(),
        ListDirectoryTool(),
        ReadFileBlockTool(),
        ReadFileTool(),
        ReadHTMLTool(),
        ReplaceInFileTool(),
        RipgrepTool(),
        SearchDefinitionNamesTool(),
        TaskCompleteTool(),
        WriteFileTool(),
        AgentTool(model=model),
        add_tool,
        multiply_tool,
        concat_tool
    ]