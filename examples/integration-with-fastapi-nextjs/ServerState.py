#!/usr/bin/env python
"""FastAPI server for the QuantaLogic agent."""

import asyncio
import sys
from loguru import logger


class ServerState:
    """Global server state management."""

    def __init__(self):
        """Initialize the global server state."""
        self.interrupt_count = 0
        self.force_exit = False
        self.is_shutting_down = False
        self.shutdown_initiated = asyncio.Event()
        self.shutdown_complete = asyncio.Event()
        self.server = None

    async def initiate_shutdown(self, force: bool = False):
        """Initiate the shutdown process."""
        if not self.is_shutting_down or force:
            logger.debug("Initiating server shutdown...")
            self.is_shutting_down = True
            self.force_exit = force
            self.shutdown_initiated.set()
            if force:
                # Force exit immediately
                logger.warning("Forcing immediate shutdown...")
                sys.exit(1)
            await self.shutdown_complete.wait()

    def handle_interrupt(self):
        """Handle interrupt signal."""
        self.interrupt_count += 1
        if self.interrupt_count == 1:
            logger.debug("Graceful shutdown initiated (press Ctrl+C again to force)")
            asyncio.create_task(self.initiate_shutdown(force=False))
        else:
            logger.warning("Forced shutdown initiated...")
            # Use asyncio.create_task to avoid RuntimeError
            asyncio.create_task(self.initiate_shutdown(force=True))
