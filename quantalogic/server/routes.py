"""API routes for the QuantaLogic server."""

import asyncio
import json
import uuid
from asyncio import Queue
from datetime import datetime
from typing import Empty, Optional

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from quantalogic.server.models import TaskStatus, TaskSubmission, UserValidationResponse
from quantalogic.server.state import agent_state

# Initialize templates
templates = Jinja2Templates(directory="quantalogic/server/templates")


async def submit_validation_response(validation_id: str, response: UserValidationResponse):
    """Submit a validation response."""
    if validation_id not in agent_state.validation_responses:
        raise HTTPException(status_code=404, detail="Validation request not found")

    response_queue = agent_state.validation_responses[validation_id]
    await response_queue.put(response.response)
    return {"status": "success"}


async def event_stream(request: Request, task_id: Optional[str] = None):
    """SSE endpoint for streaming agent events."""
    client_id = agent_state.add_client(task_id)

    try:
        # Determine the appropriate queue based on task_id
        if task_id:
            if task_id not in agent_state.task_event_queues:
                agent_state.task_event_queues[task_id] = Queue()
            queue = agent_state.task_event_queues[task_id]
        else:
            queue = agent_state.event_queues[client_id]

        async def generate():
            try:
                while True:
                    # Check for client disconnection
                    if await request.is_disconnected():
                        break

                    try:
                        # Non-blocking get with a short timeout
                        event = queue.get_nowait()
                        yield f"data: {json.dumps(event)}\n\n"
                    except Empty:
                        # Prevent tight loop and allow for disconnection checks
                        await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in event stream for client {client_id}: {e}")
            finally:
                # Ensure cleanup of client and task-specific resources
                agent_state.remove_client(client_id)
                if task_id:
                    agent_state.remove_task_event_queue(task_id)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            },
        )
    except Exception as e:
        logger.error(f"Event stream initialization error: {e}")
        agent_state.remove_client(client_id)
        raise


async def get_index(request: Request):
    """Serve the main application page."""
    return templates.TemplateResponse("index.html", {"request": request, "title": "QuantaLogic"})


async def submit_task(request: TaskSubmission):
    """Submit a new task and return its ID."""
    task_id = str(uuid.uuid4())
    agent_state.tasks[task_id] = {
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "task": request.task,
        "model_name": request.model_name,
    }
    return {"task_id": task_id}


async def get_task_status(task_id: str):
    """Get the status of a specific task."""
    if task_id not in agent_state.tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task_data = agent_state.tasks[task_id]
    return TaskStatus(**task_data)


async def list_tasks(status: Optional[str] = None, limit: int = 10, offset: int = 0):
    """List all tasks with optional filtering."""
    tasks = []
    for task_id, task_data in agent_state.tasks.items():
        if status is None or task_data["status"] == status:
            tasks.append({"task_id": task_id, **task_data})

    # Apply pagination
    paginated_tasks = tasks[offset : offset + limit]
    return {"tasks": paginated_tasks, "total": len(tasks), "limit": limit, "offset": offset}
