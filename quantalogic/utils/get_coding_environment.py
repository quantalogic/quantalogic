import os

from loguru import logger

from quantalogic.utils.get_environment import get_environment
from quantalogic.utils.git_ls import git_ls


def get_coding_environment() -> str:
    """Retrieve coding environment details."""
    logger.debug("Retrieving coding environment details.")
    result = (
        f"{get_environment()}"
        "\n\n"
        "<codebase_first_level>\n"
        f"{git_ls(directory_path=os.getcwd(), recursive=False, max_depth=1)}"
        "\n</codebase_first_level>\n"
    )
    logger.debug(f"Coding environment details:\n{result}")
    return result
