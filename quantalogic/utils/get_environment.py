import os
from datetime import datetime

from loguru import logger


def get_environment() -> str:
    """Retrieve the current environment details."""
    try:
        logger.debug("Retrieving environment details.")
        shell = os.getenv("SHELL", "bash")
        current_dir = os.getcwd()
        operating_system = os.name
        date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        environment_details = (
            f"Current shell: {shell}\n"
            f"Current directory: {current_dir}\n"
            f"Operating system: {operating_system}\n"
            f"Date and time: {date_time}"
        )
        logger.debug(f"Environment details:\n{environment_details}")
        return environment_details
    except Exception as e:
        logger.error(f"Error retrieving environment details: {str(e)}")
        return "Environment details unavailable."
