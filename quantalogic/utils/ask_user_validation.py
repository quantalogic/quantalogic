import asyncio

from rich.prompt import Confirm


async def console_ask_for_user_validation(question="Do you want to continue?", validation_id=None) -> bool:
    """Prompt the user for validation using Rich (async version).
    
    Args:
        question: The validation question to ask
        validation_id: Optional ID for tracking validation requests (not used in this implementation)
                  
    Returns:
        bool: True if the user validates, False otherwise.
    """
    # Run the synchronous Rich prompt in a thread pool to avoid blocking
    return await asyncio.to_thread(Confirm.ask, question, default=True)


def sync_console_ask_for_user_validation(question="Do you want to continue?", validation_id=None) -> bool:
    """Synchronous wrapper for console_ask_for_user_validation.
    
    This function allows for backward compatibility with code that isn't using async/await.
    
    Args:
        question: The validation question to ask
        validation_id: Optional ID for tracking validation requests (not used in this implementation)
    
    Returns:
        bool: User's confirmation
    """
    return Confirm.ask(question, default=True)