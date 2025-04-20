from .tools import (
    create_project_plan,
    get_subtasks_by_status,
    retrieve_project_plan,
    update_subtask_status_by_id,
    update_subtasks_status,
)

__all__ = [
    "create_project_plan",
    "get_subtasks_by_status",
    "retrieve_project_plan",
    "update_subtask_status_by_id",
    "update_subtasks_status",
    "get_tools"
]

def get_tools():
    """Return a list of tool functions for registration."""
    return [
        create_project_plan,
        get_subtasks_by_status,
        retrieve_project_plan,
        update_subtask_status_by_id,
        update_subtasks_status
    ]
    
