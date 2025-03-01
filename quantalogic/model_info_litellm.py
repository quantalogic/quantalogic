import functools

# litellm will be imported lazily when needed
_litellm = None

def _get_litellm():
    """Lazy load litellm module.

    Returns:
        The litellm module
    """
    global _litellm
    if _litellm is None:
        import litellm
        _litellm = litellm
    return _litellm

@functools.lru_cache(maxsize=32)
def litellm_get_model_info(model_name: str) -> dict | None:
    """Get model information with prefix fallback logic using only litellm.

    Args:
        model_name: The model identifier to get information for

    Returns:
        Dictionary containing model information

    Raises:
        ValueError: If model info cannot be found after prefix fallbacks
    """
    litellm = _get_litellm()
    tried_models = [model_name]

    while True:
        try:
            # Attempt to get model info through litellm
            info = litellm.get_model_info(model_name)
            if info:
                return info
        except Exception:
            pass

        # Try removing one prefix level
        parts = model_name.split("/")
        if len(parts) <= 1:
            break

        model_name = "/".join(parts[1:])
        tried_models.append(model_name)

    return None

def litellm_get_model_max_input_tokens(model_name: str) -> int | None:
    """Get maximum input tokens for a model using litellm.

    Args:
        model_name: The model identifier

    Returns:
        Maximum input tokens or None if not found
    """
    try:
        info = litellm_get_model_info(model_name)
        return info.get("max_input_tokens", 8192)
    except Exception:
        return 8192  # Default for many modern models

def litellm_get_model_max_output_tokens(model_name: str) -> int | None:
    """Get maximum output tokens for a model using litellm.

    Args:
        model_name: The model identifier

    Returns:
        Maximum output tokens or None if not found
    """
    try:
        info = litellm_get_model_info(model_name)
        return info.get("max_output_tokens", 4096)
    except Exception:
        return 4096  # Conservative default