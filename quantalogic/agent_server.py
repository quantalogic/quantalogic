#!/usr/bin/env python
"""FastAPI server for the QuantaLogic agent."""

import asyncio
import functools
import json
import logging
import signal
import sys
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from threading import Lock
from typing import Any, AsyncGenerator, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import BaseModel
from rich.console import Console

from quantalogic.agent_config import (
    MODEL_NAME,
    create_agent,
    create_coding_agent,  # noqa: F401
    create_orchestrator_agent,  # noqa: F401
)
from quantalogic.print_event import print_events

# Configure logger
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)

# Constants
SHUTDOWN_TIMEOUT = 5.0  # seconds
VALIDATION_TIMEOUT = 30.0  # seconds

def handle_sigterm(signum, frame):
    """Handle SIGTERM signal."""
    logger.info("Received SIGTERM signal")
    raise SystemExit(0)

signal.signal(signal.SIGTERM, handle_sigterm)

def get_version() -> str:
    """Get the current version of the package."""
    return "QuantaLogic version: 1.0.0"


class ServerState:
    """Global server state management."""

    def __init__(self):
        self.interrupt_count = 0
        self.force_exit = False
        self.is_shutting_down = False
        self.shutdown_initiated = asyncio.Event()
        self.shutdown_complete = asyncio.Event()
        self.server = None

    async def initiate_shutdown(self, force: bool = False):
        """Initiate the shutdown process."""
        if not self.is_shutting_down or force:
            logger.info("Initiating server shutdown...")
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
            logger.info("Graceful shutdown initiated (press Ctrl+C again to force)")
            asyncio.create_task(self.initiate_shutdown(force=False))
        else:
            logger.warning("Forced shutdown initiated...")
            # Use asyncio.create_task to avoid RuntimeError
            asyncio.create_task(self.initiate_shutdown(force=True))


# Models
class TaskRequest(BaseModel):
    """Request model for task solving."""

    task: str
    model_name: Optional[str] = MODEL_NAME
    max_iterations: Optional[int] = 30

    model_config = {
        "extra": "forbid"
    }


class TaskResponse(BaseModel):
    """Response model for task solving."""

    result: str
    total_tokens: int
    model_name: str
    version: str

    model_config = {
        "extra": "forbid"
    }


class EventMessage(BaseModel):
    """Event message model for SSE."""

    id: str
    event: str
    data: Dict[str, Any]
    timestamp: str

    model_config = {
        "extra": "forbid"
    }


class UserValidationRequest(BaseModel):
    """Request model for user validation."""

    question: str
    validation_id: str | None = None

    model_config = {
        "extra": "forbid"
    }


class UserValidationResponse(BaseModel):
    """Response model for user validation."""

    response: bool

    model_config = {
        "extra": "forbid"
    }


class AgentState:
    """Manages agent state and event queues."""

    def __init__(self):
        """Initialize the agent state."""
        self.agent = None
        self.event_queues: Dict[str, Queue] = {}
        self.queue_lock = Lock()
        self.client_counter = 0
        self.console = Console()
        self.validation_requests: Dict[str, Dict[str, Any]] = {}
        self.validation_responses: Dict[str, asyncio.Queue] = {}

    def add_client(self) -> str:
        """Add a new client and return its ID."""
        with self.queue_lock:
            self.client_counter += 1
            client_id = f"client_{self.client_counter}"
            self.event_queues[client_id] = Queue()
            logger.info(f"New client connected: {client_id}")
            return client_id

    def remove_client(self, client_id: str):
        """Remove a client and its event queue."""
        with self.queue_lock:
            if client_id in self.event_queues:
                del self.event_queues[client_id]
                logger.info(f"Client disconnected: {client_id}")

    def broadcast_event(self, event_type: str, data: Dict[str, Any]):
        """Broadcast an event to all connected clients."""
        try:
            formatted_data = self._format_data_for_client(data)
            event = EventMessage(
                id=f"evt_{datetime.now().timestamp()}",
                event=event_type,
                data=formatted_data,
                timestamp=datetime.now().isoformat(),
            )

            with self.queue_lock:
                for queue in self.event_queues.values():
                    queue.put_nowait(event)

            logger.debug(f"Broadcasted event: {event_type}")
        except Exception as e:
            logger.error(f"Error broadcasting event: {e}", exc_info=True)

    def _format_data_for_client(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format data for client-side rendering."""
        try:
            formatted_data = {}

            for key, value in data.items():
                if isinstance(value, (int, float, str, bool, list)):
                    formatted_data[key] = value
                elif isinstance(value, dict):
                    formatted_data[key] = self._format_data_for_client(value)
                else:
                    formatted_data[key] = str(value)

            return formatted_data
        except Exception as e:
            logger.error(f"Error formatting data: {e}", exc_info=True)
            return {"error": "Error formatting data"}

    def initialize_agent_with_sse_validation(self, model_name: str = MODEL_NAME):
        """Initialize agent with SSE-based user validation."""
        try:
            self.agent = create_agent(model_name)

            # Comprehensive list of agent events to track
            agent_events = [
                "session_start",
                "session_end",
                "session_add_message",
                "task_solve_start",
                "task_solve_end",
                "task_think_start",
                "task_think_end",
                "task_complete",
                "tool_execution_start",
                "tool_execution_end",
                "tool_execute_validation_start",
                "tool_execute_validation_end",
                "memory_full",
                "memory_compacted",
                "memory_summary",
                "error_max_iterations_reached",
                "error_tool_execution",
                "error_model_response",
            ]

            # Setup event handlers
            for event in agent_events:
                self.agent.event_emitter.on(event, lambda e, d, event=event: self._handle_event(event, d))

            # Override ask_for_user_validation with SSE-based method
            self.agent.ask_for_user_validation = self.sse_ask_for_user_validation

            logger.info(f"Agent initialized with model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}", exc_info=True)
            raise

    async def sse_ask_for_user_validation(self, question: str = "Do you want to continue?") -> bool:
        """SSE-based user validation method."""
        validation_id = str(uuid.uuid4())
        response_queue = asyncio.Queue()
        
        # Store validation request and response queue
        self.validation_requests[validation_id] = {
            "question": question,
            "timestamp": datetime.now().isoformat()
        }
        self.validation_responses[validation_id] = response_queue

        # Broadcast validation request
        self.broadcast_event("user_validation_request", {
            "validation_id": validation_id,
            "question": question
        })

        try:
            # Wait for response with timeout
            async with asyncio.timeout(VALIDATION_TIMEOUT):
                response = await response_queue.get()
                return response
        except asyncio.TimeoutError:
            logger.warning(f"Validation request timed out: {validation_id}")
            return False
        finally:
            # Cleanup
            if validation_id in self.validation_requests:
                del self.validation_requests[validation_id]
            if validation_id in self.validation_responses:
                del self.validation_responses[validation_id]

    def _handle_event(self, event_type: str, data: Dict[str, Any]):
        """Enhanced event handling with rich console output."""
        try:
            # Print events to server console
            print_events(event_type, data)

            # Log event details
            logger.info(f"Agent Event: {event_type}")
            logger.debug(f"Event Data: {data}")

            # Broadcast to clients
            self.broadcast_event(event_type, data)

        except Exception as e:
            logger.error(f"Error in event handling: {e}", exc_info=True)

    def get_current_model_name(self) -> str:
        """Get the current model name safely."""
        if self.agent and self.agent.model:
            return self.agent.model.model
        return MODEL_NAME

    async def cleanup(self):
        """Clean up resources during shutdown."""
        try:
            logger.info("Cleaning up resources...")
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
                logger.info("Cleanup completed")
        except asyncio.TimeoutError:
            logger.warning(f"Cleanup timed out after {SHUTDOWN_TIMEOUT} seconds")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
        finally:
            self.agent = None
            if server_state.force_exit:
                sys.exit(1)


# Initialize global states
server_state = ServerState()
agent_state = AgentState()

# Initialize FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app."""
    try:
        # Setup signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(handle_shutdown(s))
            )
        yield
    finally:
        logger.info("Shutting down server gracefully...")
        await server_state.initiate_shutdown()
        await agent_state.cleanup()
        server_state.shutdown_complete.set()
        logger.info("Server shutdown complete")

async def handle_shutdown(sig):
    """Handle shutdown signals."""
    if sig == signal.SIGINT and server_state.interrupt_count >= 1:
        # Force exit on second CTRL+C
        await server_state.initiate_shutdown(force=True)
    else:
        server_state.handle_interrupt()

app = FastAPI(
    title="QuantaLogic API",
    description="AI Agent Server for QuantaLogic",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="quantalogic/static"), name="static")

# Configure Jinja2 templates
templates = Jinja2Templates(directory="quantalogic/templates")

# Middleware to log requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    logger.debug(
        f"Path: {request.url.path} "
        f"Method: {request.method} "
        f"Time: {process_time:.3f}s "
        f"Status: {response.status_code}"
    )

    return response


@app.post("/validate_response/{validation_id}")
async def submit_validation_response(validation_id: str, response: UserValidationResponse):
    """Submit a validation response."""
    if validation_id not in agent_state.validation_responses:
        raise HTTPException(status_code=404, detail="Validation request not found")
    
    try:
        response_queue = agent_state.validation_responses[validation_id]
        await response_queue.put(response.response)
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        logger.error(f"Error processing validation response: {e}")
        raise HTTPException(status_code=500, detail="Failed to process validation response")


@app.post("/solve_task")
async def solve_task(request: TaskRequest) -> TaskResponse:
    """Solve a task using the AI agent."""
    try:
        # Initialize agent if not already initialized
        if not agent_state.agent:
            agent_state.initialize_agent_with_sse_validation(request.model_name)

        # Run solve_task in a thread pool since it's a blocking operation
        loop = asyncio.get_event_loop()
        solution = await loop.run_in_executor(
            None, functools.partial(agent_state.agent.solve_task, request.task, max_iterations=request.max_iterations)
        )

        # Emit task completion event with the final answer
        agent_state.broadcast_event("task_complete", {
            "result": solution,
            "total_tokens": agent_state.agent.total_tokens,
            "model_name": agent_state.get_current_model_name(),
            "timestamp": datetime.now().isoformat()
        })

        return TaskResponse(
            result=solution,
            total_tokens=agent_state.agent.total_tokens,
            model_name=agent_state.get_current_model_name(),
            version=get_version(),
        )

    except Exception as e:
        logger.error(f"Error solving task: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e), "traceback": traceback.format_exc()})


@app.get("/events")
async def event_stream(request: Request) -> StreamingResponse:
    """SSE endpoint for streaming agent events."""

    async def event_generator() -> AsyncGenerator[str, None]:
        client_id = agent_state.add_client()
        try:
            while not server_state.is_shutting_down:
                if await request.is_disconnected():
                    break

                try:
                    # Try to get an event from the queue with a timeout
                    event = agent_state.event_queues[client_id].get_nowait()
                    yield f"event: {event.event}\ndata: {json.dumps(event.dict())}\n\n"
                except Empty:
                    # No events available, yield a keepalive comment
                    yield ": keepalive\n\n"
                    await asyncio.sleep(0.1)

                # Check for shutdown during event processing
                if server_state.is_shutting_down:
                    yield "event: shutdown\ndata: {\"message\": \"Server shutting down\"}\n\n"
                    break

        finally:
            agent_state.remove_client(client_id)
            logger.info(f"Client {client_id} disconnected")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
        }
    )


@app.get("/")
async def get_index(request: Request) -> HTMLResponse:
    """Serve the main application page."""
    response = templates.TemplateResponse("index.html", {"request": request})
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# Update the Agent initialization to use SSE validation by default
AgentState.initialize_agent = AgentState.initialize_agent_with_sse_validation

if __name__ == "__main__":
    config = uvicorn.Config(
        "quantalogic.agent_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        timeout_keep_alive=5,
        access_log=True,
        timeout_graceful_shutdown=5  # Reduced from 10 to 5 seconds
    )
    server = uvicorn.Server(config)
    server_state.server = server
    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        sys.exit(1)