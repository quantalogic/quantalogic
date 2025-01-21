"""LLM Tool for generating answers to questions using a language model."""

from typing import Callable

from loguru import logger
from pydantic import ConfigDict, Field

from quantalogic.console_print_token import console_print_token
from quantalogic.generative_model import GenerativeModel, Message
from quantalogic.tools.tool import Tool, ToolArgument


class LLMTool(Tool):
    """Tool to generate answers using a specified language model."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    name: str = Field(default="llm_tool")
    description: str = Field(
        default=(
            "Generates answers to questions using a specified language model. "
            "Note: This tool operates in total isolation and does not have access to: "
            " - Memory: All context must be explicitly provided in the prompt. "
            " - File system."
            " - Variables: Any required variables should be interpolated into the prompt (e.g., $var1$). "
            " - No access to Tools, URL, file, or other external resources. "
            "Ensure all necessary information is included directly in your prompt."
        )
    )
    arguments: list = Field(
        default=[
            ToolArgument(
                name="system_prompt",
                arg_type="string",
                description=("The persona or system prompt to guide the language model's behavior. "),
                required=True,
                example=("You are an expert in natural language processing and machine learning. "),
            ),
            ToolArgument(
                name="prompt",
                arg_type="string",
                description=("The question to ask the language model. Use interpolation if possible example $var1$."),
                required=True,
                example="What is the meaning of $var1$ ?",
            ),
            ToolArgument(
                name="temperature",
                arg_type="string",
                description='Sampling temperature between "0.0" and "1.0": "0.0" no creativity, "1.0" full creativity. (float)',
                required=True,
                default="0.5",
                example="0.5",
            ),
        ]
    )

    model_name: str = Field(..., description="The name of the language model to use")
    system_prompt: str | None = Field(default=None)
    on_token: Callable | None = Field(default=None, exclude=True)
    generative_model: GenerativeModel | None = Field(default=None, exclude=True)

    def __init__(
        self,
        model_name: str,
        system_prompt: str | None = None,
        on_token: Callable | None = None,
        name: str = "llm_tool",
        generative_model: GenerativeModel | None = None,
    ):
        # Use dict to pass validated data to parent constructor
        super().__init__(
            **{
                "model_name": model_name,
                "system_prompt": system_prompt,
                "on_token": on_token,
                "name": name,
                "generative_model": generative_model,
            }
        )

        # Initialize the generative model
        self.model_post_init(None)

    def model_post_init(self, __context):
        """Initialize the generative model after model initialization."""
        if self.generative_model is None:
            self.generative_model = GenerativeModel(model=self.model_name)
            logger.debug(f"Initialized LLMTool with model: {self.model_name}")

        # Only set up event listener if on_token is provided
        if self.on_token is not None:
            logger.debug(f"Setting up event listener for LLMTool with model: {self.model_name}")
            self.generative_model.event_emitter.on("stream_chunk", self.on_token)

    def execute(
        self, system_prompt: str | None = None, prompt: str | None = None, temperature: str | None = None
    ) -> str:
        """Execute the tool to generate an answer based on the provided question.

        Args:
            system_prompt (str): The system prompt to guide the model.
            prompt (str): The question to be answered.
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

        used_system_prompt = self.system_prompt if self.system_prompt else system_prompt

        # Prepare the messages history
        messages_history = [
            Message(role="system", content=used_system_prompt),
        ]

        is_streaming = self.on_token is not None

        # Set the model's temperature
        if self.generative_model:
            self.generative_model.temperature = temp

            # Generate the response using the generative model
            try:
                result = self.generative_model.generate_with_history(
                    messages_history=messages_history, prompt=prompt, streaming=is_streaming
                )

                if is_streaming:
                    response = ""
                    for chunk in result:
                        response += chunk
                else:
                    response = result.response

                logger.debug(f"Generated response: {response}")
                return response
            except Exception as e:
                logger.error(f"Error generating response: {e}")
                raise Exception(f"Error generating response: {e}") from e
        else:
            raise ValueError("Generative model not initialized")


if __name__ == "__main__":
    # Example usage of LLMTool
    tool = LLMTool(model_name="openrouter/openai/gpt-4o-mini")
    system_prompt = 'Answer the question as truthfully as possible using the provided context, and if the answer is not contained within the context, say "I don\'t know".'
    question = "What is the meaning of life?"
    temperature = "0.7"
    answer = tool.execute(system_prompt=system_prompt, prompt=question, temperature=temperature)
    print(answer)
    pirate = LLMTool(
        model_name="openrouter/openai/gpt-4o-mini", system_prompt="You are a pirate.", on_token=console_print_token
    )
    pirate_answer = pirate.execute(system_prompt=system_prompt, prompt=question, temperature=temperature)
    print("\n")
    print(f"Anwser: {pirate_answer}")

    custom_tool = LLMTool(
        model_name="openrouter/openai/gpt-4o-mini", system_prompt="You are a pirate.", on_token=console_print_token
    )
    print(custom_tool.to_markdown())
