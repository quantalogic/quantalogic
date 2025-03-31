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
import os

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
from quantalogic.create_custom_agent import create_custom_agent
from quantalogic.console_print_events import console_print_events
from quantalogic.memory import AgentMemory
from quantalogic.task_runner import configure_logger
from .utils import handle_sigterm, get_version
from .ServerState import ServerState
from .models import AnalyzePaperRequest, BookNovelRequest, ConvertRequest, CourseRequest, EventMessage, ImageAnalysisRequest, ImageGenerationRequest, JourneyRequest, LinkedInIntroduceContentRequest, QuizRequest, TutorialRequest, UserValidationRequest, UserValidationResponse, AgentConfig, TaskSubmission

SHUTDOWN_TIMEOUT = 10.0  # seconds
VALIDATION_TIMEOUT = 10.0  # seconds

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
        self.agent_registry = AgentRegistry()
        self.agent_configs: Dict[str, AgentConfig] = {}
        
        # Validation-related attributes with better organization
        self._validation_lock = Lock()
        self._validation_requests: Dict[str, Dict[str, Any]] = {}
        self._validation_responses: Dict[str, asyncio.Queue] = {}
        self._validation_timeouts: Dict[str, asyncio.Task] = {}
        
        self.use_default_agent = use_default_agent
        
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
            "user_validation_request",
            "user_validation_response",
            "chat_response",
            "stream_chunk",
            "final_result",
            "error",
            #"stream_start",
            #"stream_end",
            "memory_full",
            "memory_compacted",
            "memory_summary",
            "error_agent_not_found",
            "node_started",
            "node_completed",
            "node_failed",
            "transition_evaluated",
            "workflow_started",
            "workflow_completed",
            "sub_workflow_entered",
            "sub_workflow_exited",
            "streaming_chunk",
            "task_progress"
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
            
            # Convert tools to dict format expected by create_custom_agent
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
            agent = create_custom_agent( 
                model_name=config.model_name,
                vision_model_name=None, 
                no_stream=False,
                tools=tools_dict,
                specific_expertise=config.expertise,
                memory=AgentMemory(),
                agent_mode=config.agent_mode
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

    
    async def sse_ask_for_user_validation(
        self,
        validation_id: str,
        question: str = "Do you want to continue?",
        tool_name: str = "",
        arguments: Dict[str, Any] = None
    ) -> bool:
        """Request user validation via SSE events."""
        if not validation_id:
            raise ValueError("validation_id must be provided")
            
        start_time = time.time()
        logger.info(f"[{validation_id}] Starting validation request")
        response_queue = asyncio.Queue(maxsize=1)
        task_id = self._get_current_task_id()

        try:
            # Initialize validation request and start timeout in background
            await self._init_validation_request(validation_id, question, tool_name, arguments, response_queue)
            
            # Send validation request event
            self._send_validation_start_event(validation_id, question, tool_name, arguments, task_id)
            logger.info(f"[{validation_id}] Sent validation start event, waiting for response...")
            
            # Just wait for response - timeout is handled separately
            response = await response_queue.get()
            elapsed = time.time() - start_time
            logger.info(f"[{validation_id}] Got response in {elapsed:.2f} seconds")
            
            self._send_validation_end_event(validation_id, response, task_id)
            return response

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[{validation_id}] Validation error after {elapsed:.2f} seconds: {e}", exc_info=True)
            self._send_validation_error_event(validation_id, str(e), task_id)
            return False
            
        finally:
            # Schedule cleanup as background task
            asyncio.create_task(self._cleanup_validation(validation_id))

    def _get_current_task_id(self) -> Optional[str]:
        """Get ID of currently running task."""
        return next(
            (task_id for task_id, task in self.tasks.items() if task.get("status") == "running"),
            None
        )

    async def _init_validation_request(
        self,
        validation_id: str,
        question: str,
        tool_name: str,
        arguments: Dict[str, Any],
        response_queue: asyncio.Queue
    ) -> None:
        """Initialize validation request state."""
        with self._validation_lock:
            self._validation_requests[validation_id] = {
                "question": question,
                "tool_name": tool_name,
                "arguments": arguments,
                "timestamp": datetime.now().isoformat(),
                "status": "pending"
            }
            self._validation_responses[validation_id] = response_queue
            self._validation_timeouts[validation_id] = asyncio.create_task(
                self._handle_validation_timeout(validation_id)
            )

    def _send_validation_start_event(
        self,
        validation_id: str,
        question: str,
        tool_name: str,
        arguments: Dict[str, Any],
        task_id: Optional[str]
    ) -> None:
        """Send validation start event."""
        self.broadcast_event(
            "tool_execute_validation_start",
            {
                "validation_id": validation_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "question": question,
                "task_id": task_id
            }
        )

    def _send_validation_end_event(
        self,
        validation_id: str,
        approved: bool,
        task_id: Optional[str]
    ) -> None:
        """Send validation end event."""
        # Cancel timeout task immediately
        if validation_id in self._validation_timeouts:
            self._validation_timeouts[validation_id].cancel()
            
        self.broadcast_event(
            "tool_execute_validation_end",
            {
                "validation_id": validation_id,
                "approved": approved,
                "task_id": task_id
            }
        )

    def _send_validation_timeout_event(
        self,
        validation_id: str,
        task_id: Optional[str]
    ) -> None:
        """Send validation timeout event."""
        self.broadcast_event(
            "tool_execute_validation_end",
            {
                "validation_id": validation_id,
                "approved": False,
                "error": "Validation request timed out",
                "task_id": task_id
            }
        )

    def _send_validation_error_event(
        self,
        validation_id: str,
        error: str,
        task_id: Optional[str]
    ) -> None:
        """Send validation error event."""
        self.broadcast_event(
            "tool_execute_validation_end",
            {
                "validation_id": validation_id,
                "approved": False,
                "error": error,
                "task_id": task_id
            }
        )

    async def _handle_validation_timeout(self, validation_id: str) -> None:
        """Handle validation request timeout."""
        try:
            await asyncio.sleep(VALIDATION_TIMEOUT)
            with self._validation_lock:
                # Check if validation is still pending
                request = self._validation_requests.get(validation_id)
                if request and request["status"] == "pending":
                    request["status"] = "timeout"
                    if validation_id in self._validation_responses:
                        response_queue = self._validation_responses[validation_id]
                        try:
                            response_queue.put_nowait(False)
                        except asyncio.QueueFull:
                            # Queue is full, response was already processed
                            pass
        except asyncio.CancelledError:
            # Task was cancelled because response was received - this is expected
            logger.debug(f"Timeout cancelled for validation ID {validation_id}")
        except Exception as e:
            logger.error(f"Timeout handler error: {e}", exc_info=True)

    async def _cleanup_validation(self, validation_id: str) -> None:
        """Clean up validation resources."""
        with self._validation_lock:
            if validation_id in self._validation_timeouts:
                self._validation_timeouts[validation_id].cancel()
                del self._validation_timeouts[validation_id]
            self._validation_requests.pop(validation_id, None)
            self._validation_responses.pop(validation_id, None)

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
                self.agent = create_custom_agent( 
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

    def _handle_workflow_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle workflow-specific events."""
        # Add workflow-specific metadata
        if event_type == "workflow_started":
            data["workflow_info"] = {
                "start_time": datetime.utcnow().isoformat(),
                "status": "running"
            }
        elif event_type == "workflow_completed":
            data["workflow_info"] = {
                "end_time": datetime.utcnow().isoformat(),
                "status": "completed"
            }
        elif event_type in ["node_started", "node_completed", "node_failed"]:
            # Add node execution metadata
            data["node_info"] = {
                "timestamp": datetime.utcnow().isoformat(),
                "status": event_type.replace("node_", "")
            }
        elif event_type == "transition_evaluated":
            # Add transition metadata
            data["transition_info"] = {
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Broadcast the enhanced event
        self._handle_event(event_type, data)

    def _setup_workflow_events(self, agent: Agent) -> None:
        """Set up workflow-specific event handlers."""
        workflow_events = [
            "workflow_started",
            "workflow_completed",
            "node_started",
            "node_completed",
            "node_failed",
            "transition_evaluated",
            "sub_workflow_entered",
            "sub_workflow_exited"
        ]
        
        for event in workflow_events:
            def create_workflow_handler(event_type: str):
                def handler(event: str, *args: Any, **kwargs: Any):
                    logger.debug(f"Received workflow event: {event_type}")
                    data = args[0] if args else kwargs
                    self._handle_workflow_event(event_type, data)
                return handler
                
            handler = create_workflow_handler(event)
            self._event_handlers[event] = handler
            agent.event_emitter.on(event, handler)

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
                
                # Handle string data for stream_chunk events
                if event_type == "stream_chunk" and isinstance(data, str):
                    data = {"chunk": data}
                
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

        # Set up standard event handlers
        for event in self.agent_events:
            if event not in [
                "workflow_started", "workflow_completed",
                "node_started", "node_completed", "node_failed",
                "transition_evaluated", "sub_workflow_entered", "sub_workflow_exited"
            ]:
                logger.debug(f"Setting up handler for event: {event}")
                handler = create_event_handler(event)
                self._event_handlers[event] = handler
                agent.event_emitter.on(event, handler)
        
        # Set up workflow-specific event handlers
        self._setup_workflow_events(agent)

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
            """ self._handle_event("task_solve_end", {
                "task_id": task_id,
                "agent_id": agent_id,
                "message": "Task execution completed",
                "result": result,
            }) """
            
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

    async def execute_chat(self, task_id: str) -> None:
        """Execute a chat asynchronously."""
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
            
            # Run chat in a thread to not block the event loop
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: agent.chat(
                    message=task_info["request"]["task"], 
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

    async def get_news(self, task_id: str) -> None:
        """Execute a get news asynchronously."""
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
            
            # Run chat in a thread to not block the event loop
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: agent.chat_news_specific(
                    message=task_info["request"]["task"], 
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

    def _update_task_success(self, task_info: Dict[str, Any], result: str, agent: Optional[Agent]) -> None:
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
                    self._validation_requests.clear()
                    self._validation_responses.clear()
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

            # Import the tutorial generation module
            from quantalogic.flows.create_tutorial import generate_tutorial


    async def execute_tutorial(self, task_id: str, request: TutorialRequest) -> None:
        """Execute a tutorial generation task asynchronously."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task_info = self.tasks[task_id]
        task_info["started_at"] = datetime.now().isoformat()
        task_info["status"] = "running"

        try:
            logger.info(f"Starting tutorial generation: {task_id}") 
            
            # Add the examples directory to Python path
            examples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'examples', "integration-with-fastapi-nextjs"))
            sys.path.append(examples_dir)
            
            from flows.create_tutorial.create_tutorial import generate_tutorial
            
            # Run tutorial generation in a thread to not block the event loop
            loop = asyncio.get_running_loop()

            # Create event for task completion
            self._handle_event("task_solve_start", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "Tutorial generation started"
            })

            result = await loop.run_in_executor(
                None,
                lambda: generate_tutorial(
                    markdown_content=request.markdown_content,
                    model=request.model,
                    num_chapters=request.num_chapters,
                    words_per_chapter=request.words_per_chapter,
                    copy_to_clipboard=request.copy_to_clipboard,
                    skip_refinement=request.skip_refinement,
                    task_id=task_id,
                    _handle_event=self._handle_event
                )
            )

            self._update_task_success(task_info, result, None) 
            
            # Create event for task completion
            self._handle_event("task_solve_end", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "Tutorial generation completed",
                "result": result
            })
            
        except Exception as e:
            self._update_task_failure(task_info, e)
            
            # Create event for task failure
            self._handle_event("error_tool_execution", {
                "task_id": task_id,
                "message": f"Tutorial generation failed: {str(e)}"
            })
            
            logger.exception(f"Error generating tutorial {task_id}")
        finally:
            self.remove_task_event_queue(task_id)

    async def execute_course(self, task_id: str, request: CourseRequest) -> None:
        """Execute a course generation task asynchronously."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task_info = self.tasks[task_id]
        task_info["started_at"] = datetime.now().isoformat()
        task_info["status"] = "running"

        try:
            logger.info(f"== Starting course generation: {task_id}") 
            
            # Add the examples directory to Python path
            examples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'examples', "integration-with-fastapi-nextjs"))
            sys.path.append(examples_dir)
            
            from flows.courses_generator.course_generator_agent import generate_course
            
            # Run tutorial generation in a thread to not block the event loop
            loop = asyncio.get_running_loop()

            # Create event for task completion
            self._handle_event("task_solve_start", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "Course generation started"
            })

            request = CourseRequest(
                subject=request.subject,
                number_of_chapters=request.number_of_chapters,
                level=request.level,
                words_by_chapter=request.words_by_chapter,
                target_directory="./courses/python3",
                pdf_generation=True,
                docx_generation=True,
                epub_generation=False,
                model=request.model_name,
                model_name=request.model_name,
            )

            logger.info(f"== Course request: {request}")

            result = await loop.run_in_executor(
                None,
                lambda: asyncio.run(generate_course(
                    request,
                    task_id=task_id,
                    _handle_event=self._handle_event
                ))
            )
            logger.info(f"== Course generation result: {result}")

            self._update_task_success(task_info, result, None) 
            
            # Create event for task completion
            self._handle_event("task_solve_end", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "Course generation completed",
                "result": result
            })
            
        except Exception as e:
            self._update_task_failure(task_info, e)
            
            # Create event for task failure
            self._handle_event("error_tool_execution", {
                "task_id": task_id,
                "message": f"Tutorial generation failed: {str(e)}"
            })
            
            logger.exception(f"Error generating tutorial {task_id}")
        finally:
            self.remove_task_event_queue(task_id)


    async def execute_journey(self, task_id: str, request: JourneyRequest) -> None:
        """Execute a journey generation task asynchronously."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task_info = self.tasks[task_id]
        task_info["started_at"] = datetime.now().isoformat()
        task_info["status"] = "running"

        try:
            logger.info(f"== Starting journey generation: {task_id}") 
            
            # Add the examples directory to Python path
            examples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'examples', "integration-with-fastapi-nextjs"))
            sys.path.append(examples_dir)
            
            from flows.planner_journey.planner import generate_journey_plan
            
            # Run tutorial generation in a thread to not block the event loop
            loop = asyncio.get_running_loop()

            # Create event for task completion
            self._handle_event("task_solve_start", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "Journey generation started"
            }) 

            result = await loop.run_in_executor(
                None,
                lambda: asyncio.run(generate_journey_plan(
                    destination=request.destination,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    budget=request.budget,
                    model=request.model,
                    task_id=task_id,
                    _handle_event=self._handle_event
                ))
            )
            logger.debug(f"================================================================")
            logger.info(f"================================================================")
            logger.info(f"== Journey generation result: {result}")

            self._update_task_success(task_info, result, None) 
            
            # Create event for task completion
            self._handle_event("task_solve_end", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "Journey generation completed",
                "result": result
            })
            
        except Exception as e:
            self._update_task_failure(task_info, e)
            
            # Create event for task failure
            self._handle_event("error_tool_execution", {
                "task_id": task_id,
                "message": f"Tutorial generation failed: {str(e)}"
            })
            
            logger.exception(f"Error generating tutorial {task_id}")
        finally:
            self.remove_task_event_queue(task_id)

    async def execute_quizz(self, task_id: str, request: QuizRequest) -> None:
        """Execute a quiz generation task asynchronously."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task_info = self.tasks[task_id]
        task_info["started_at"] = datetime.now().isoformat()
        task_info["status"] = "running"

        try:
            logger.info(f"== Starting quiz generation: {task_id}") 
            
            # Add the examples directory to Python path
            examples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'examples', "integration-with-fastapi-nextjs"))
            sys.path.append(examples_dir)
            
            from flows.questions_and_answers.question_and_anwsers import generate_quiz
            
            # Run tutorial generation in a thread to not block the event loop
            loop = asyncio.get_running_loop()

            # Create event for task completion
            self._handle_event("task_solve_start", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "Quiz generation started"
            }) 

            result = await loop.run_in_executor(
                None,
                lambda: asyncio.run(generate_quiz(
                    file_path=request.file_path,
                    model=request.model,
                    num_questions=request.num_questions,
                    token_limit=request.token_limit,
                    save=request.save,
                    task_id=task_id,
                    _handle_event=self._handle_event
                ))
            )
            logger.debug(f"================================================================")
            logger.info(f"================================================================")
            logger.info(f"== Journey generation result: {result}")

            self._update_task_success(task_info, result, None) 
            
            # Create event for task completion
            self._handle_event("task_solve_end", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "Journey generation completed",
                "result": result
            })
            
        except Exception as e:
            self._update_task_failure(task_info, e)
            
            # Create event for task failure
            self._handle_event("error_tool_execution", {
                "task_id": task_id,
                "message": f"Tutorial generation failed: {str(e)}"
            })
            
            logger.exception(f"Error generating tutorial {task_id}")
        finally:
            self.remove_task_event_queue(task_id)

    async def execute_analyze_paper(self, task_id: str, request: AnalyzePaperRequest) -> None:
        """Execute a paper analysis task asynchronously."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task_info = self.tasks[task_id]
        task_info["started_at"] = datetime.now().isoformat()
        task_info["status"] = "running"

        try:
            logger.info(f"== Starting paper analysis: {task_id}") 
            
            # Add the examples directory to Python path
            examples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'examples', "integration-with-fastapi-nextjs"))
            sys.path.append(examples_dir)
            
            from flows.analyze_paper.analyze_paper import generate_analyze_paper
            
            # Run tutorial generation in a thread to not block the event loop
            loop = asyncio.get_running_loop()

            # Create event for task completion
            self._handle_event("task_solve_start", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "Paper analysis started"
            }) 

            result = await loop.run_in_executor(
                None,
                lambda: asyncio.run(generate_analyze_paper(
                    file_path=request.file_path,
                    text_extraction_model=request.text_extraction_model or "gemini/gemini-2.0-flash",
                    cleaning_model=request.cleaning_model or "gemini/gemini-2.0-flash",
                    writing_model=request.writing_model or "gemini/gemini-2.0-flash",
                    # output_dir=request.output_dir,
                    copy_to_clipboard_flag=request.copy_to_clipboard_flag or True,
                    max_character_count=request.max_character_count or 3000,
                    task_id=task_id,
                    _handle_event=self._handle_event
                ))
            )
            logger.debug(f"================================================================")
            logger.info(f"================================================================")
            logger.info(f"== Journey generation result: {result}")

            self._update_task_success(task_info, result, None) 
            
            # Create event for task completion
            self._handle_event("task_solve_end", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "Paper analysis completed",
                "result": result
            })
            
        except Exception as e:
            self._update_task_failure(task_info, e)
            
            # Create event for task failure
            self._handle_event("error_tool_execution", {
                "task_id": task_id,
                "message": f"Paper analysis failed: {str(e)}"
            })
            
            logger.exception(f"Error generating tutorial {task_id}")
        finally:
            self.remove_task_event_queue(task_id)

    async def execute_linkedin_introduce_content(self, task_id: str, request: LinkedInIntroduceContentRequest) -> None:
        """Execute a LinkedIn introduce content task asynchronously."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task_info = self.tasks[task_id]
        task_info["started_at"] = datetime.now().isoformat()
        task_info["status"] = "running"

        try:
            logger.info(f"== Starting paper analysis: {task_id}") 
            
            # Add the examples directory to Python path
            examples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'examples', "integration-with-fastapi-nextjs"))
            sys.path.append(examples_dir)
            
            from flows.linkedin_introduce_content.linkedin_introduce_content import generate_linkedin_introduce_content
            
            # Run tutorial generation in a thread to not block the event loop
            loop = asyncio.get_running_loop()

            # Create event for task completion
            self._handle_event("task_solve_start", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "LinkedIn introduce content started"
            }) 

            result = await loop.run_in_executor(
                None,
                lambda: asyncio.run(generate_linkedin_introduce_content(
                    file_path=request.file_path,
                    analysis_model=request.analysis_model or "gemini/gemini-2.0-flash", 
                    writing_model=request.writing_model or "gemini/gemini-2.0-flash",
                    cleaning_model=request.cleaning_model or "gemini/gemini-2.0-flash",
                    formatting_model=request.formatting_model or "gemini/gemini-2.0-flash",
                    copy_to_clipboard_flag=request.copy_to_clipboard_flag or True, 
                    intent=request.intent or None,
                    mock_analysis=request.mock_analysis or False,
                    task_id=task_id,
                    _handle_event=self._handle_event
                ))
            )
            logger.debug(f"================================================================")
            logger.info(f"================================================================")
            logger.info(f"== Journey generation result: {result}")

            self._update_task_success(task_info, result, None) 
            
            # Create event for task completion
            self._handle_event("task_solve_end", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "LinkedIn introduce content completed",
                "result": result
            })
            
        except Exception as e:
            self._update_task_failure(task_info, e)
            
            # Create event for task failure
            self._handle_event("error_tool_execution", {
                "task_id": task_id,
                "message": f"LinkedIn introduce content failed: {str(e)}"
            })
            
            logger.exception(f"Error generating tutorial {task_id}")
        finally:
            self.remove_task_event_queue(task_id)

    async def execute_convert(self, task_id: str, request: ConvertRequest) -> None:
        """Execute a PDF to Markdown conversion task asynchronously."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task_info = self.tasks[task_id]
        task_info["started_at"] = datetime.now().isoformat()
        task_info["status"] = "running"

        try:
            logger.info(f"== Starting PDF to Markdown conversion: {task_id}") 
            
            # Add the examples directory to Python path
            examples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'examples', "integration-with-fastapi-nextjs"))
            sys.path.append(examples_dir)
            
            from flows.pdf_to_markdown.pdf_to_markdown import convert
            
            # Run tutorial generation in a thread to not block the event loop
            loop = asyncio.get_running_loop()

            # Create event for task completion
            self._handle_event("task_solve_start", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "PDF to Markdown conversion started"
            }) 

            result = await loop.run_in_executor(
                None,
                lambda: asyncio.run(convert(
                    input_pdf=request.input_pdf,
                    output_md=request.output_md,
                    model=request.model,
                    system_prompt=request.system_prompt,
                    task_id=task_id,
                    _handle_event=self._handle_event
                ))
            )
            logger.debug(f"================================================================")
            logger.info(f"================================================================")
            logger.info(f"== Journey generation result: {result}")

            self._update_task_success(task_info, result, None) 
            
            # Create event for task completion
            self._handle_event("task_solve_end", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "PDF to Markdown conversion completed",
                "result": result
            })
            
        except Exception as e:
            self._update_task_failure(task_info, e)
            
            # Create event for task failure
            self._handle_event("error_tool_execution", {
                "task_id": task_id,
                "message": f"PDF to Markdown conversion failed: {str(e)}"
            })
            
            logger.exception(f"Error converting PDF to Markdown {task_id}")
        finally:
            self.remove_task_event_queue(task_id)

    async def execute_image_generation(self, task_id: str, request: ImageGenerationRequest) -> None:
        """Execute an image generation task asynchronously."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task_info = self.tasks[task_id]
        task_info["started_at"] = datetime.now().isoformat()
        task_info["status"] = "running"

        try:
            logger.info(f"== Starting image generation: {task_id}") 
            
            # Add the examples directory to Python path
            examples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'examples', "integration-with-fastapi-nextjs"))
            sys.path.append(examples_dir)
            
            from flows.image_generation.image_generation_flow import generate_image
            
            # Run tutorial generation in a thread to not block the event loop
            loop = asyncio.get_running_loop()

            # Create event for task completion
            self._handle_event("task_solve_start", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "Image generation started"
            }) 

            result = await loop.run_in_executor(
                None,
                lambda: asyncio.run(generate_image(
                    prompt=request.prompt,
                    model_type=request.model_type,
                    style=request.style,
                    size=request.size,
                    analysis_model=request.analysis_model or "gemini/gemini-2.0-flash",
                    enhancement_model=request.enhancement_model or "gemini/gemini-2.0-flash",
                    task_id=task_id,
                    _handle_event=self._handle_event
                ))
            )
            logger.debug(f"================================================================")
            logger.info(f"================================================================")
            logger.info(f"== Journey generation result: {result}")

            self._update_task_success(task_info, result, None) 
            
            # Create event for task completion
            self._handle_event("task_solve_end", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "PDF to Markdown conversion completed",
                "result": result
            })
            
        except Exception as e:
            self._update_task_failure(task_info, e)
            
            # Create event for task failure
            self._handle_event("error_tool_execution", {
                "task_id": task_id,
                "message": f"PDF to Markdown conversion failed: {str(e)}"
            })
            
            logger.exception(f"Error converting PDF to Markdown {task_id}")
        finally:
            self.remove_task_event_queue(task_id)

    async def execute_book_creation_novel_only(self, task_id: str, request: BookNovelRequest) -> None:
        """Execute an image generation task asynchronously."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task_info = self.tasks[task_id]
        task_info["started_at"] = datetime.now().isoformat()
        task_info["status"] = "running"

        try:
            logger.info(f"== Starting image generation: {task_id}") 
            
            # Add the examples directory to Python path
            examples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'examples', "integration-with-fastapi-nextjs"))
            sys.path.append(examples_dir)
            
            from flows.book_animation.book_novel import create_book
            
            # Run tutorial generation in a thread to not block the event loop
            loop = asyncio.get_running_loop()

            # Create event for task completion
            self._handle_event("task_solve_start", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "Image generation started"
            }) 

            example_content = """
            A psychological exploration of memory and identity through the lens of an unreliable narrator.
            Set in a small coastal town, the story follows a reclusive writer who begins receiving mysterious
            letters that seem to be written by their younger self, forcing them to confront long-buried truths
            about their past.
            """
            result = await loop.run_in_executor(
                None,
                lambda: asyncio.run(create_book(
                    content=example_content,
                    title="Echoes of Yesterday",
                    author="A.I. Wordsworth",
                    output_path="novel.md",
                    num_chapters=3,
                    words_per_chapter=3000,
                    narration_style={
                        "type": "unreliable_narrator",
                        "perspective": "first person with questionable memory",
                        "tense": "present"
                    },
                    literary_style={
                        "genre": "psychological literary fiction",
                        "tone": "introspective and unsettling",
                        "themes": ["memory", "identity", "truth", "self-deception"],
                        "writing_style": "stream of consciousness with unreliable elements",
                        "influences": ["Virginia Woolf", "Kazuo Ishiguro", "Vladimir Nabokov"]
                    },
                    target_audience="Readers of literary fiction and psychological narratives",
                    task_id=task_id,
                    _handle_event=self._handle_event
                ))
            )
            logger.debug(f"================================================================")
            logger.info(f"================================================================")
            logger.info(f"== Journey generation result: {result}")

            self._update_task_success(task_info, result, None) 
            
            # Create event for task completion
            self._handle_event("task_solve_end", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "PDF to Markdown conversion completed",
                "result": result
            })
            
        except Exception as e:
            self._update_task_failure(task_info, e)
            
            # Create event for task failure
            self._handle_event("error_tool_execution", {
                "task_id": task_id,
                "message": f"PDF to Markdown conversion failed: {str(e)}"
            })
            
            logger.exception(f"Error converting PDF to Markdown {task_id}")
        finally:
            self.remove_task_event_queue(task_id)

    async def execute_image_analysis(self, task_id: str, request: ImageAnalysisRequest) -> None:
        """Execute an image analysis task asynchronously."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task_info = self.tasks[task_id]
        task_info["started_at"] = datetime.now().isoformat()
        task_info["status"] = "running"

        try:
            logger.info(f"== Starting image analysis: {task_id}") 
            
            # Add the examples directory to Python path
            examples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'examples', "integration-with-fastapi-nextjs"))
            sys.path.append(examples_dir)
            
            from flows.image_analysis.image_analysis_flow import analyze_image_workflow
            
            # Run tutorial generation in a thread to not block the event loop
            loop = asyncio.get_running_loop()

            # Create event for task completion
            self._handle_event("task_solve_start", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "Image analysis started"
            })

            result = await loop.run_in_executor(
                None,
                lambda: asyncio.run(analyze_image_workflow(  
                    image_url=request.image_url,
                    image_context=request.image_context,
                    analysis_context=request.analysis_context,
                    vision_model=request.vision_model,
                    analysis_model=request.analysis_model,
                    task_id=task_id,
                    _handle_event=self._handle_event
                ))
            )
            logger.debug(f"================================================================")
            logger.info(f"================================================================")
            logger.info(f"== Image analysis result: {result}")

            self._update_task_success(task_info, result, None) 
            
            # Create event for task completion
            self._handle_event("task_solve_end", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "Image analysis completed",
                "result": result
            })
            
        except Exception as e:
            self._update_task_failure(task_info, e)
            
            # Create event for task failure
            self._handle_event("error_tool_execution", {
                "task_id": task_id,
                "message": f"Image analysis failed: {str(e)}"
            })
            
            logger.exception(f"Error analyzing image {task_id}")
        finally:
            self.remove_task_event_queue(task_id) 
            
            # Create event for task completion
            self._handle_event("task_solve_end", {
                "task_id": task_id, 
                "agent_id": "default",
                "message": "Image analysis completed",
                "result": result
            })