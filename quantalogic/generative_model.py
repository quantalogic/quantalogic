"""Generative model module for AI-powered text generation."""

import openai
from litellm import completion, exceptions, get_max_tokens, get_model_info, token_counter
from loguru import logger
from pydantic import BaseModel, Field, field_validator

MIN_RETRIES = 3


class Message(BaseModel):
    """Represents a message in a conversation with a specific role and content."""

    role: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)

    @field_validator("role", "content")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate that the field is not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace-only")
        return v


class TokenUsage(BaseModel):
    """Represents token usage statistics for a language model."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ResponseStats(BaseModel):
    """Represents detailed statistics for a model response."""

    response: str
    usage: TokenUsage
    model: str
    finish_reason: str | None = None


class GenerativeModel:
    """Generative model for AI-powered text generation with configurable parameters."""

    def __init__(
        self,
        model: str = "ollama/qwen2.5-coder:14b",
        temperature: float = 0.7,
    ) -> None:
        """Initialize a generative model with configurable parameters.

        Configure the generative model with specified model,
        temperature, and maximum token settings.

        Args:
            model: Model identifier.
                Defaults to "ollama/qwen2.5-coder:14b".
            temperature: Sampling temperature between 0 and 1.
                Defaults to 0.7.
        """
        self.model = model
        self.temperature = temperature

    # Define retriable exceptions based on LiteLLM's exception mapping
    RETRIABLE_EXCEPTIONS = (
        exceptions.RateLimitError,  # Rate limits - should retry
        exceptions.APIConnectionError,  # Connection issues - should retry
        exceptions.ServiceUnavailableError,  # Service issues - should retry
        exceptions.Timeout,  # Timeout - should retry
        exceptions.APIError,  # Generic API errors - should retry
    )

    # Non-retriable exceptions that need specific handling
    CONTEXT_EXCEPTIONS = (
        exceptions.ContextWindowExceededError,
        exceptions.InvalidRequestError,
    )

    POLICY_EXCEPTIONS = (exceptions.ContentPolicyViolationError,)

    AUTH_EXCEPTIONS = (
        exceptions.AuthenticationError,
        exceptions.PermissionDeniedError,
    )

    # Retry on specific retriable exceptions
    def generate_with_history(self, messages_history: list[Message], prompt: str) -> ResponseStats:
        """Generate a response with conversation history.

        Generates a response based on previous conversation messages
        and a new user prompt.

        Args:
            messages_history: Previous conversation messages.
            prompt: Current user prompt.

        Returns:
            Detailed response statistics.

        Raises:
            openai.AuthenticationError: If authentication fails.
            openai.InvalidRequestError: If the request is invalid (e.g., context length exceeded).
            openai.APIError: For content policy violations or other API errors.
            Exception: For other unexpected errors.
        """
        messages = [{"role": msg.role, "content": str(msg.content)} for msg in messages_history]
        messages.append({"role": "user", "content": str(prompt)})

        try:
            logger.debug(f"Generating response for prompt: {prompt}")

            response = completion(
                temperature=self.temperature,
                model=self.model,
                messages=messages,
                num_retries=MIN_RETRIES,
            )

            token_usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

            return ResponseStats(
                response=response.choices[0].message.content,
                usage=token_usage,
                model=self.model,
                finish_reason=response.choices[0].finish_reason,
            )

        except Exception as e:
            error_details = {
                "error_type": type(e).__name__,
                "message": str(e),
                "model": self.model,
                "provider": getattr(e, "llm_provider", "unknown"),
                "status_code": getattr(e, "status_code", None),
            }

            logger.error("LLM Generation Error: {}", error_details)

            # Handle authentication and permission errors
            if isinstance(e, self.AUTH_EXCEPTIONS):
                raise openai.AuthenticationError(
                    f"Authentication failed with provider {error_details['provider']}"
                ) from e

            # Handle context window errors
            if isinstance(e, self.CONTEXT_EXCEPTIONS):
                raise openai.InvalidRequestError(f"Context window exceeded or invalid request: {str(e)}") from e

            # Handle content policy violations
            if isinstance(e, self.POLICY_EXCEPTIONS):
                raise openai.APIError(f"Content policy violation: {str(e)}") from e

            # For other exceptions, preserve the original error type if it's from OpenAI
            if isinstance(e, openai.OpenAIError):
                raise

            # Wrap unknown errors in APIError
            raise openai.APIError(f"Unexpected error during generation: {str(e)}") from e

    def generate(self, prompt: str) -> ResponseStats:
        """Generate a response without conversation history.

        Generates a response for a single user prompt without
        any previous conversation context.

        Args:
            prompt: User prompt.

        Returns:
            Detailed response statistics.
        """
        return self.generate_with_history([], prompt)

    def get_max_tokens(self) -> int:
        """Get the maximum number of tokens that can be generated by the model."""
        return get_max_tokens(self.model)

    def token_counter(self, messages: list[Message]) -> int:
        """Count the number of tokens in a list of messages."""
        litellm_messages = [{"role": msg.role, "content": str(msg.content)} for msg in messages]
        return token_counter(model=self.model, messages=litellm_messages)

    def token_counter_with_history(self, messages_history: list[Message], prompt: str) -> int:
        """Count the number of tokens in a list of messages and a prompt."""
        litellm_messages = [{"role": msg.role, "content": str(msg.content)} for msg in messages_history]
        litellm_messages.append({"role": "user", "content": str(prompt)})
        return token_counter(model=self.model, messages=litellm_messages)

    def get_model_info(self) -> dict | None:
        """Get information about the model."""
        model_info = get_model_info(self.model)

        if not model_info:
            # Search without prefix "openrouter/"
            model_info = get_model_info(self.model.replace("openrouter/", ""))

        return model_info

    def get_model_max_input_tokens(self) -> int:
        """Get the maximum number of input tokens for the model."""
        try:
            model_info = self.get_model_info()
            max_tokens = model_info.get("max_input_tokens") if model_info else None
            return max_tokens
        except Exception as e:
            logger.error(f"Error getting max input tokens for {self.model}: {e}")
            return None

    def get_model_max_output_tokens(self) -> int | None:
        """Get the maximum number of output tokens for the model."""
        try:
            model_info = self.get_model_info()
            if model_info:
                return model_info.get("max_output_tokens")

            # Fallback for unmapped models
            logger.warning(f"No max output tokens found for {self.model}. Using default.")
            return 4096  # A reasonable default for many chat models
        except Exception as e:
            logger.error(f"Error getting max output tokens for {self.model}: {e}")
            return None
