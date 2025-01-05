import os

from quantalogic.utils.get_environment import get_environment
from quantalogic.utils.git_ls import git_ls


def get_coding_environment() -> str:
    """Retrieve coding environment details."""
    return (
            f"{get_environment()}"
            "\n\n"
            "<codebase>\n"
            f"{git_ls(directory_path=os.getcwd())}"
            "</codebase>\n"
    )