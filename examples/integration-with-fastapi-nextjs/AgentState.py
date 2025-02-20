#!/usr/bin/env python
"""FastAPI server for the QuantaLogic agent."""

import asyncio
import functools
import json
import signal
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from queue import Empty, Queue
from threading import Lock
from typing import Any, AsyncGenerator, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import BaseModel
from rich.console import Console

from quantalogic import console_print_token
from quantalogic.agent import Agent
from quantalogic.agent_config import (
    MODEL_NAME,
)
from quantalogic.agent_factory import AgentRegistry, create_agent_for_mode
from quantalogic.console_print_events import console_print_events
from quantalogic.memory import AgentMemory
from quantalogic.task_runner import configure_logger
from .utils import handle_sigterm, get_version
from .ServerState import ServerState
from .models import EventMessage, UserValidationRequest, UserValidationResponse, TaskSubmission, TaskStatus, AgentConfig

memory = AgentMemory()
SHUTDOWN_TIMEOUT = 10.0  # seconds
VALIDATION_TIMEOUT = 30.0  # seconds


class AgentState:
    """Manages agent state and event queues."""

    def __init__(self, use_default_agent: bool = False):
        """Initialize the AgentState.
        
        Args:
            use_default_agent: If True, will use default agent when specified agent is not found
        """
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.task_queues: Dict[str, Queue] = {}
        self.event_queues: Dict[str, Dict[str, Queue]] = {}
        self.active_agents: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.queue_lock = Lock()
        self.client_counter = 0
        self.agent = None
        self.validation_requests: Dict[str, Dict[str, Any]] = {}
        self.validation_responses: Dict[str, asyncio.Queue] = {}
        self.agent_registry = AgentRegistry()
        self.agent_configs: Dict[str, AgentConfig] = {}  # Store agent configurations
        # Add validation-related attributes
        
        self.use_default_agent = use_default_agent  # Flag to control default agent usage
        # List of events to listen for
        self.agent_events = [
            "session_start",
            "task_solve_start",
            "task_think_start",
            "task_think_end",
            "tool_execution_start",
            "tool_execution_end",
            "tool_execute_validation_start",
            "tool_execute_validation_end",
            "task_complete",
            "task_solve_end",
            "error_tool_execution",
            "error_max_iterations_reached",
            "error_model_response",
            "stream_event",
            # "stream_chunk",
            # "final_result",
            # "error",
            # "stream_start",
            # "stream_end",
            # "memory_full",
            # "memory_compacted",
            # "memory_summary",
            # "error_agent_not_found",
        ]

    async def create_agent(self, config: AgentConfig) -> bool:
        """Create a new agent with the given configuration.
        
        Args:
            config: Agent configuration
            
        Returns:
            bool: True if agent was created successfully
        """
        try:
            if config.id in self.agent_configs:
                raise ValueError(f"Agent with ID {config.id} already exists")
            
            # Store the configuration
            self.agent_configs[config.id] = config
            
            # Convert tools to dict format expected by create_agent_for_mode
            tools_dict = []
            for tool in config.tools:
                tool_dict = {
                    "type": tool.type,
                    "parameters": {}
                }
                if tool.parameters:
                    # Convert Pydantic model to dict and remove None values
                    params = tool.parameters.dict(exclude_none=True)
                    tool_dict["parameters"] = params
                tools_dict.append(tool_dict)
            
            logger.debug(f"Converted tools configuration: {tools_dict}")
            
            # Create the agent
            agent = create_agent_for_mode(
                mode=config.mode,
                model_name=config.model_name,
                vision_model_name=None,
                no_stream=False,
                tools=tools_dict,
                specific_expertise=config.expertise,
                memory=AgentMemory()
            )
             
            # Override ask_for_user_validation with SSE-based method 
            agent.ask_for_user_validation = self.sse_ask_for_user_validation

            # Set up event handlers
            self._setup_agent_events(agent)
            
            # Register the agent
            self.agent_registry.register_agent(config.id, agent)
            
            logger.info(f"Created agent {config.id} with name: {config.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create agent: {e}", exc_info=True)
            raise

    
    async def sse_ask_for_user_validation(self, question: str = "Do you want to continue?") -> bool:
        """SSE-based user validation method."""
        validation_id = str(uuid.uuid4())
        response_queue = asyncio.Queue()

        # Store validation request and response queue
        self.validation_requests[validation_id] = {"question": question, "timestamp": datetime.now().isoformat()}
        self.validation_responses[validation_id] = response_queue

        # Broadcast validation request
        self.broadcast_event("user_validation_request", {"validation_id": validation_id, "question": question})

        try:
            # Wait for response with timeout
            async with asyncio.timeout(VALIDATION_TIMEOUT):
                response = await response_queue.get()
                return response
        except TimeoutError:
            logger.warning(f"Validation request timed out: {validation_id}")
            return False
        finally:
            # Cleanup
            if validation_id in self.validation_requests:
                del self.validation_requests[validation_id]
            if validation_id in self.validation_responses:
                del self.validation_responses[validation_id]


    def get_agent_config(self, agent_id: str) -> Optional[AgentConfig]:
        """Get the configuration for an agent.
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            Optional[AgentConfig]: Agent configuration if found
        """
        return self.agent_configs.get(agent_id)

    def list_agents(self) -> List[AgentConfig]:
        """List all available agents.
        
        Returns:
            List[AgentConfig]: List of agent configurations
        """
        return list(self.agent_configs.values())

    async def get_agent(self, agent_id: str) -> Agent:
        """Get an agent instance by ID.
        
        Args:
            agent_id: ID of the agent to get
            
        Returns:
            Agent: The agent instance
            
        Raises:
            ValueError: If agent not found and use_default_agent is False
        """
        try:
            # If agent_id is 'default' or (agent doesn't exist and use_default_agent is True)
            if agent_id == "default" or (agent_id not in self.agent_configs and self.use_default_agent):
                if "default" not in self.agent_registry._agents:
                    # Initialize default agent if it doesn't exist
                    await self.initialize_agent_with_sse_validation()
                return self.agent_registry.get_agent("default")
                
            # Normal case - get specified agent
            if agent_id not in self.agent_configs:
                raise ValueError(f"Agent {agent_id} not found")
                
            if agent_id not in self.agent_registry._agents:
                # Recreate the agent if it doesn't exist
                config = self.agent_configs[agent_id]
                await self.create_agent(config)
                
            return self.agent_registry.get_agent(agent_id)
            
        except Exception as e:
            if self.use_default_agent:
                logger.warning(f"Failed to get agent {agent_id}, falling back to default agent: {str(e)}")
                if "default" not in self.agent_registry._agents:
                    await self.initialize_agent_with_sse_validation()
                return self.agent_registry.get_agent("default")
            raise

    async def initialize_agent_with_sse_validation(
        self, 
        model_name: str = MODEL_NAME, 
        mode: str = "minimal",
        tools: Optional[List[Dict[str, Any]]] = None,
        expertise: str = ""
    ) -> Agent:
        """Initialize agent with SSE-based user validation.
        
        Args:
            model_name: Name of the model to use
            mode: Mode for agent creation (minimal, custom, etc.)
            tools: Optional list of tools for custom agents
            expertise: Optional expertise for custom agents
        """
        try:
            logger.info(f"Initializing agent with model: {model_name}")
            
            if "default" not in self.agent_registry._agents:
                self.agent = create_agent_for_mode(
                    mode=mode,
                    model_name=model_name,
                    vision_model_name=None,
                    no_stream=False,
                    tools=tools,
                    specific_expertise=expertise,
                    # memory=memory
                )
                # Set up event handlers before registering the agent
                self._setup_agent_events(self.agent)
                self.agent_registry.register_agent("default", self.agent)
                logger.info(f"Agent initialized successfully with {mode} mode")

                # Add validation-related attributes
                # self.agent.ask_for_user_validation = self.sse_ask_for_user_validation

            agent = self.agent_registry.get_agent("default")
            # Ensure events are set up even for existing agent
            self._setup_agent_events(agent)
            return agent
            
        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}", exc_info=True)
            raise

    def _setup_agent_events(self, agent: Agent) -> None:
        """Set up event handlers for the agent."""
        # Instead of removing all listeners, we'll track our handlers
        if not hasattr(self, '_event_handlers'):
            self._event_handlers = {}
            
        # Remove existing handlers if any
        for event_type, handler in self._event_handlers.items():
            if handler:
                agent.event_emitter.off(event_type, handler)
        
        # Clear existing handlers
        self._event_handlers = {}
        
        def create_event_handler(event_type: str):
            def handler(event: str, *args: Any, **kwargs: Any):
                logger.debug(f"Received agent event: {event_type} with args: {args} kwargs: {kwargs}")
                # Get data from args or kwargs
                data = args[0] if args else kwargs
                # Add task_id to the event data if it's not there
                if isinstance(data, dict) and "task_id" not in data:
                    current_task_id = next(
                        (task_id for task_id, task in self.tasks.items() if task.get("status") == "running"),
                        None
                    )
                    if current_task_id:
                        data["task_id"] = current_task_id
                self._handle_event(event_type, data)
            return handler

        # Set up new handlers
        for event in self.agent_events:
            logger.debug(f"Setting up handler for event: {event}")
            handler = create_event_handler(event)
            self._event_handlers[event] = handler
            agent.event_emitter.on(event, handler)

        # agent.event_emitter.on(event=["stream_chunk"], listener=console_print_token)

    def _handle_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle agent events with rich console output."""
        try:
            # Use console_print_events for consistent event formatting
            console_print_events(event_type, data)
            
            # Create event message
            event = EventMessage(
                id=str(uuid.uuid4()),
                event=event_type,
                data=data,
                timestamp=datetime.utcnow().isoformat()
            )
            
            
            logger.debug(f"Broadcasting event: {event_type} - {data}")
            
            # Get task_id from data if available
            task_id = data.get("task_id")
            
            # Broadcast to all clients
            with self.queue_lock:
                for client_id, client_queues in self.event_queues.items():
                    try:
                        # Always send to global queue
                        if "global" in client_queues:
                            client_queues["global"].put(event)
                            logger.debug(f"Event sent to client {client_id} global queue")
                        
                        # If event has task_id and client has that task queue, send there too
                        if task_id and task_id in client_queues:
                            client_queues[task_id].put(event)
                            logger.debug(f"Event sent to client {client_id} task queue {task_id}")
                    except Exception as e:
                        logger.error(f"Error sending event to client {client_id}: {e}")
                        
        except Exception as e:
            logger.error(f"Error handling event {event_type}: {e}", exc_info=True)

    async def execute_task(self, task_id: str) -> None:
        """Execute a task asynchronously."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task_info = self.tasks[task_id]
        task_info["started_at"] = datetime.now().isoformat()
        task_info["status"] = "running"

        try:
            logger.info(f"Starting task execution: {task_id}")
            request = task_info.get("request", {})
            agent_id = request.get("agent_id")
            
            try:
                # Get the agent for this task
                agent = await self.get_agent(agent_id)
            except ValueError as e:
                if self.use_default_agent:
                    logger.warning(f"Using default agent due to: {str(e)}")
                    agent = await self.get_agent("default")
                else:
                    raise
            
            # Create event for task start
            self._handle_event("task_solve_start", {
                "task_id": task_id,
                "agent_id": agent_id,
                "message": "Task execution started"
            })
            
            # Run solve_task in a thread to not block the event loop
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: agent.solve_task(
                    task=task_info["request"]["task"],
                    max_iterations=task_info["request"].get("max_iterations", 30),
                    streaming=True,  # Enable streaming for more events
                    clear_memory=False  # Keep memory between tasks
                )
            )

            self._update_task_success(task_info, result, agent)
            
            # Create event for task completion
            self._handle_event("task_solve_end", {
                "task_id": task_id,
                "agent_id": agent_id,
                "message": "Task execution completed",
                "result": result
            })
            
        except Exception as e:
            self._update_task_failure(task_info, e)
            
            # Create event for task failure
            self._handle_event("error_tool_execution", {
                "task_id": task_id,
                "message": f"Task execution failed: {str(e)}"
            })
            
            logger.exception(f"Error executing task {task_id}")
        finally:
            self.remove_task_event_queue(task_id)

    def _update_task_success(self, task_info: Dict[str, Any], result: str, agent: Agent) -> None:
        """Update task info after successful execution.
        
        Args:
            task_info: Task information dictionary
            result: Task execution result
            agent: Agent that executed the task
        """
        task_info["completed_at"] = datetime.now().isoformat()
        task_info["status"] = "completed"
        task_info["result"] = result
        task_info["total_tokens"] = agent.total_tokens if hasattr(agent, "total_tokens") else None
        task_info["model_name"] = self.get_current_model_name()
        
    def _update_task_failure(self, task_info: Dict[str, Any], error: Exception) -> None:
        """Update task info after failed execution.
        
        Args:
            task_info: Task information dictionary
            error: Exception that caused the failure
        """
        task_info["completed_at"] = datetime.now().isoformat()
        task_info["status"] = "failed"
        task_info["error"] = str(error)

    async def submit_task(self, task_request: TaskSubmission) -> str:
        """Submit a new task and return its ID."""
        task_id = str(uuid.uuid4())
        self.tasks[task_id] = {
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "request": task_request.dict(),
        }
        self.task_queues[task_id] = asyncio.Queue()
        return task_id

    async def get_task_event_queue(self, task_id: str) -> Queue:
        """Get or create a task-specific event queue."""
        with self.queue_lock:
            if task_id not in self.task_queues:
                self.task_queues[task_id] = Queue()
            return self.task_queues[task_id]

    def remove_task_event_queue(self, task_id: str):
        """Remove a task-specific event queue."""
        with self.queue_lock:
            if task_id in self.task_queues:
                del self.task_queues[task_id]
                logger.debug(f"Removed event queue for task_id: {task_id}")

    def add_client(self, task_id: Optional[str] = None) -> str:
        """Add a new client and return its ID."""
        with self.queue_lock:
            client_id = f"client_{self.client_counter}"
            self.client_counter += 1
            
            logger.debug(f"Adding new client: {client_id} for task: {task_id}")

            # Initialize client queues
            self.event_queues[client_id] = {"global": Queue()}
            
            # Add task-specific queue if needed
            if task_id:
                self.event_queues[client_id][task_id] = Queue()
                logger.debug(f"Created task queue for client {client_id} and task {task_id}")

            return client_id

    def remove_client(self, client_id: str, task_id: Optional[str] = None):
        """Remove a client's event queue, optionally for a specific task."""
        with self.queue_lock:
            if client_id in self.event_queues:
                if task_id and task_id in self.event_queues[client_id]:
                    # Remove specific task queue for this client
                    del self.event_queues[client_id][task_id]

                    # Remove active agent for this client-task
                    if client_id in self.active_agents and task_id in self.active_agents[client_id]:
                        del self.active_agents[client_id][task_id]
                else:
                    # Remove entire client entry
                    del self.event_queues[client_id]

                    # Remove all active agents for this client
                    if client_id in self.active_agents:
                        del self.active_agents[client_id]

    def broadcast_event(
        self, event_type: str, data: Dict[str, Any], task_id: Optional[str] = None, client_id: Optional[str] = None
    ):
        """Broadcast an event to specific client-task queues or globally.

        Allows optional filtering by client_id and task_id to prevent event leakage.
        """
        event = EventMessage(
            id=str(uuid.uuid4()), event=event_type, task_id=task_id, data=data, timestamp=datetime.utcnow().isoformat()
        )

        with self.queue_lock:
            for curr_client_id, client_queues in self.event_queues.items():
                # Skip if specific client_id is provided and doesn't match
                if client_id and curr_client_id != client_id:
                    continue

                if task_id and task_id in client_queues:
                    # Send to specific task queue
                    client_queues[task_id].put(event)
                elif not task_id and "global" in client_queues:
                    # Send to global queue if no task specified
                    client_queues["global"].put(event)

    def get_current_model_name(self) -> str:
        """Get the current model name safely."""
        if self.agent and self.agent.model:
            return self.agent.model.model
        return MODEL_NAME

    async def cleanup(self):
        """Clean up resources during shutdown."""
        try:
            logger.debug("Cleaning up resources...")
            if server_state.force_exit:
                logger.warning("Forced cleanup - skipping graceful shutdown")
                return

            async with asyncio.timeout(SHUTDOWN_TIMEOUT):
                with self.queue_lock:
                    # Notify all clients
                    self.broadcast_event("server_shutdown", {"message": "Server is shutting down"})
                    # Clear queues
                    self.event_queues.clear()
                    self.validation_requests.clear()
                    self.validation_responses.clear()
                # Clear agent
                self.agent = None
                logger.debug("Cleanup completed")
        except TimeoutError:
            logger.warning(f"Cleanup timed out after {SHUTDOWN_TIMEOUT} seconds")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
        finally:
            self.agent = None
            if server_state.force_exit:
                sys.exit(1)
