

import asyncio
from collections.abc import Callable
import datetime
import os
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional

import pyperclip
import typer
from loguru import logger
from pydantic import BaseModel
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from quantalogic.flow.flow import Nodes, Workflow, WorkflowEvent, WorkflowEventType



# Create custom observer that uses _handle_event if provided
async def event_observer(event: WorkflowEvent, task_id: Optional[str] = None, _handle_event: Optional[Callable[[str, Dict[str, Any]], None]] = None):
    if not _handle_event:
        return

    # Base event data that's common across all events
    base_event_data = {
        "task_id": task_id,
        "agent_id": "default",
        "timestamp": datetime.datetime.now().isoformat(),
        "event_type": event.event_type.value
    }

    # Handle streaming chunks immediately
    logger.info(f"=========================== Event type: {event.event_type}  ============================")


    if event.event_type == WorkflowEventType.STREAMING_CHUNK:
        _handle_event("streaming_chunk", {
            **base_event_data,
            "content": event.result,  # Changed from event.context.get("result", "")
            "node_name": event.node_name,
            "message": "Streaming content chunk"
        })
        return

    # Event type specific handling
    event_mapping = {
        WorkflowEventType.WORKFLOW_STARTED: {
            "event": "workflow_started",
            "data": {
                **base_event_data,
                "message": "Starting tutorial generation",
            }
        },
        WorkflowEventType.WORKFLOW_COMPLETED: {
            "event": "workflow_completed",
            "data": {
                **base_event_data,
                "message": "Tutorial generation completed",
                "result": event.result
            }
        },
        WorkflowEventType.NODE_STARTED: {
            "event": "node_started",
            "data": {
                **base_event_data,
                "node_name": event.node_name,
                "message": f"Starting node: {event.node_name}"
            }
        },
        WorkflowEventType.NODE_COMPLETED: {
            "event": "node_completed",
            "data": {
                **base_event_data,
                "node_name": event.node_name,
                "result": event.result,
                "message": f"Completed node: {event.node_name}"
            }
        },
        WorkflowEventType.NODE_FAILED: {
            "event": "node_failed",
            "data": {
                **base_event_data,
                "node_name": event.node_name,
                "error": str(event.exception),
                "message": f"Node failed: {event.node_name}"
            }
        },
        WorkflowEventType.TRANSITION_EVALUATED: {
            "event": "transition_evaluated",
            "data": {
                **base_event_data,
                "from_node": event.transition_from,
                "to_node": event.transition_to,
                "message": f"Transition: {event.transition_from} -> {event.transition_to}"
            }
        }
    }

    # Get the event configuration
    event_config = event_mapping.get(event.event_type)
    if event_config:
        # Special handling for specific nodes
        if event.event_type == WorkflowEventType.NODE_COMPLETED:
            if event.node_name == "compile_book":
                _handle_event("workflow_completed", {
                    **base_event_data,
                    "message": "Tutorial compilation completed",
                    "result": event.result
                })
            elif event.node_name == "update_chapters":
                chapter_num = event.result
                total_chapters = len(event.context["structure"].chapters)
                _handle_event("task_progress", {
                    **base_event_data,
                    "message": f"Generated chapter {chapter_num} of {total_chapters}",
                    "progress": {
                        "current": chapter_num,
                        "total": total_chapters,
                        "percentage": round((chapter_num / total_chapters) * 100)
                    },
                    "preview": "\n".join(event.context["completed_chapters"][-1].split('\n')[:3])
                })
        
        # Send the event
        _handle_event(event_config["event"], event_config["data"])
