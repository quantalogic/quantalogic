"""Legal-oriented LLM Tool for generating answers using retrieved legal context."""

import asyncio
from typing import Callable, Dict, List, Optional, Union

from loguru import logger
from pydantic import ConfigDict, Field

from quantalogic.console_print_token import console_print_token
from quantalogic.event_emitter import EventEmitter
from quantalogic.generative_model import GenerativeModel, Message
from quantalogic.tools.tool import Tool, ToolArgument


class OrientedLLMTool(Tool):
    """Advanced LLM tool specialized for legal analysis and response generation."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    name: str = Field(default="legal_llm_tool")
    description: str = Field(
        default=(
            "A specialized legal language model tool that generates expert legal analysis and responses. "
            "Features:\n"
            "- Legal expertise: Specialized in legal analysis and interpretation\n"
            "- Context integration: Utilizes retrieved legal documents and precedents\n"
            "- Multi-jurisdictional: Handles multiple legal systems and languages\n"
            "- Citation support: Properly cites legal sources and precedents\n"
            "\nCapabilities:\n"
            "- Legal document analysis\n"
            "- Statutory interpretation\n"
            "- Case law analysis\n"
            "- Regulatory compliance guidance"
        )
    )
    arguments: list = Field(
        default=[
            ToolArgument(
                name="role",
                arg_type="string",
                description="Legal specialization (e.g., 'commercial_law', 'environmental_law', 'constitutional_law')",
                required=True,
                default="general_legal_expert",
            ),
            ToolArgument(
                name="legal_context",
                arg_type="string",
                description="Retrieved legal documents, precedents, and relevant context from RAG tool",
                required=True,
            ),
            ToolArgument(
                name="jurisdiction",
                arg_type="string",
                description="Relevant legal jurisdiction(s) for analysis",
                required=True,
                default="general",
            ),
            ToolArgument(
                name="query_type",
                arg_type="string",
                description="Type of legal analysis needed (e.g., 'interpretation', 'compliance', 'comparison')",
                required=True,
                default="interpretation",
            ),
            ToolArgument(
                name="prompt",
                arg_type="string",
                description="Specific legal question or analysis request",
                required=True,
            ),
            ToolArgument(
                name="temperature",
                arg_type="float",
                description="Response precision (0.0 for strict legal interpretation, 1.0 for creative analysis)",
                required=False,
                default="0.3",
            ),
        ]
    )

    model_name: str = Field(..., description="The name of the language model to use")
    role: str = Field(default="general_legal_expert", description="The specific role or persona for the LLM")
    jurisdiction: str = Field(default="general", description="The relevant jurisdiction for the LLM")
    on_token: Callable | None = Field(default=None, exclude=True)
    generative_model: GenerativeModel | None = Field(default=None, exclude=True)
    event_emitter: EventEmitter | None = Field(default=None, exclude=True)

    def __init__(
        self,
        model_name: str,
        name: str = "legal_llm_tool",
        role: str = "general_legal_expert",
        jurisdiction: str = "general",
        on_token: Optional[Callable] = None,
        event_emitter: Optional[EventEmitter] = None,
    ):
        """Initialize the Legal LLM Tool.

        Args:
            model_name: Name of the language model
            role: Legal specialization role
            jurisdiction: Default jurisdiction
            on_token: Optional callback for token streaming
            event_emitter: Optional event emitter for streaming
        """
        super().__init__(
            model_name=model_name,
            name=name,
            role=role,
            jurisdiction=jurisdiction,
            on_token=on_token,
            event_emitter=event_emitter,
        )
        
        self.model_name = model_name
        self.role = role
        self.jurisdiction = jurisdiction
        self.on_token = on_token
        self.event_emitter = event_emitter
        self.generative_model = None
        
        # Initialize the model
        self.model_post_init(None)

    def model_post_init(self, __context):
        """Initialize the generative model with legal-specific configuration."""
        if self.generative_model is None:
            self.generative_model = GenerativeModel(
                model=self.model_name,
                event_emitter=self.event_emitter
            )
            logger.debug(f"Initialized Legal LLM Tool with model: {self.model_name}")

        if self.on_token is not None:
            self.generative_model.event_emitter.on("stream_chunk", self.on_token)

    def _build_legal_system_prompt(
        self,
        role: str,
        jurisdiction: str,
        query_type: str,
        legal_context: Union[str, Dict, List]
    ) -> str:
        """Build a specialized legal system prompt.

        Args:
            role: Legal specialization role
            jurisdiction: Relevant jurisdiction
            query_type: Type of legal analysis
            legal_context: Retrieved legal context from RAG

        Returns:
            Structured system prompt for legal analysis
        """
        # Format legal context if it's not a string
        if not isinstance(legal_context, str):
            legal_context = str(legal_context)

        system_prompt = f"""You are an expert legal advisor specialized in {role}.
Jurisdiction: {jurisdiction}
Analysis Type: {query_type}

Your task is to provide a well-reasoned legal analysis based on the following context:

{legal_context}

Guidelines:
1. Base your analysis strictly on provided legal sources
2. Cite specific articles, sections, and precedents
3. Consider jurisdictional context and limitations
4. Highlight any legal uncertainties or ambiguities
5. Provide clear, actionable conclusions

Format your response as follows:
1. Legal Analysis
2. Relevant Citations
3. Key Considerations
4. Conclusion

Remember: If a legal point is not supported by the provided context, acknowledge the limitation."""

        return system_prompt

    async def async_execute(
        self,
        prompt: str,
        legal_context: Union[str, Dict, List],
        role: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        query_type: str = "interpretation",
        temperature: float = 0.3
    ) -> str:
        """Execute legal analysis asynchronously.

        Args:
            prompt: Legal question or analysis request
            legal_context: Retrieved legal documents and context
            role: Optional override for legal specialization
            jurisdiction: Optional override for jurisdiction
            query_type: Type of legal analysis needed
            temperature: Response precision (0.0-1.0)

        Returns:
            Detailed legal analysis and response
        """
        try:
            if not (0.0 <= temperature <= 1.0):
                raise ValueError("Temperature must be between 0 and 1")

            used_role = role or self.role
            used_jurisdiction = jurisdiction or self.jurisdiction

            system_prompt = self._build_legal_system_prompt(
                used_role,
                used_jurisdiction,
                query_type,
                legal_context
            )

            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=prompt)
            ]

            if self.generative_model:
                self.generative_model.temperature = temperature
                
                is_streaming = self.on_token is not None
                result = await self.generative_model.async_generate_with_history(
                    messages_history=messages,
                    prompt=prompt,
                    streaming=is_streaming
                )

                if is_streaming:
                    response = ""
                    async for chunk in result:
                        response += chunk
                else:
                    response = result.response

                logger.info(f"Generated legal analysis for {query_type} query in {used_jurisdiction} jurisdiction")
                return response
            else:
                raise ValueError("Generative model not initialized")

        except Exception as e:
            logger.error(f"Error in legal analysis: {str(e)}")
            raise

    def execute(self, *args, **kwargs) -> str:
        """Synchronous wrapper for async_execute."""
        return asyncio.run(self.async_execute(*args, **kwargs))


if __name__ == "__main__":
    # Example usage of OrientedLLMTool
    tool = OrientedLLMTool(model_name="openrouter/openai/gpt-4o-mini")
    legal_context = "Retrieved legal documents and context from RAG tool"
    question = "What is the meaning of life?"
    temperature = 0.7

    # Synchronous execution
    answer = tool.execute(prompt=question, legal_context=legal_context, temperature=temperature)
    print("Synchronous Answer:")
    print(answer)

    # Asynchronous execution with streaming
    pirate = OrientedLLMTool(
        model_name="openrouter/openai/gpt-4o-mini", on_token=console_print_token
    )
    pirate_answer = asyncio.run(
        pirate.async_execute(prompt=question, legal_context=legal_context, temperature=temperature)
    )
    print("\nAsynchronous Pirate Answer:")
    print(f"Answer: {pirate_answer}")

    # Display tool configuration in Markdown
    custom_tool = OrientedLLMTool(
        model_name="openrouter/openai/gpt-4o-mini", on_token=console_print_token
    )
    print("\nTool Configuration:")
    print(custom_tool.to_markdown())
