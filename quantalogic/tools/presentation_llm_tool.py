"""Specialized LLM Tool for formatting and structuring content presentations."""

from typing import Callable, Literal, ClassVar, Dict

from loguru import logger
from pydantic import ConfigDict, Field

from quantalogic.console_print_token import console_print_token
from quantalogic.event_emitter import EventEmitter
from quantalogic.generative_model import GenerativeModel, Message
from quantalogic.tools.tool import Tool, ToolArgument


class PresentationLLMTool(Tool):
    """Tool to format and structure content using a language model."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    name: str = Field(default="presentation_llm_tool")
    description: str = Field(
        default=(
            "Specializes in formatting and structuring content for presentation. "
            "Takes raw content and formats it according to specified presentation styles. "
            "Supports various output formats like markdown, bullet points, technical documentation, etc."
        )
    )
    arguments: list = Field(
        default=[
            ToolArgument(
                name="content",
                arg_type="string",
                description="The raw content to be formatted",
                required=True,
                example="Here's the raw analysis results and data...",
            ),
            ToolArgument(
                name="format_style",
                arg_type="string",
                description=(
                    "The desired presentation format. Options: "
                    "'technical_doc', 'executive_summary', 'markdown', "
                    "'bullet_points', 'tutorial', 'api_doc'"
                ),
                required=True,
                example="technical_doc",
            ),
            ToolArgument(
                name="temperature",
                arg_type="string",
                description='Sampling temperature between "0.0" and "1.0"',
                required=True,
                default="0.3",
                example="0.3",
            ),
        ]
    )

    model_name: str = Field(..., description="The name of the language model to use")
    system_prompt: str = Field(
        default=(
            "You are an expert content formatter specializing in creating clear, "
            "well-structured, and professional presentations. Your role is to take "
            "raw content and transform it into the requested format while maintaining "
            "accuracy and improving clarity. Focus on:"
            "\n- Clear hierarchical structure"
            "\n- Consistent formatting"
            "\n- Professional tone"
            "\n- Logical flow"
            "\n- Emphasis on key points"
            "\n- Appropriate level of detail for the format"
        )
    )
    on_token: Callable | None = Field(default=None, exclude=True)
    generative_model: GenerativeModel | None = Field(default=None, exclude=True)
    event_emitter: EventEmitter | None = Field(default=None, exclude=True)

    FORMAT_PROMPTS: ClassVar[Dict[str, str]] = {
        "technical_doc": (
            "Format this as a technical documentation with clear sections, "
            "code examples properly formatted, and technical details preserved."
        ),
        "executive_summary": (
            "Create a concise executive summary highlighting key points, "
            "decisions, and outcomes in a business-friendly format."
        ),
        "markdown": (
            "Convert this content into well-structured markdown format with "
            "appropriate headers, lists, code blocks, and emphasis."
        ),
        "bullet_points": (
            "Transform this into a clear bullet-point format with main points "
            "and sub-points properly organized and hierarchical."
        ),
        "tutorial": (
            "Structure this as a step-by-step tutorial with clear instructions, "
            "examples, and explanations suitable for learning."
        ),
        "api_doc": (
            "Format this as API documentation with clear endpoint descriptions, "
            "parameters, response formats, and examples."
        ),
    }

    def __init__(
        self,
        model_name: str,
        on_token: Callable | None = None,
        name: str = "presentation_llm_tool",
        generative_model: GenerativeModel | None = None,
        event_emitter: EventEmitter | None = None,
    ):
        """Initialize the Presentation LLM tool.
        
        Args:
            model_name (str): Name of the language model to use
            on_token (Callable | None): Optional callback for token streaming
            name (str): Name of the tool
            generative_model (GenerativeModel | None): Optional pre-configured model
            event_emitter (EventEmitter | None): Optional event emitter
        """
        super().__init__(
            **{
                "model_name": model_name,
                "on_token": on_token,
                "name": name,
                "generative_model": generative_model,
                "event_emitter": event_emitter,
            }
        )
        self.model_post_init(None)

    def model_post_init(self, __context):
        """Initialize the generative model after model initialization."""
        if self.generative_model is None:
            self.generative_model = GenerativeModel(
                model=self.model_name,
                event_emitter=self.event_emitter
            )
            logger.debug(f"Initialized PresentationLLMTool with model: {self.model_name}")

        if self.on_token is not None:
            logger.debug("Setting up event listener for PresentationLLMTool")
            self.generative_model.event_emitter.on("stream_chunk", self.on_token)

    def execute(
        self,
        content: str,
        format_style: Literal[
            "technical_doc",
            "executive_summary",
            "markdown",
            "bullet_points",
            "tutorial",
            "api_doc",
        ],
        temperature: str = "0.3",
    ) -> str:
        """Execute the tool to format the content according to the specified style.

        Args:
            content (str): The raw content to be formatted
            format_style (str): The desired presentation format
            temperature (str): Sampling temperature, defaults to "0.3"

        Returns:
            str: The formatted content

        Raises:
            ValueError: If temperature is invalid or format_style is not supported
        """
        try:
            temp = float(temperature)
            if not (0.0 <= temp <= 1.0):
                raise ValueError("Temperature must be between 0 and 1.")
        except ValueError as ve:
            logger.error(f"Invalid temperature value: {temperature}")
            raise ValueError(f"Invalid temperature value: {temperature}") from ve

        if format_style not in self.FORMAT_PROMPTS:
            raise ValueError(f"Unsupported format style: {format_style}")

        format_prompt = self.FORMAT_PROMPTS[format_style]
        
        messages_history = [
            Message(role="system", content=self.system_prompt),
            Message(
                role="user",
                content=(
                    f"{format_prompt}\n\n"
                    f"Here's the content to format:\n\n{content}"
                ),
            ),
        ]

        is_streaming = self.on_token is not None

        if self.generative_model:
            self.generative_model.temperature = temp

            try:
                result = self.generative_model.generate_with_history(
                    messages_history=messages_history,
                    prompt="",  # Prompt is already included in messages_history
                    streaming=is_streaming
                )

                if is_streaming:
                    response = ""
                    for chunk in result:
                        response += chunk
                else:
                    response = result.response

                logger.debug("Successfully formatted content")
                return response
            except Exception as e:
                logger.error(f"Error formatting content: {e}")
                raise Exception(f"Error formatting content: {e}") from e
        else:
            raise ValueError("Generative model not initialized")


if __name__ == "__main__":
    # Example usage
    formatter = PresentationLLMTool(
        model_name="openrouter/openai/gpt-4o-mini",
        on_token=console_print_token
    )
    
    raw_content = """
    Analysis results:
    - Found 3 critical bugs in the authentication system
    - Performance improved by 45% after optimization
    - New API endpoints added for user management
    - Database queries optimized
    - Added unit tests for core functions
    """
    
    # Format as technical documentation
    tech_doc = formatter.execute(
        content=raw_content,
        format_style="technical_doc",
        temperature="0.3"
    )
    print("\nTechnical Documentation Format:")
    print(tech_doc)
    
    # Format as bullet points
    bullets = formatter.execute(
        content=raw_content,
        format_style="bullet_points",
        temperature="0.3"
    )
    print("\nBullet Points Format:")
    print(bullets)
