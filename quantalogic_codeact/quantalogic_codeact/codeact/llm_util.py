from typing import Callable, List, Optional

import litellm
from litellm import exceptions
from loguru import logger

from .events import StreamTokenEvent


class LLMCompletionError(Exception):
    """Non-recoverable error during LLM completion."""
    pass

async def litellm_completion(
    model: str,
    messages: List[dict],
    temperature: float,
    stream: bool = False,
    max_tokens: Optional[int] = None,
    step: Optional[int] = None,
    notify_event: Optional[Callable] = None,
    agent_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    task_id: Optional[str] = None,
    **kwargs
) -> str:
    """A wrapper for litellm.acompletion with streaming support and fallback to non-streaming."""
    full_response = ""
    if stream:
        if notify_event is None:
            raise ValueError("notify_event callback is required when streaming is enabled.")
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
                        agent_id=agent_id,
                        agent_name=agent_name,
                        token=token,
                        step_number=step,
                        task_id=task_id
                    ))
            return full_response
        except Exception as e:
            # Log the issue and notify the user via the event system
            fallback_message = "⚠️ Streaming not supported for this model, falling back to non-streaming.\n"
            logger.warning(f"Streaming failed for model {model}: {e}. Falling back to non-streaming.")
            if notify_event:
                await notify_event(StreamTokenEvent(
                    event_type="StreamToken",
                    agent_id=agent_id,
                    agent_name=agent_name,
                    token=fallback_message,
                    step_number=step,
                    task_id=task_id
                ))
            stream = False  # Proceed with non-streaming mode

    if not stream:
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
            err_msg = f"❌ Completion failed: {e.__class__.__name__}: {e}"
            raise LLMCompletionError(err_msg)
        except Exception as e:
            # Async non-streaming failed, fallback to sync completion
            logger.warning(f"Async completion failed for model {model}: {e}. Trying sync completion.")
            try:
                sync_resp = litellm.completion(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs
                )
                return sync_resp.choices[0].message.content
            except Exception as sync_e:
                raise LLMCompletionError(f"❌ Sync completion fallback failed: {sync_e}")