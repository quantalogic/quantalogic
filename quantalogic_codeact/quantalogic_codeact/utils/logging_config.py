"""Logging configuration utilities for Quantalogic CodeAct."""

import logging
import os
import sys
from pathlib import Path

from loguru import logger


class InterceptHandler(logging.Handler):
    """Handler to intercept standard library logging and redirect to loguru."""
    
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging_interception():
    """Set up interception of standard library logging to loguru."""
    # Remove all existing loguru handlers first
    logger.remove()
    
    # Intercept standard library logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Set the logging level for external modules we know are verbose
    external_loggers = [
        "quantalogic_toolbox_mcp",
        "httpx", 
        "asyncio",
        "litellm",  # LiteLLM can be very verbose
        "aiohttp",  # Used by many HTTP libraries
    ]
    
    for logger_name in external_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def configure_cli_logging(log_level: str | None = None) -> None:
    """Configure logging for CLI usage with appropriate default level.
    
    Args:
        log_level: Optional log level override (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Set environment variables for external libraries
    os.environ.setdefault("LITELLM_LOG", "WARNING")  # Set LiteLLM log level
    
    # Set up logging interception first
    setup_logging_interception()
    
    # Set default level for CLI - quiet by default
    if log_level is None:
        # Try to load from config if available
        try:
            from quantalogic_codeact.codeact.agent_config import GLOBAL_CONFIG_PATH, AgentConfig
            if Path(GLOBAL_CONFIG_PATH).exists():
                config = AgentConfig.load_from_file(GLOBAL_CONFIG_PATH)
                log_level = config.log_level
            else:
                log_level = "ERROR"  # Default to ERROR for cleanest CLI output
        except Exception:
            log_level = "ERROR"
    
    # Configure loguru with appropriate format
    if log_level.upper() in ["DEBUG"]:
        # Detailed format for debug level only
        format_str = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>.<cyan>{function}</cyan>:{line} - <level>{message}</level>"
    elif log_level.upper() in ["INFO"]:
        # Medium detail for info level
        format_str = "<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <level>{message}</level>"
    else:
        # Simple format for warnings and errors only
        format_str = "<level>{level}: {message}</level>"
    
    logger.add(
        sys.stderr,
        level=log_level.upper(),
        format=format_str,
        colorize=True
    )


def silence_external_loggers() -> None:
    """Silence external library loggers that are too verbose for CLI usage."""
    # List of external loggers to quiet down
    external_loggers = [
        "quantalogic_toolbox_mcp",
        "quantalogic_toolbox_math", 
        "httpx",  # Used by external toolboxes
        "asyncio",
        "litellm",  # LiteLLM debug logs
        "aiohttp",
    ]
    
    for logger_name in external_loggers:
        external_logger = logging.getLogger(logger_name)
        external_logger.setLevel(logging.WARNING)  # Only show warnings and above


def get_quiet_logger_config() -> dict:
    """Get configuration for a quiet logger suitable for tool loading."""
    return {
        "handlers": [
            {
                "sink": sys.stderr,
                "level": "WARNING",  # Only show warnings and errors during tool loading
                "format": "<level>{level}: {message}</level>",
                "colorize": True
            }
        ]
    }
