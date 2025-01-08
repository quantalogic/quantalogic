"""State management for the QuantaLogic server."""

import asyncio
import sys
import traceback
from datetime import datetime
from queue import Queue
from threading import Lock
from typing import Any, Dict, Optional

from loguru import logger
from rich.console import Console

# Configure logger
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)


class ServerState:
    """Global server state management."""

    def __init__(self):
        """Initialize the ServerState with default values for server management."""
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
            asyncio.create_task(self.initiate_shutdown(force=True))


class AgentState:
    """Manages agent state and event queues."""

    def __init__(self):
        """Initialize the agent state."""
        self.agent = None
        self.event_queues: Dict[str, Queue] = {}
        self.task_event_queues: Dict[str, Queue] = {}
        self.queue_lock = Lock()
        self.client_counter = 0
        self.console = Console()
        self.validation_requests: Dict[str, Dict[str, Any]] = {}
        self.validation_responses: Dict[str, asyncio.Queue] = {}
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.task_queues: Dict[str, asyncio.Queue] = {}
        self.agents: Dict[str, Any] = {}  # Dictionary to store agents by task ID

    def add_client(self, task_id: Optional[str] = None) -> str:
        """Add a new client and return its ID.

        Args:
            task_id (Optional[str]): Optional task ID to associate with the client.

        Returns:
            str: Unique client ID
        """
        with self.queue_lock:
            self.client_counter += 1
            client_id = f"client_{self.client_counter}"

            # Create a client-specific event queue
            self.event_queues[client_id] = Queue()

            # If a task_id is provided, create or use an existing task-specific queue and agent
            if task_id:
                if task_id not in self.task_event_queues:
                    self.task_event_queues[task_id] = Queue()
                if task_id not in self.agents:
                    self.agents[task_id] = self.create_agent_for_task(task_id)

            logger.debug(f"New client connected: {client_id} for task: {task_id}")
            return client_id

    def create_agent_for_task(self, task_id: str) -> Any:
        """Create and return a new agent for the specified task.

        Args:
            task_id (str): The task ID for which to create the agent.

        Returns:
            Any: The created agent instance.
        """
        # Placeholder for agent creation logic
        agent = ...  # Replace with actual agent creation logic
        logger.debug(f"Agent created for task: {task_id}")
        return agent

    def get_agent_for_task(self, task_id: str) -> Optional[Any]:
        """Retrieve the agent for the specified task.

        Args:
            task_id (str): The task ID for which to retrieve the agent.

        Returns:
            Optional[Any]: The agent instance if found, else None.
        """
        return self.agents.get(task_id)

    def remove_client(self, client_id: str):
        """Remove a client and its event queue."""
        with self.queue_lock:
            if client_id in self.event_queues:
                del self.event_queues[client_id]
                logger.debug(f"Client disconnected: {client_id}")

    def _format_data_for_client(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format data for client consumption."""
        if isinstance(data, dict):
            return {k: str(v) if isinstance(v, datetime | bytes) else v for k, v in data.items()}
        return data

    def broadcast_event(self, event_type: str, data: Dict[str, Any]):
        """Broadcast an event to all connected clients or specific task queue.

        Args:
            event_type (str): Type of the event.
            data (Dict[str, Any]): Event data.
        """
        from quantalogic.models import EventMessage  # Import here to avoid circular dependency

        try:
            formatted_data = self._format_data_for_client(data)
            event = EventMessage(
                id=f"evt_{datetime.now().timestamp()}",
                event=event_type,
                task_id=data.get("task_id"),
                data=formatted_data,
                timestamp=datetime.now().isoformat(),
            )

            with self.queue_lock:
                task_id = data.get("task_id")

                # If task_id is provided, send to task-specific queue and use task-specific agent
                if task_id and task_id in self.task_event_queues:
                    self.task_event_queues[task_id].put(event.model_dump())
                    agent = self.get_agent_for_task(task_id)
                    if agent:
                        # Use the agent for task-specific processing
                        # Placeholder for agent-specific logic
                        pass
                    logger.debug(f"Event sent to task-specific queue: {task_id}")

                # Optionally broadcast to global event queues if needed
                else:
                    for queue in self.event_queues.values():
                        queue.put(event.model_dump())
                    logger.debug("Event broadcast to all client queues")

        except Exception as e:
            logger.error(f"Error broadcasting event: {e}")
            logger.error(traceback.format_exc())

    def remove_task_event_queue(self, task_id: str):
        """Remove a task-specific event queue safely.

        Args:
            task_id (str): The task ID to remove from event queues.
        """
        with self.queue_lock:
            if task_id in self.task_event_queues:
                del self.task_event_queues[task_id]

            # Additional cleanup for related task resources
            if task_id in self.tasks:
                del self.tasks[task_id]

            if task_id in self.task_queues:
                del self.task_queues[task_id]

            if task_id in self.agents:
                del self.agents[task_id]
