"""LLM Vision Tool for analyzing images using a language model."""

from typing import Optional

from loguru import logger
from pydantic import ConfigDict, Field

from quantalogic.generative_model import GenerativeModel, Message
from quantalogic.tools.tool import Tool, ToolArgument

# DEFAULT_MODEL_NAME = "ollama/llama3.2-vision"
DEFAULT_MODEL_NAME = "openrouter/openai/gpt-4o-mini"


class LLMVisionTool(Tool):
    """Tool to analyze images using a specified language model."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    name: str = Field(default="llm_vision_tool")
    description: str = Field(
        default=(
            "Analyzes images and generates responses using a specified language model. "
            "Supports multimodal input combining text and images."
        )
    )
    arguments: list = Field(
        default=[
            ToolArgument(
                name="system_prompt",
                arg_type="string",
                description="The system prompt to guide the model's behavior",
                required=True,
                example="You are an expert in image analysis and visual understanding.",
            ),
            ToolArgument(
                name="prompt",
                arg_type="string",
                description="The question or instruction about the image",
                required=True,
                example="What is shown in this image?",
            ),
            ToolArgument(
                name="image_url",
                arg_type="string",
                description="URL of the image to analyze",
                required=True,
                example="https://example.com/image.jpg",
            ),
            ToolArgument(
                name="temperature",
                arg_type="string",
                description='Sampling temperature between "0.0" and "1.0"',
                required=True,
                default="0.7",
                example="0.7",
            ),
        ]
    )

    model_name: str = Field(..., description="The name of the language model to use")
    generative_model: Optional[GenerativeModel] = Field(default=None)

    def model_post_init(self, __context):
        """Initialize the generative model after model initialization."""
        if self.generative_model is None:
            self.generative_model = GenerativeModel(model=self.model_name)
            logger.debug(f"Initialized LLMVisionTool with model: {self.model_name}")

        # Only set up event listener if on_token is provided
        if self.on_token is not None:
            logger.debug(f"Setting up event listener for LLMVisionTool with model: {self.model_name}")
            self.generative_model.event_emitter.on("stream_chunk", self.on_token)

    def execute(self, system_prompt: str, prompt: str, image_url: str, temperature: str = "0.7") -> str:
        """Execute the tool to analyze an image and generate a response.

        Args:
            system_prompt: The system prompt to guide the model
            prompt: The question or instruction about the image
            image_url: URL of the image to analyze
            temperature: Sampling temperature

        Returns:
            The generated response

        Raises:
            ValueError: If temperature is invalid or image_url is malformed
            Exception: If there's an error during response generation
        """
        try:
            temp = float(temperature)
            if not (0.0 <= temp <= 1.0):
                raise ValueError("Temperature must be between 0 and 1.")
        except ValueError as ve:
            logger.error(f"Invalid temperature value: {temperature}")
            raise ValueError(f"Invalid temperature value: {temperature}") from ve

        if not image_url.startswith(("http://", "https://")):
            raise ValueError("Image URL must start with http:// or https://")

        # Prepare the messages history
        messages_history = [
            Message(role="system", content=system_prompt),
        ]

        if self.generative_model is None:
            self.generative_model = GenerativeModel(model=self.model_name)

        self.generative_model.temperature = temp

        try:
            is_streaming = self.on_token is not None
            response_stats = self.generative_model.generate_with_history(
                messages_history=messages_history,
                prompt=prompt,
                image_url=image_url,
                streaming=is_streaming
            )

            if is_streaming:
                response = ""
                for chunk in response_stats:
                    response += chunk
            else:
                response = response_stats.response.strip()

            logger.info(f"Generated response: {response}")
            return response
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise Exception(f"Error generating response: {e}") from e


if __name__ == "__main__":
    # Example usage
    tool = LLMVisionTool(model_name=DEFAULT_MODEL_NAME)
    system_prompt = "You are a vision expert."
    question = "What is shown in this image? Describe it with details."
    image_url = "https://fastly.picsum.photos/id/767/200/300.jpg?hmac=j5YA1cRw-jS6fK3Mx2ooPwl2_TS3RSyLmFmiM9TqLC4"
    temperature = "0.7"
    answer = tool.execute(system_prompt=system_prompt, prompt=question, image_url=image_url, temperature=temperature)
    print(answer)
