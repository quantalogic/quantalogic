import asyncio


def _console_ask_for_user_validation_impl(validation_id: str = "", question: str = "Do you want to continue?") -> bool:
    """Synchronous implementation of the user validation prompt using Rich.
    
    Args:
        validation_id (str): The ID of the validation request.
        question (str): The validation question.
        
    Returns:
        bool: User's confirmation.
    """
    from rich.prompt import Confirm
    
    # ValidationID can be used for more complex validation scenarios
    # but for simple console validation we just show the question
    return Confirm.ask(question, default=True)


async def _async_console_ask_for_user_validation_impl(validation_id: str = "", question: str = "Do you want to continue?") -> bool:
    """Asynchronous implementation of the user validation prompt using Rich.
    
    Args:
        validation_id (str): The ID of the validation request.
        question (str): The validation question.
        
    Returns:
        bool: User's confirmation.
    """
    # Run the synchronous implementation in a thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _console_ask_for_user_validation_impl, validation_id, question
    )


async def console_ask_for_user_validation(*args, **kwargs) -> bool:
    """Prompt the user for validation using Rich (async version).
    
    Supports both the new and old function signatures for backward compatibility:
    - New signature: console_ask_for_user_validation(validation_id: str = "", question: str = "Do you want to continue?")
    - Old signature: console_ask_for_user_validation(question: str = "Do you want to continue?")
    
    Args:
        *args: Variable length argument list.
          - If one argument: treated as the question (old style)
          - If two arguments: treated as validation_id and question (new style)
        **kwargs: Arbitrary keyword arguments.
          - If contains only 'question': old style
          - If contains 'validation_id' and/or 'question': new style
        validation_id (str, optional): The ID of the validation request.
        question (str, optional): The validation question.
        
    Returns:
        bool: User's confirmation.
    """
    # Handle old signature: single positional argument or just 'question' keyword argument
    if len(args) == 1 and not kwargs:
        # Old style: console_ask_for_user_validation("Question text")
        return await _async_console_ask_for_user_validation_impl("", args[0])
    elif not args and len(kwargs) == 1 and "question" in kwargs:
        # Old style: console_ask_for_user_validation(question="Question text")
        return await _async_console_ask_for_user_validation_impl("", kwargs["question"])
    else:
        # New style with both parameters or defaults
        validation_id = kwargs.get("validation_id", "") if not args else args[0]
        question = kwargs.get("question", "Do you want to continue?") if len(args) < 2 else args[1]
        return await _async_console_ask_for_user_validation_impl(validation_id, question)


# Synchronous wrapper for backward compatibility with code that doesn't use async/await
def sync_console_ask_for_user_validation(*args, **kwargs) -> bool:
    """Synchronous wrapper for console_ask_for_user_validation.
    
    This function provides backward compatibility for code that needs to call
    the validation function synchronously without using async/await.
    
    Args:
        *args: Variable length argument list.
          - If one argument: treated as the question (old style)
          - If two arguments: treated as validation_id and question (new style)
        **kwargs: Arbitrary keyword arguments.
          - If contains only 'question': old style
          - If contains 'validation_id' and/or 'question': new style
        
    Returns:
        bool: User's confirmation.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    # Determine arguments based on the calling pattern
    if len(args) == 1 and not kwargs:
        # Old style with just question
        return loop.run_until_complete(_async_console_ask_for_user_validation_impl("", args[0]))
    elif not args and len(kwargs) == 1 and "question" in kwargs:
        # Old style with question as keyword arg
        return loop.run_until_complete(_async_console_ask_for_user_validation_impl("", kwargs["question"]))
    else:
        # New style
        validation_id = kwargs.get("validation_id", "") if not args else args[0]
        question = kwargs.get("question", "Do you want to continue?") if len(args) < 2 else args[1]
        return loop.run_until_complete(_async_console_ask_for_user_validation_impl(validation_id, question))