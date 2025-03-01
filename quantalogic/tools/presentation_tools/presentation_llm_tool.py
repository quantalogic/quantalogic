"""Specialized LLM Tool for formatting and structuring content presentations."""

from typing import Callable, ClassVar, Dict, Literal

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
                    "'bullet_points', 'tutorial', 'api_doc', 'article', "
                    "'html_doc', 'slide_deck', 'code_review', 'release_notes', "
                    "'user_guide', 'research_paper', 'database_doc', 'analytics_report'"
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
            ToolArgument(
                name="additional_info",
                arg_type="string",
                description=(
                    "Optional additional notes or requirements for formatting. "
                    "These will be added as extra instructions to the formatter."
                ),
                required=False,
                example="Please make it concise and focus on technical accuracy."
            ),
        ]
    )

    model_name: str = Field(..., description="The name of the language model to use")
    system_prompt: str = Field(
        default=(
            "You are an expert content formatter and technical writer specializing in creating "
            "clear, well-structured, and professional presentations. Your role is to take "
            "raw content and transform it into the requested format while:"
            "\n- Maintaining accuracy and technical precision"
            "\n- Ensuring clear hierarchical structure"
            "\n- Following consistent formatting standards"
            "\n- Using appropriate professional tone"
            "\n- Creating logical information flow"
            "\n- Emphasizing key points effectively"
            "\n- Adapting detail level to format and audience"
            "\n- Incorporating relevant examples and references"
            "\n- Following industry best practices for each format"
        )
    )
    additional_info: str | None = Field(default=None, description="Default additional formatting instructions")
    on_token: Callable | None = Field(default=None, exclude=True)
    generative_model: GenerativeModel | None = Field(default=None, exclude=True)
    event_emitter: EventEmitter | None = Field(default=None, exclude=True)

    FORMAT_PROMPTS: ClassVar[Dict[str, str]] = {
        "technical_doc": (
            "Format this as a comprehensive technical documentation with:"
            "\n- Clear hierarchical sections and subsections"
            "\n- Properly formatted code examples and technical details"
            "\n- Implementation details and considerations"
            "\n- Prerequisites and dependencies"
            "\n- Troubleshooting guidelines"
        ),
        "executive_summary": (
            "Create a concise executive summary that:"
            "\n- Highlights key points, decisions, and outcomes"
            "\n- Uses business-friendly language"
            "\n- Includes actionable insights"
            "\n- Provides clear recommendations"
            "\n- Summarizes impact and value"
        ),
        "markdown": (
            "Convert this content into well-structured markdown with:"
            "\n- Appropriate heading levels"
            "\n- Properly formatted lists and tables"
            "\n- Code blocks with language specification"
            "\n- Links and references"
            "\n- Emphasis and formatting for readability"
        ),
        "bullet_points": (
            "Transform this into a clear hierarchical bullet-point format with:"
            "\n- Main points and key takeaways"
            "\n- Organized sub-points and details"
            "\n- Consistent formatting and indentation"
            "\n- Clear relationships between points"
        ),
        "tutorial": (
            "Structure this as a comprehensive tutorial with:"
            "\n- Clear prerequisites and setup instructions"
            "\n- Step-by-step guidance with examples"
            "\n- Common pitfalls and solutions"
            "\n- Practice exercises or challenges"
            "\n- Further learning resources"
        ),
        "api_doc": (
            "Format this as detailed API documentation including:"
            "\n- Endpoint descriptions and URLs"
            "\n- Request/response formats and examples"
            "\n- Authentication requirements"
            "\n- Error handling and status codes"
            "\n- Usage examples and best practices"
        ),
        "article": (
            "Format this as an engaging article with:"
            "\n- Compelling introduction and conclusion"
            "\n- Clear sections and transitions"
            "\n- Supporting examples and evidence"
            "\n- Engaging writing style"
            "\n- Key takeaways or summary"
        ),
        "html_doc": (
            "Format this as HTML documentation with:"
            "\n- Semantic HTML structure"
            "\n- Navigation and table of contents"
            "\n- Code examples with syntax highlighting"
            "\n- Cross-references and links"
            "\n- Responsive layout considerations"
        ),
        "slide_deck": (
            "Structure this as presentation slides with:"
            "\n- Clear title and agenda"
            "\n- One main point per slide"
            "\n- Supporting visuals or diagrams"
            "\n- Speaker notes or talking points"
            "\n- Call to action or next steps"
        ),
        "code_review": (
            "Format this as a detailed code review with:"
            "\n- Code quality assessment"
            "\n- Performance considerations"
            "\n- Security implications"
            "\n- Suggested improvements"
            "\n- Best practices alignment"
        ),
        "release_notes": (
            "Structure this as release notes with:"
            "\n- Version and date information"
            "\n- New features and enhancements"
            "\n- Bug fixes and improvements"
            "\n- Breaking changes"
            "\n- Upgrade instructions"
        ),
        "user_guide": (
            "Format this as a user guide with:"
            "\n- Getting started instructions"
            "\n- Feature explanations and use cases"
            "\n- Configuration options"
            "\n- Troubleshooting steps"
            "\n- FAQs and support information"
        ),
        "research_paper": (
            "Structure this as a research paper with:"
            "\n- Abstract and introduction"
            "\n- Methodology and approach"
            "\n- Results and analysis"
            "\n- Discussion and implications"
            "\n- References and citations"
        ),
        "database_doc": (
            "Format this as a comprehensive database documentation with:"
            "\n- Schema overview and ER diagrams (in text/ascii format)"
            "\n- Table descriptions and relationships"
            "\n- Column details (name, type, constraints, indexes)"
            "\n- Primary and foreign key relationships"
            "\n- Common queries and use cases"
            "\n- Performance considerations"
            "\n- Data integrity rules"
            "\n- Security and access control"
        ),
        "analytics_report": (
            "Structure this as a data analytics report with:"
            "\n- Key metrics and KPIs"
            "\n- Data summary and statistics"
            "\n- Trend analysis and patterns"
            "\n- Visual representations (in text/ascii format)"
            "\n- Correlations and relationships"
            "\n- Insights and findings"
            "\n- Recommendations based on data"
            "\n- Data quality notes"
            "\n- Methodology and data sources"
        ),
    }

    def __init__(
        self,
        model_name: str,
        on_token: Callable | None = None,
        name: str = "presentation_llm_tool",
        generative_model: GenerativeModel | None = None,
        event_emitter: EventEmitter | None = None,
        additional_info: str | None = None,
    ):
        """Initialize the Presentation LLM tool.
        
        Args:
            model_name (str): Name of the language model to use
            on_token (Callable | None): Optional callback for token streaming
            name (str): Name of the tool
            generative_model (GenerativeModel | None): Optional pre-configured model
            event_emitter (EventEmitter | None): Optional event emitter
            additional_info (str | None): Default additional formatting instructions
        """
        super().__init__(
            **{
                "model_name": model_name,
                "on_token": on_token,
                "name": name,
                "generative_model": generative_model,
                "event_emitter": event_emitter,
                "additional_info": additional_info,
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
            "article",
            "html_doc",
            "slide_deck",
            "code_review",
            "release_notes",
            "user_guide",
            "research_paper",
            "database_doc",
            "analytics_report",
        ],
        temperature: str = "0.3",
        additional_info: str | None = None,
    ) -> str:
        """Execute the tool to format the content according to the specified style.

        Args:
            content (str): The raw content to be formatted
            format_style (str): The desired presentation format
            temperature (str): Sampling temperature, defaults to "0.3"
            additional_info (str | None): Optional additional notes or requirements for formatting.
                If not provided, will use the default additional_info set during initialization.
                Example: "Please make it concise and focus on technical accuracy."

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
        
        # Use provided additional_info or fall back to default
        info_to_use = additional_info if additional_info is not None else self.additional_info
        
        # Add additional formatting instructions if provided
        additional_instructions = ""
        if info_to_use:
            additional_instructions = f"\n\nAdditional requirements:\n{info_to_use}"
        
        messages_history = [
            Message(role="system", content=self.system_prompt),
            Message(
                role="user",
                content=(
                    f"{format_prompt}\n{additional_instructions}\n\n"
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
