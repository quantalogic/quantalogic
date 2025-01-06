def console_ask_for_user_validation(question: str = "Do you want to continue?") -> bool:
    """Prompt the user for validation using Rich.

    Args:
        question (str): The validation question.

    Returns:
        bool: User's confirmation.
    """
    from rich.prompt import Confirm

    return Confirm.ask(question, default=True)
