from typing import Callable, List, Optional

import litellm


async def litellm_completion(
    model: str,
    messages: List[dict],
    max_tokens: int,
    temperature: float,
    stream: bool = False,
    step: Optional[int] = None,
    notify_event: Optional[Callable] = None,
    **kwargs
) -> str:
    """
    A wrapper for litellm.acompletion that supports streaming and non-streaming modes.
    
    Args:
        model (str): The model to use (e.g., "gemini/gemini-2.0-flash").
        messages (List[dict]): The conversation history as a list of message dictionaries.
        max_tokens (int): Maximum number of tokens to generate.
        temperature (float): Sampling temperature for the model.
        stream (bool): If True, stream tokens; if False, return the full response.
        step (Optional[int]): Step number for event tracking (used in streaming mode).
        notify_event (Optional[Callable]): Callback to trigger events during streaming.
        **kwargs: Additional arguments to pass to litellm.acompletion.

    Returns:
        str: The generated response (full text in both modes).

    Raises:
        ValueError: If notify_event is missing when stream=True.
        Exception: If the completion request fails.
    """
    from .events import StreamTokenEvent  # Local import to avoid circular dependency

    if stream:
        if notify_event is None:
            raise ValueError("notify_event callback is required when streaming is enabled.")
        
        full_response = ""
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                **kwargs
            )
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response += token
                    await notify_event(StreamTokenEvent(
                        event_type="StreamToken",
                        token=token,
                        step_number=step
                    ))
            return full_response
        except Exception as e:
            raise Exception(f"Streaming completion failed: {e}")
    else:
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Completion failed: {e}")
