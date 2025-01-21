"""Generative model module for AI-powered text generation."""

import functools
from datetime import datetime
from typing import Any, Dict, List

import litellm
import openai
from litellm import completion, exceptions, get_max_tokens, get_model_info, image_generation, token_counter
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from quantalogic.event_emitter import EventEmitter  # Importing the EventEmitter class
from quantalogic.get_model_info import get_max_input_tokens, get_max_output_tokens, model_info

MIN_RETRIES = 1



litellm.suppress_debug_info = True # Very important to suppress prints don't remove



# Define the Message class for conversation handling
class Message(BaseModel):
    """Represents a message in a conversation with a specific role and content."""

    role: str = Field(..., min_length=1)
    content: str | dict = Field(..., min_length=1)
    image_url: str | None = Field(default=None, pattern=r"^https?://")

    @field_validator("role")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate that the field is not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace-only")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str | dict) -> str | dict:
        """Validate content based on its type."""
        if isinstance(v, str):
            if not v or not v.strip():
                raise ValueError("Text content cannot be empty or whitespace-only")
        elif isinstance(v, dict):
            if not v.get("text") or not v.get("image_url"):
                raise ValueError("Multimodal content must have both text and image_url")
        return v

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, v: str | None) -> str | None:
        """Validate image URL format if present."""
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("Image URL must start with http:// or https://")
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
    data: List[Dict[str, Any]] | None = None
    created: str | None = None


class GenerativeModel:
    """Generative model for AI-powered text generation and image generation."""

    def __init__(
        self,
        model: str = "ollama/qwen2.5-coder:14b",
        temperature: float = 0.7,
        event_emitter: EventEmitter = None,  # EventEmitter instance
    ) -> None:
        """Initialize a generative model with configurable parameters.

        Args:
            model: Model identifier. Defaults to "ollama/qwen2.5-coder:14b".
            temperature: Temperature parameter for controlling randomness in generation. 
                        Higher values (e.g. 0.8) make output more random, lower values (e.g. 0.2) 
                        make it more deterministic. Defaults to 0.7.
            event_emitter: Optional event emitter instance for handling asynchronous events 
                          and callbacks during text generation. Defaults to None.
        """
        logger.debug(f"Initializing GenerativeModel with model={model}, temperature={temperature}")
        self.model = model
        self.temperature = temperature
        self.event_emitter = event_emitter or EventEmitter()  # Initialize event emitter
        self._get_model_info_cached = functools.lru_cache(maxsize=32)(self._get_model_info_impl)

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

    # Generate a response with conversation history and optional streaming
    def generate_with_history(
        self, messages_history: list[Message], prompt: str, image_url: str | None = None, streaming: bool = False
    ) -> ResponseStats:
        """Generate a response with conversation history and optional image.

        Args:
            messages_history: Previous conversation messages.
            prompt: Current user prompt.
            image_url: Optional image URL for visual queries.
            streaming: Whether to stream the response.

        Returns:
            Detailed response statistics or a generator in streaming mode.
        """
        messages = [{"role": msg.role, "content": str(msg.content)} for msg in messages_history]

        if image_url:
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": str(prompt)},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            )
        else:
            messages.append({"role": "user", "content": str(prompt)})

        if streaming:
            self.event_emitter.emit("stream_start")  # Emit stream start event
            return self._stream_response(messages)  # Return generator

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
            self._handle_generation_exception(e)

    def _stream_response(self, messages):
        """Private method to handle streaming responses."""
        try:
            for chunk in completion(
                temperature=self.temperature,
                model=self.model,
                messages=messages,
                num_retries=MIN_RETRIES,
                stream=True,  # Enable streaming
            ):
                if chunk.choices[0].delta.content is not None:
                    self.event_emitter.emit("stream_chunk", chunk.choices[0].delta.content)
                    yield chunk.choices[0].delta.content  # Yield each chunk of content

            self.event_emitter.emit("stream_end")  # Emit stream end event
        except Exception as e:
            logger.error(f"Streaming error: {str(e)}")
            raise

    def generate(self, prompt: str, image_url: str | None = None, streaming: bool = False) -> ResponseStats:
        """Generate a response without conversation history.

        Args:
            prompt: User prompt.
            image_url: Optional image URL for visual queries.
            streaming: Whether to stream the response.

        Returns:
            Detailed response statistics or a generator in streaming mode.
        """
        return self.generate_with_history([], prompt, image_url, streaming)

    def _handle_generation_exception(self, e):
        """Handle exceptions during generation."""
        error_details = {
            "error_type": type(e).__name__,
            "message": str(e),
            "model": self.model,
            "provider": getattr(e, "llm_provider", "unknown"),
            "status_code": getattr(e, "status_code", None),
        }

        logger.error("LLM Generation Error: {}", error_details)
        logger.debug(f"Error details: {error_details}")
        logger.debug(f"Model: {self.model}, Temperature: {self.temperature}")

        if isinstance(e, self.AUTH_EXCEPTIONS):
            logger.debug("Authentication error occurred")
            raise openai.AuthenticationError(f"Authentication failed with provider {error_details['provider']}") from e

        if isinstance(e, self.CONTEXT_EXCEPTIONS):
            raise openai.InvalidRequestError(f"Context window exceeded or invalid request: {str(e)}") from e

        if isinstance(e, self.POLICY_EXCEPTIONS):
            raise openai.APIError(f"Content policy violation: {str(e)}") from e

        if isinstance(e, openai.OpenAIError):
            raise

        raise openai.APIError(f"Unexpected error during generation: {str(e)}") from e

    def get_max_tokens(self) -> int:
        """Get the maximum number of tokens that can be generated by the model."""
        return get_max_tokens(self.model)

    def token_counter(self, messages: list[Message]) -> int:
        """Count the number of tokens in a list of messages."""
        logger.debug(f"Counting tokens for {len(messages)} messages using model {self.model}")
        litellm_messages = [{"role": msg.role, "content": str(msg.content)} for msg in messages]
        token_count = token_counter(model=self.model, messages=litellm_messages)
        logger.debug(f"Token count: {token_count}")
        return token_count

    def token_counter_with_history(self, messages_history: list[Message], prompt: str) -> int:
        """Count the number of tokens in a list of messages and a prompt."""
        litellm_messages = [{"role": msg.role, "content": str(msg.content)} for msg in messages_history]
        litellm_messages.append({"role": "user", "content": str(prompt)})
        return token_counter(model=self.model, messages=litellm_messages)

    def _get_model_info_impl(self, model_name: str) -> dict:
        """Get information about the model with prefix fallback logic."""
        original_model = model_name
        tried_models = [model_name]
        
        while True:
            try:
                logger.debug(f"Attempting to retrieve model info for: {model_name}")
                # Try direct lookup from model_info dictionary first
                if model_name in model_info:
                    logger.debug(f"Found model info for {model_name} in model_info")
                    return model_info[model_name]
                    
                # Try get_model_info as fallback
                info = get_model_info(model_name)
                if info:
                    logger.debug(f"Found model info for {model_name} via get_model_info")
                    return info
            except Exception as e:
                logger.debug(f"Failed to get model info for {model_name}: {str(e)}")
                pass

            # Try removing one prefix level
            parts = model_name.split("/")
            if len(parts) <= 1:
                break
            model_name = "/".join(parts[1:])
            tried_models.append(model_name)

        error_msg = f"Could not find model info for {original_model} after trying: {' → '.join(tried_models)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    def get_model_info(self, model_name: str = None) -> dict:
        """Get cached information about the model."""
        if model_name is None:
            model_name = self.model
        return self._get_model_info_cached(model_name)

    def get_model_max_input_tokens(self) -> int | None:
        """Get the maximum number of input tokens for the model."""
        try:
            # First try direct lookup
            max_tokens = get_max_input_tokens(self.model)
            if max_tokens is not None:
                return max_tokens
            
            # If not found, try getting from model info
            model_info = self.get_model_info()
            if model_info:
                return model_info.get("max_input_tokens")
            
            # If still not found, log warning and return default
            logger.warning(f"No max input tokens found for {self.model}. Using default.")
            return 8192  # A reasonable default for many models
            
        except Exception as e:
            logger.error(f"Error getting max input tokens for {self.model}: {e}")
            return None

    def get_model_max_output_tokens(self) -> int | None:
        """Get the maximum number of output tokens for the model."""
        try:
            # First try direct lookup
            max_tokens = get_max_output_tokens(self.model)
            if max_tokens is not None:
                return max_tokens
            
            # If not found, try getting from model info
            model_info = self.get_model_info()
            if model_info:
                return model_info.get("max_output_tokens")
            
            # If still not found, log warning and return default
            logger.warning(f"No max output tokens found for {self.model}. Using default.")
            return 4096  # A reasonable default for many models
            
        except Exception as e:
            logger.error(f"Error getting max output tokens for {self.model}: {e}")
            return None

    def generate_image(self, prompt: str, params: Dict[str, Any]) -> ResponseStats:
        """Generate an image using the specified model and parameters.

        Args:
            prompt: Text description of the image to generate
            params: Dictionary of parameters for image generation including:
                   - model: Name of the image generation model
                   - size: Size of the generated image
                   - quality: Quality level (DALL-E only)
                   - style: Style preference (DALL-E only)
                   - response_format: Format of the response (url/base64)
                   - negative_prompt: What to avoid in the image (SD only)
                   - cfg_scale: Classifier Free Guidance scale (SD only)

        Returns:
            ResponseStats containing the image generation results

        Raises:
            Exception: If there's an error during image generation
        """
        try:
            logger.debug(f"Generating image with params: {params}")
            
            # Ensure prompt is in params
            generation_params = {**params}
            generation_params["prompt"] = prompt
            
            # Call litellm's image generation function
            response = image_generation(
                model=generation_params.pop("model"),
                **generation_params
            )

            # Convert response data to list of dictionaries with string values
            if hasattr(response, "data"):
                data = []
                for img in response.data:
                    img_data = {}
                    if hasattr(img, "url"):
                        img_data["url"] = str(img.url)
                    if hasattr(img, "b64_json"):
                        img_data["b64_json"] = str(img.b64_json)
                    if hasattr(img, "revised_prompt"):
                        img_data["revised_prompt"] = str(img.revised_prompt)
                    data.append(img_data)
            else:
                data = [{"url": str(response.url)}]

            # Convert timestamp to ISO format string
            if hasattr(response, "created"):
                try:
                    created = datetime.fromtimestamp(response.created).isoformat()
                except (TypeError, ValueError):
                    created = str(response.created)
            else:
                created = None

            # Convert response to our ResponseStats format
            return ResponseStats(
                response="",  # Empty for image generation
                usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                model=str(params["model"]),
                data=data,
                created=created
            )

        except Exception as e:
            logger.error(f"Error in image generation: {str(e)}")
            raise
