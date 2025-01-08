"""LLM Tool for generating answers to questions using a language model."""

import logging

from pydantic import ConfigDict, Field

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
    generative_model: GenerativeModel | None = Field(default=None)
    system_prompt: str | None = Field(default=None)

    def model_post_init(self, __context):
        """Initialize the generative model after model initialization."""
        if self.generative_model is None:
            self.generative_model = GenerativeModel(model=self.model_name)
            logging.debug(f"Initialized LLMTool with model: {self.model_name}")


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
            logging.error(f"Invalid temperature value: {temperature}")
            raise ValueError(f"Invalid temperature value: {temperature}") from ve

        used_system_prompt = self.system_prompt if self.system_prompt else system_prompt

        # Prepare the messages history
        messages_history = [
            Message(role="system", content=used_system_prompt),
            Message(role="user", content=prompt),
        ]

        # Set the model's temperature
        if self.generative_model:
            self.generative_model.temperature = temp

            # Generate the response using the generative model
            try:
                response_stats = self.generative_model.generate_with_history(
                    messages_history=messages_history, prompt=""
                )
                response = response_stats.response.strip()
                logging.info(f"Generated response: {response}")
                return response
            except Exception as e:
                logging.error(f"Error generating response: {e}")
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
    pirate = LLMTool(model_name="openrouter/openai/gpt-4o-mini", system_prompt="You are a pirate.")
    pirate_answer = pirate.execute(system_prompt=system_prompt, prompt=question, temperature=temperature)
    print(pirate_answer)
