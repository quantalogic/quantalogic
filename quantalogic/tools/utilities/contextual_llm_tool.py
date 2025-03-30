"""Enhanced Contextual LLM Tool with AgentMemory integration."""

import asyncio
from typing import Callable, Dict, Optional, Any

from loguru import logger
from pydantic import ConfigDict, Field

from quantalogic.console_print_token import console_print_token
from quantalogic.event_emitter import EventEmitter
from quantalogic.generative_model import GenerativeModel, Message
from quantalogic.tools.tool import Tool, ToolArgument
from quantalogic.memory import AgentMemory, VariableMemory


class ContextualLLMTool(Tool):
    """Enhanced LLM tool with integrated AgentMemory and role-based capabilities."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    name: str = Field(default="contextual_llm_tool")
    description: str = Field(
        default=(
            "Advanced LLM tool with memory and context management capabilities. Features:\n"
            " - Conversation history with automatic memory compaction\n"
            " - Role-based behavior with system prompts\n"
            " - Variable interpolation support\n"
            " - Streaming response capability\n"
            " - Context-aware responses"
        )
    )
    arguments: list = Field(
        default=[
            ToolArgument(
                name="role",
                arg_type="string",
                description="The specific role/persona for the model",
                required=True,
                example="python_expert",
            ),
            ToolArgument(
                name="prompt",
                arg_type="string",
                description="The question or task for the model. Supports variable interpolation",
                required=True,
                example="How do I implement $feature_name$ in Python?",
            ),
            ToolArgument(
                name="context",
                arg_type="string",
                description="Additional context for the current interaction",
                required=False,
                example="Using Python 3.12 with asyncio",
            ),
            ToolArgument(
                name="temperature",
                arg_type="string",
                description="Sampling temperature (0.0-1.0)",
                required=False,
                default="0.7",
                example="0.5",
            ),
        ]
    )

    # Core configuration
    model_name: str = Field(..., description="Name of the language model to use")
    agent_memory: AgentMemory = Field(default_factory=AgentMemory)
    variable_memory: VariableMemory = Field(default_factory=VariableMemory)
    
    # Role management
    current_role: str = Field(default=None)
    role_prompts: Dict[str, str] = Field(
        default_factory=dict,
        description="Role to system prompt mapping"
    )
    
    # Tool configuration
    generative_model: Optional[GenerativeModel] = Field(default=None, exclude=True)
    event_emitter: Optional[EventEmitter] = Field(default=None, exclude=True)
    on_token: Optional[Callable] = Field(default=None, exclude=True)

    def __init__(
        self,
        model_name: str,
        roles: Optional[Dict[str, str]] = None,
        on_token: Optional[Callable] = None,
        name: str = "contextual_llm_tool",
        generative_model: Optional[GenerativeModel] = None,
        event_emitter: Optional[EventEmitter] = None,
        memory_compact_threshold: int = 2,
    ):
        """Initialize the ContextualLLMTool.

        Args:
            model_name: Name of the language model
            roles: Dictionary mapping role names to system prompts
            on_token: Optional callback for token streaming
            name: Name of the tool instance
            generative_model: Optional pre-initialized model
            event_emitter: Optional event emitter
            memory_compact_threshold: Number of message pairs to keep after compaction
        """
        super().__init__(
            **{
                "model_name": model_name,
                "role_prompts": roles or {},
                "on_token": on_token,
                "name": name,
                "generative_model": generative_model,
                "event_emitter": event_emitter,
            }
        )
        
        self.memory_compact_threshold = memory_compact_threshold
        self.model_post_init(None)

    def model_post_init(self, __context):
        """Initialize the generative model and set up event listeners."""
        if self.generative_model is None:
            self.generative_model = GenerativeModel(
                model=self.model_name,
                event_emitter=self.event_emitter
            )
            logger.debug(f"Initialized ContextualLLMTool with model: {self.model_name}")

        if self.on_token is not None:
            self.generative_model.event_emitter.on("stream_chunk", self.on_token)

    def _get_role_prompt(self, role: str) -> str:
        """Get the system prompt for a specific role."""
        if role not in self.role_prompts:
            raise ValueError(f"Role '{role}' not found in defined roles")
        return self.role_prompts[role]

    def _prepare_conversation_history(self, role: str, context: Optional[str] = None) -> list[Message]:
        """Prepare conversation history with role and context."""
        messages = []
        
        # Add role-specific system prompt
        role_prompt = self._get_role_prompt(role)
        messages.append(Message(role="system", content=role_prompt))
        
        # Add current context if provided
        if context:
            messages.append(Message(role="system", content=f"Current context: {context}"))
        
        # Add conversation history from agent memory
        messages.extend(self.agent_memory.memory)
        
        return messages

    def _interpolate_variables(self, text: str) -> str:
        """Replace variable placeholders with their values."""
        for key, value in self.variable_memory.items():
            text = text.replace(f"${key}$", value)
        return text

    async def async_execute(
        self,
        role: str,
        prompt: str,
        context: Optional[str] = None,
        temperature: str = "0.7",
    ) -> str:
        """Execute the tool asynchronously with memory management.

        Args:
            role: The role/persona for the model
            prompt: The question or task
            context: Additional context for this interaction
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            The generated response

        Raises:
            ValueError: If parameters are invalid
            Exception: If there's an error during generation
        """
        try:
            temp = float(temperature)
            if not (0.0 <= temp <= 1.0):
                raise ValueError("Temperature must be between 0 and 1")
        except ValueError as ve:
            logger.error(f"Invalid temperature value: {temperature}")
            raise ValueError(f"Invalid temperature value: {temperature}") from ve

        # Interpolate variables in prompt
        processed_prompt = self._interpolate_variables(prompt)
        
        # Add user message to memory
        self.agent_memory.add(Message(role="user", content=processed_prompt))
        
        # Prepare conversation history
        messages = self._prepare_conversation_history(role, context)
        
        # Configure model
        if self.generative_model:
            self.generative_model.temperature = temp
            
            try:
                # Generate response
                is_streaming = self.on_token is not None
                result = await self.generative_model.async_generate_with_history(
                    messages_history=messages,
                    prompt=processed_prompt,
                    streaming=is_streaming
                )

                # Handle streaming or direct response
                if is_streaming:
                    response = ""
                    async for chunk in result:
                        response += chunk
                else:
                    response = result.response

                # Add assistant response to memory
                self.agent_memory.add(Message(role="assistant", content=response))
                
                # Compact memory if needed
                self.agent_memory.compact(n=self.memory_compact_threshold)

                logger.debug(f"Generated contextual response: {response}")
                return response

            except Exception as e:
                logger.error(f"Error generating response: {e}")
                raise Exception(f"Error generating response: {e}") from e
        else:
            raise ValueError("Generative model not initialized")

    def execute(self, *args, **kwargs) -> str:
        """Synchronous execution wrapper."""
        return asyncio.run(self.async_execute(*args, **kwargs))

    def reset_memory(self):
        """Reset both agent and variable memories."""
        self.agent_memory.reset()
        self.variable_memory.reset()


if __name__ == "__main__":
    # Example usage
    roles = {
        "python_expert": (
            "You are an expert Python developer with deep knowledge of best practices, "
            "design patterns, and the Python ecosystem."
        ),
        "code_reviewer": (
            "You are a thorough code reviewer focused on code quality, security, "
            "and maintainability."
        )
    }

    # Initialize tool with roles
    tool = ContextualLLMTool(
        model_name="openrouter/openai/gpt-4o-mini",
        roles=roles,
        on_token=console_print_token
    )

    # Example async usage with variable interpolation
    async def main():
        # Set a variable
        tool.variable_memory["feature_name"] = "async context managers"
        
        # Use as Python expert
        response = await tool.async_execute(
            role="python_expert",
            prompt="How do I implement $feature_name$ in Python?",
            context="Building a production-grade application",
            temperature="0.7"
        )
        print("\nPython Expert Response:")
        print(response)

        # Use as code reviewer
        response = await tool.async_execute(
            role="code_reviewer",
            prompt="Review this implementation of $feature_name$:\n\nclass AsyncContextManager:\n    async def __aenter__(self):\n        return self",
            context="Reviewing async utilities",
            temperature="0.7"
        )
        print("\nCode Reviewer Response:")
        print(response)

    # Run example
    asyncio.run(main())
