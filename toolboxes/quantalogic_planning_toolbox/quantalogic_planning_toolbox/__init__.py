import quantalogic_planning_toolbox.tools

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
        quantalogic_planning_toolbox.tools.create_project_plan,
        quantalogic_planning_toolbox.tools.get_subtasks_by_status,
        quantalogic_planning_toolbox.tools.retrieve_project_plan,
        quantalogic_planning_toolbox.tools.update_subtask_status_by_id,
        quantalogic_planning_toolbox.tools.update_subtasks_status
    ]
    
