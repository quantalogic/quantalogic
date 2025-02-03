
from loguru import logger

def handle_sigterm(signum, frame):
    """Handle SIGTERM signal."""
    logger.debug("Received SIGTERM signal")
    raise SystemExit(0)


def get_version() -> str:
    """Get the current version of the package."""
    return "QuantaLogic version: 1.0.0"

