#!/usr/bin/env python
"""FastAPI server for the QuantaLogic agent."""

import asyncio
import functools
import json
import os
import shutil
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
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import BaseModel
from rich.console import Console

from quantalogic.agent import Agent
from quantalogic.agent_config import (
    MODEL_NAME,
)
from quantalogic.agent_factory import AgentRegistry, create_agent_for_mode
from quantalogic.console_print_events import console_print_events
from quantalogic.task_runner import configure_logger
from .utils import handle_sigterm, get_version
from .ServerState import ServerState
from .models import EventMessage, UserValidationRequest, UserValidationResponse, TaskSubmission, TaskStatus
from .AgentState import AgentState

# Configure logger
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)
class ToolParameters(BaseModel):
    """Parameters for tool configurations.
    
    This class defines all possible parameters that can be passed to different tools.
    Each tool will only use the parameters it needs.
    """
    # LLM and Model related parameters
    model_name: Optional[str] = None
    vision_model_name: Optional[str] = None
    provider: Optional[str] = None
    additional_info: Optional[str] = None

    # Database related parameters
    connection_string: Optional[str] = None

    # Git related parameters
    access_token: Optional[str] = None  # For Bitbucket
    auth_token: Optional[str] = None    # For GitHub and other git operations

    class Config:
        """Pydantic config for ToolParameters."""
        extra = "allow"  # Allow extra fields for future extensibility

class ToolConfig(BaseModel):
    """Configuration for a single tool."""
    type: str
    parameters: ToolParameters


class AgentConfig(BaseModel):
    """Configuration for creating a new agent."""
    id: str
    name: str
    description: str
    expertise: str
    mode: str = "custom"
    model_name: str
    tools: List[ToolConfig]

# Constants
SHUTDOWN_TIMEOUT = 10.0  # seconds
VALIDATION_TIMEOUT = 30.0  # seconds
UPLOAD_DIR = "/tmp/data"  # Directory for file uploads

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)

signal.signal(signal.SIGTERM, handle_sigterm)


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
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(handle_shutdown(s)))
        yield
    finally:
        logger.debug("Shutting down server gracefully...")
        await server_state.initiate_shutdown()
        await agent_state.cleanup()
        server_state.shutdown_complete.set()
        logger.debug("Server shutdown complete")


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
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Mount static files
# app.mount("/static", StaticFiles(directory="quantalogic/server/static"), name="static")

# Configure Jinja2 templates
# templates = Jinja2Templates(directory="quantalogic/server/templates")


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


@app.post("/api/agent/validation/{validation_id}")
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
    


@app.get("/api/agent/events")
async def event_stream(request: Request, task_id: Optional[str] = None) -> StreamingResponse:
    """SSE endpoint for streaming agent events."""

    async def event_generator() -> AsyncGenerator[str, None]:
        # Ensure unique client-task combination
        client_id = agent_state.add_client(task_id)
        logger.debug(f"Client {client_id} subscribed to {'task_id: ' + task_id if task_id else 'all events'}")

        try:
            while not server_state.is_shutting_down:
                if await request.is_disconnected():
                    logger.debug(f"Client {client_id} disconnected")
                    break

                #logger.info(f"Client {client_id} connected")
                #logger.info("agent_state.event_queues: " + str(agent_state.event_queues))

                try:
                    # Prioritize task-specific queue if task_id is provided
                    if task_id and task_id in agent_state.event_queues[client_id]:
                        event = agent_state.event_queues[client_id][task_id].get_nowait()
                        logger.debug(f"Sending task event to client {client_id}: {event}")
                    else:
                        # Fall back to global queue if no task_id
                        event = agent_state.event_queues[client_id]["global"].get_nowait()
                        logger.debug(f"Sending global event to client {client_id}: {event}")

                    # Format and yield the event
                    event_data = event.dict()
                    event_str = f"event: {event.event}\ndata: {json.dumps(event_data)}\n\n"
                    logger.debug(f"Sending SSE data: {event_str}")
                    yield event_str

                except Empty:
                    # Send keepalive to maintain connection
                    yield ": keepalive\n\n"
                    await asyncio.sleep(0.1)  # Increased sleep time to reduce load

                if server_state.is_shutting_down:
                    yield 'event: shutdown\ndata: {"message": "Server shutting down"}\n\n'
                    break

        finally:
            # Clean up the client's event queue
            agent_state.remove_client(client_id, task_id)
            logger.debug(f"Client {client_id} {'unsubscribed from task_id: ' + task_id if task_id else 'disconnected'}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",  # Disable proxy buffering
        },
    )


@app.get("/api/agent/")
async def get_index(request: Request) -> HTMLResponse:
    """Serve the main application page."""
    # response = templates.TemplateResponse("index.html", {"request": request})
    # response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    # response.headers["Pragma"] = "no-cache"
    # response.headers["Expires"] = "0"
    # return response
    return HTMLResponse(content="")


@app.post("/api/agent/upload")
async def upload_file(file: UploadFile = File(...)) -> Dict[str, str]:
    """Handle file uploads."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = str(uuid.uuid4())[:8]
        file_extension = os.path.splitext(file.filename)[1]
        new_filename = f"{timestamp}_{random_suffix}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, new_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {
            "status": "success",
            "filename": new_filename,
            "path": file_path
        }
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/tasks")
async def submit_task(request: TaskSubmission) -> Dict[str, str]:
    """Submit a new task and return its ID."""
    task_id = await agent_state.submit_task(request)
    # Start task execution in background
    asyncio.create_task(agent_state.execute_task(task_id))
    return {"task_id": task_id}


@app.get("/api/agent/tasks/{task_id}")
async def get_task_status(task_id: str) -> TaskStatus:
    """Get the status of a specific task."""
    if task_id not in agent_state.tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = agent_state.tasks[task_id]
    return TaskStatus(task_id=task_id, **task)


@app.get("/api/agent/tasks")
async def list_tasks(status: Optional[str] = None, limit: int = 10, offset: int = 0) -> List[TaskStatus]:
    """List all tasks with optional filtering."""
    tasks = []
    for task_id, task in agent_state.tasks.items():
        if status is None or task["status"] == status:
            tasks.append(TaskStatus(task_id=task_id, **task))

    return tasks[offset : offset + limit]


# Agent management endpoints
@app.post("/api/agent/agents")
async def create_agent(config: AgentConfig) -> Dict[str, bool]:
    """Create a new agent with the given configuration."""
    success = await agent_state.create_agent(config)
    return {"success": success}

@app.get("/api/agent/agents")
async def list_agents() -> List[AgentConfig]:
    """List all available agents."""
    return agent_state.list_agents()

@app.get("/api/agent/agents/{agent_id}")
async def get_agent(agent_id: str) -> AgentConfig:
    """Get agent configuration by ID."""
    config = agent_state.get_agent_config(agent_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return config

@app.get("/api/agent/download/{filename}")
async def download_file(filename: str):
    """Download a file from the upload directory."""
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/octet-stream'
    )

@app.get("/api/agent/health")
async def health_check() -> Dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    config = uvicorn.Config(
        "quantalogic.agent_server:app",
        host="0.0.0.0",
        port=8002,
        #reload=True,
        log_level="info",
        #timeout_keep_alive=5,
        access_log=True,
        #timeout_graceful_shutdown=10,  # Increased from 5 to 10 seconds
    )
    server = uvicorn.Server(config)
    server_state.server = server
    try:
        server.run()
    except KeyboardInterrupt:
        logger.debug("Received keyboard interrupt")
        sys.exit(1)
