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
    """A wrapper for litellm.acompletion that supports streaming and non-streaming modes."""
    from .events import StreamTokenEvent

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