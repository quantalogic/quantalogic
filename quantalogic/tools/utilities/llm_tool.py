"""LLM Tool for generating answers to questions using a language model."""

import asyncio
from typing import Callable

from loguru import logger
from pydantic import ConfigDict, Field

from quantalogic.console_print_token import console_print_token
from quantalogic.event_emitter import EventEmitter
from quantalogic.generative_model import GenerativeModel, Message
from quantalogic.tools.tool import Tool, ToolArgument


class OrientedLLMTool(Tool):
    """Tool to generate answers using a specified language model."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    name: str = Field(default="oriented_llm_tool")
    description: str = Field(
        default=(
            "An advanced language model tool that generates contextually aware and role-specific responses. "
            "Features:\n"
            "- Role-based responses: Adapts to specific personas or expertise areas\n"
            "- Context awareness: Maintains conversation context for more relevant responses\n"
            "- Structured system prompts: Uses well-defined prompts for consistent behavior\n"
            "\nNote: This tool operates in isolation and requires:\n"
            "- Explicit context in prompts\n"
            "- Variable interpolation (e.g., $var1$)\n"
            "- All necessary information provided in the prompt"
        )
    )
    arguments: list = Field(
        default=[
            ToolArgument(
                name="role",
                arg_type="string",
                description="The specific role or persona the LLM should adopt (e.g., 'python_expert', 'data_scientist', 'technical_writer')",
                required=False,
                default="general_assistant",
                example="python_expert",
            ),
            ToolArgument(
                name="context",
                arg_type="string",
                description="Previous context or relevant information to consider for the response",
                required=False,
                default=None,
                example="Previously discussed Python best practices and PEP8 guidelines",
            ),
            ToolArgument(
                name="system_prompt",
                arg_type="string",
                description="Structured guidelines for the model's behavior and response format",
                required=True,
                example=(
                    "You are an expert Python developer with deep knowledge of best practices.\n"
                    "Follow these guidelines:\n"
                    "1. Provide clear, concise explanations\n"
                    "2. Include relevant code examples\n"
                    "3. Reference official documentation when appropriate\n"
                    "4. Highlight potential pitfalls and edge cases"
                ),
            ),
            ToolArgument(
                name="prompt",
                arg_type="string",
                description="The main question or task for the language model",
                required=True,
                example="What are the best practices for handling exceptions in Python?",
            ),
            ToolArgument(
                name="temperature",
                arg_type="string",
                description='Sampling temperature between "0.0" (precise) and "1.0" (creative)',
                required=True,
                default="0.5",
                example="0.7",
            ),
        ]
    )

    model_name: str = Field(..., description="The name of the language model to use")
    role: str = Field(default="general_assistant", description="The specific role or persona for the LLM")
    context: str | None = Field(default=None, description="Previous context or relevant information")
    system_prompt: str | None = Field(default=None, description="Structured guidelines for model behavior")
    on_token: Callable | None = Field(default=None, exclude=True)
    generative_model: GenerativeModel | None = Field(default=None, exclude=True)
    event_emitter: EventEmitter | None = Field(default=None, exclude=True)

    def __init__(
        self,
        model_name: str,
        role: str = "general_assistant",
        context: str | None = None,
        system_prompt: str | None = None,
        on_token: Callable | None = None,
        name: str = "oriented_llm_tool",
        generative_model: GenerativeModel | None = None,
        event_emitter: EventEmitter | None = None,
    ):
        """Initialize the OrientedLLMTool with model configuration and optional callback.

        Args:
            model_name (str): The name of the language model to use.
            system_prompt (str, optional): Default system prompt for the model.
            on_token (Callable, optional): Callback function for streaming tokens.
            name (str): Name of the tool instance. Defaults to "llm_tool".
            generative_model (GenerativeModel, optional): Pre-initialized generative model.
        """
        # Use dict to pass validated data to parent constructor
        super().__init__(
            **{
                "model_name": model_name,
                "role": role,
                "context": context,
                "system_prompt": system_prompt,
                "on_token": on_token,
                "name": name,
                "generative_model": generative_model,
                "event_emitter": event_emitter,
            }
        )
        
        # Initialize the generative model
        self.model_post_init(None)

    def model_post_init(self, __context):
        """Initialize the generative model after model initialization."""
        if self.generative_model is None:
            self.generative_model = GenerativeModel(
                model=self.model_name,
                event_emitter=self.event_emitter
            )
            logger.debug(f"Initialized OrientedLLMTool with model: {self.model_name}")

        # Only set up event listener if on_token is provided
        if self.on_token is not None:
            logger.debug(f"Setting up event listener for OrientedLLMTool with model: {self.model_name}")
            self.generative_model.event_emitter.on("stream_chunk", self.on_token)

    async def async_execute(
        self, role: str | None = None, context: str | None = None,
        system_prompt: str | None = None, prompt: str | None = None,
        temperature: str | None = None
    ) -> str:
        """Execute the tool to generate an answer asynchronously.

        This method provides a native asynchronous implementation, utilizing the generative model's
        asynchronous capabilities for improved performance in async contexts.

        Args:
            system_prompt (str, optional): The system prompt to guide the model.
            prompt (str, optional): The question to be answered.
            temperature (str, optional): Sampling temperature. Defaults to "0.7".

        Returns:
            str: The generated answer.

        Raises:
            ValueError: If temperature is not a valid float between 0 and 1.
            Exception: If there's an error during response generation.
        """
        try:
            temp = float(temperature)
            if not (0.0 <= temp <= 1.0):
                raise ValueError("Temperature must be between 0 and 1.")
        except ValueError as ve:
            logger.error(f"Invalid temperature value: {temperature}")
            raise ValueError(f"Invalid temperature value: {temperature}") from ve

        # Use provided values or fall back to instance defaults
        used_role = role if role is not None else self.role
        used_context = context if context is not None else self.context
        used_system_prompt = system_prompt if system_prompt is not None else self.system_prompt

        # Build enhanced system prompt with role and context
        final_system_prompt = f"Role: {used_role}\n"
        if used_context:
            final_system_prompt += f"Context: {used_context}\n"
        final_system_prompt += f"Instructions: {used_system_prompt}"

        # Prepare the messages history
        messages_history = [
            Message(role="system", content=final_system_prompt),
        ]

        is_streaming = self.on_token is not None

        # Set the model's temperature
        if self.generative_model:
            self.generative_model.temperature = temp

            # Generate the response asynchronously using the generative model
            try:
                result = await self.generative_model.async_generate_with_history(
                    messages_history=messages_history, prompt=prompt, streaming=is_streaming
                )

                if is_streaming:
                    response = ""
                    async for chunk in result:
                        response += chunk
                        # Note: on_token is handled via the event emitter set in model_post_init
                else:
                    response = result.response

                logger.debug(f"Generated async response: {response}")
                return response
            except Exception as e:
                logger.error(f"Error generating async response: {e}")
                raise Exception(f"Error generating async response: {e}") from e
        else:
            raise ValueError("Generative model not initialized")


if __name__ == "__main__":
    # Example usage of OrientedLLMTool
    tool = OrientedLLMTool(model_name="openrouter/openai/gpt-4o-mini")
    system_prompt = 'Answer the question as truthfully as possible using the provided context, and if the answer is not contained within the context, say "I don\'t know".'
    question = "What is the meaning of life?"
    temperature = "0.7"

    # Synchronous execution
    answer = tool.execute(system_prompt=system_prompt, prompt=question, temperature=temperature)
    print("Synchronous Answer:")
    print(answer)

    # Asynchronous execution with streaming
    pirate = OrientedLLMTool(
        model_name="openrouter/openai/gpt-4o-mini", system_prompt="You are a pirate.", on_token=console_print_token
    )
    pirate_answer = asyncio.run(
        pirate.async_execute(system_prompt=system_prompt, prompt=question, temperature=temperature)
    )
    print("\nAsynchronous Pirate Answer:")
    print(f"Answer: {pirate_answer}")

    # Display tool configuration in Markdown
    custom_tool = OrientedLLMTool(
        model_name="openrouter/openai/gpt-4o-mini", system_prompt="You are a pirate.", on_token=console_print_token
    )
    print("\nTool Configuration:")
    print(custom_tool.to_markdown())
