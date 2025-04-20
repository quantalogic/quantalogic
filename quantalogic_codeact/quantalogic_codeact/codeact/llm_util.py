from typing import Callable, List, Optional

import litellm
from litellm import exceptions


class LLMCompletionError(Exception):
    """Non-recoverable error during LLM completion."""
    pass

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
        except exceptions.APIError as e:
            # Notify user about streaming failure
            err_msg = f"❌ Streaming completion failed: {e.__class__.__name__}: {e}"
            if notify_event:
                await notify_event(StreamTokenEvent(
                    event_type="StreamError",
                    token=err_msg,
                    step_number=step
                ))
            raise LLMCompletionError(err_msg)
        except Exception as e:
            err_msg = f"❌ Streaming completion failed: {e}"
            if notify_event:
                await notify_event(StreamTokenEvent(
                    event_type="StreamError",
                    token=err_msg,
                    step_number=step
                ))
            raise LLMCompletionError(err_msg)
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
        except exceptions.APIError as e:
            # Clear message for non-streaming errors
            err_msg = f"❌ Completion failed: {e.__class__.__name__}: {e}"
            raise LLMCompletionError(err_msg)
        except Exception as e:
            raise LLMCompletionError(f"❌ Completion failed: {e}")