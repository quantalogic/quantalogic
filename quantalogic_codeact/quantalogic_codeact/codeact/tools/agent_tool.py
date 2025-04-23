"""AgentTool definition for Quantalogic CodeAct framework."""

import asyncio
import os
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

import litellm
from loguru import logger

from quantalogic.tools import Tool, ToolArgument

from ..utils import log_tool_method


class AgentTool(Tool):
    """A specialized tool for generating text using language models, designed for AI agent workflows."""
    def __init__(self, model: str = None, timeout: int = None, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the AgentTool with configurable model and timeout."""
        try:
            super().__init__(
                name="agent_tool",
                description="Generates text using a language model with optional conversation history for context.",
                arguments=[
                    ToolArgument(name="system_prompt", arg_type="string", description="System prompt to guide the model", required=True),
                    ToolArgument(name="prompt", arg_type="string", description="User prompt to generate a response", required=True),
                    ToolArgument(name="temperature", arg_type="float", description="Temperature for generation (0 to 1)", required=True),
                    ToolArgument(
                        name="history",
                        arg_type="list",
                        description="Optional list of previous messages, each with 'role' and 'content' to gives context to the model (e.g., [{'role': 'user', 'content': 'Hi'}])",
                        required=False
                    ),
                    ToolArgument(
                        name="max_tokens",
                        arg_type="integer",
                        description="Maximum number of tokens to generate (default 2000)",
                        required=False
                    )
                ],
                return_type="string"
            )
            self.config = config or {}
            self.model: str = self._resolve_model(model)
            self.timeout: int = self._resolve_timeout(timeout)
        except Exception as e:
            logger.error(f"Failed to initialize AgentTool: {e}")
            raise

    def _resolve_model(self, model: Optional[str]) -> str:
        """Resolve the model from config, argument, or environment variable."""
        try:
            return self.config.get("model", model) or os.getenv("AGENT_MODEL", "gemini/gemini-2.0-flash")
        except Exception as e:
            logger.error(f"Error resolving model: {e}. Using default.")
            return "gemini/gemini-2.0-flash"

    def _resolve_timeout(self, timeout: Optional[int]) -> int:
        """Resolve the timeout from config, argument, or environment variable."""
        try:
            return self.config.get("timeout", timeout) or int(os.getenv("AGENT_TIMEOUT", "30"))
        except (ValueError, TypeError) as e:
            logger.error(f"Error resolving timeout: {e}. Using default.")
            return 30

    @log_tool_method
    async def async_execute(self, **kwargs) -> str:
        """Execute the tool asynchronously with error handling."""
        try:
            system_prompt: str = kwargs["system_prompt"]
            prompt: str = kwargs["prompt"]
            temperature: float = float(kwargs["temperature"])
            history: Optional[List[Dict[str, str]]] = kwargs.get("history", None)
            max_tokens: int = int(kwargs.get("max_tokens", 2000))

            if not 0 <= temperature <= 1:
                raise ValueError("Temperature must be between 0 and 1")

            messages = [{"role": "system", "content": system_prompt}]
            if history:
                if not isinstance(history, list):
                    raise ValueError("history must be a list")
                for msg in history:
                    if not isinstance(msg, dict) or "role" not in msg or "content" not in msg:
                        raise ValueError("Each message in history must be a dict with 'role' and 'content'")
                messages.extend(history)
            messages.append({"role": "user", "content": prompt})

            logger.info(f"Generating with {self.model}, temp={temperature}, max_tokens={max_tokens}, timeout={self.timeout}s, history={len(history or [])} messages")
            async with AsyncExitStack() as stack:
                await stack.enter_async_context(asyncio.timeout(self.timeout))
                try:
                    response = await litellm.acompletion(
                        model=self.model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    result = response.choices[0].message.content.strip()
                    logger.info(f"AgentTool generated text successfully: {result[:50]}...")
                    return result
                except Exception as e:
                    error_msg = f"Error: Unable to generate text due to {str(e)}"
                    logger.error(f"AgentTool failed: {e}")
                    return error_msg
        except TimeoutError:
            logger.error(f"AgentTool execution timed out after {self.timeout}s")
            return "Error: Execution timed out"
        except Exception as e:
            logger.error(f"Unexpected error in AgentTool execution: {e}")
            return f"Error: {str(e)}"
