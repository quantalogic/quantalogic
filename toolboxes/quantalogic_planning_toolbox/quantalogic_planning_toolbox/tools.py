import asyncio
import sqlite3
from enum import Enum
from typing import List

import instructor
import litellm
from nanoid import generate
from pydantic import BaseModel, Field

from quantalogic.tools import create_tool

# Model name for LLM completions
MODEL_NAME = "gemini/gemini-2.0-flash"

# Patch litellm for structured outputs
client = instructor.from_litellm(litellm.acompletion)

# Status enum for subtasks
class Status(str, Enum):
    """Valid status values for subtasks following pragmatic workflow states."""
    TODO = "todo"          # Task not yet started
    IN_PROGRESS = "in-progress"  # Actively being worked on
    REVIEW = "review"      # Completed but needs verification/QA
    DONE = "done"          # Fully completed and verified
    BLOCKED = "blocked"    # Cannot progress due to external dependency

# Database setup
DB_PATH = "tasks.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)  # Allow multi-threaded access
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS subtasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT,
        step INTEGER,
        description TEXT,
        status TEXT DEFAULT 'todo' CHECK(status IN ('todo', 'in-progress', 'review', 'done', 'blocked'))
    )
''')
conn.commit()

# Pydantic models
class Subtask(BaseModel):
    step: int = Field(...,  description="The step number (must be positive)")
    description: str = Field(...,description="The description of the subtask")

class SubtaskList(BaseModel):
    subtasks: List[Subtask]

class SubtaskWithStatus(Subtask):
    """Subtask with additional status information."""
    status: Status = Field(Status.TODO, description="Current status of the subtask")

class PlanResult(BaseModel):
    """Result container for plan generation."""
    task_id: str = Field(..., description="The generated task ID")
    task_description: str = Field(..., description="The original task description")
    subtasks: List[SubtaskWithStatus] = Field(..., description="List of generated subtasks")

# Tool to generate a plan
@create_tool
async def generate_plan(task_description: str) -> PlanResult:
    """Generate a detailed plan by breaking down a task into subtasks.
    
    This function takes a high-level task description and uses an LLM to decompose it into
    a sequence of actionable subtasks.
    
    Args:
        task_description: A string describing the high-level task to be decomposed
    
    Returns:
        PlanResult: Contains the generated task ID, original description, and subtasks
    
    Raises:
        Exception: Any exceptions from the LLM completion will be propagated
    
    Example:
        >>> await generate_plan("Develop a web application")
        PlanResult(
            task_id="abc123",
            task_description="Develop a web application",
            subtasks=[
                SubtaskWithStatus(
                    step=1, 
                    description="Design UI", 
                    status=Status.TODO
                )
            ]
        )
    """
    # Prepare the prompt for task decomposition
    prompt = (
        f"Break down the following task into subtasks. Provide the response as a JSON array "
        f"of objects, each with 'step' and 'description' fields. Task: {task_description}"
    )
    
    # Use LiteLLM client with Instructor for structured generation
    response = await client.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_model=SubtaskList,
    )
    
    # Generate a task_id using nanoid
    task_id = generate()
    
    # Create subtasks with default TODO status
    subtasks_with_status = [
        SubtaskWithStatus(
            step=subtask.step, 
            description=subtask.description, 
            status=Status.TODO
        ) for subtask in response.subtasks
    ]
    
    # Store subtasks in database
    await asyncio.to_thread(store_subtasks, task_id, subtasks_with_status)
    
    return PlanResult(
        task_id=task_id,
        task_description=task_description,
        subtasks=subtasks_with_status
    )

def store_subtasks(task_id: str, subtasks: List[SubtaskWithStatus]):
    """Store subtasks in the database (synchronous)."""
    cursor = conn.cursor()
    for subtask in subtasks:
        cursor.execute(
            'INSERT INTO subtasks (task_id, step, description, status) VALUES (?, ?, ?, ?)',
            (task_id, subtask.step, subtask.description, subtask.status.value)
        )
    conn.commit()

# Tool to retrieve the plan
@create_tool
async def get_plan(task_id: str) -> PlanResult:
    """Retrieve the current plan for a given task from the database.
    
    Args:
        task_id: The ID of the task to retrieve
    
    Returns:
        PlanResult: Contains the task ID and list of subtasks with their statuses
    
    Raises:
        ValueError: If no plan exists for the given task ID
    
    Example:
        >>> await get_plan("abc123")
        PlanResult(
            task_id="abc123",
            task_description="",  # Not stored in DB
            subtasks=[
                SubtaskWithStatus(
                    step=1, 
                    description="Design UI", 
                    status=Status.TODO
                )
            ]
        )
    """
    rows = await asyncio.to_thread(fetch_plan, task_id)
    if not rows:
        raise ValueError(f"No plan exists for task {task_id}")
    
    subtasks = [
        SubtaskWithStatus(
            step=row[0],
            description=row[1],
            status=Status(row[2])  # Convert string to Status enum
        ) for row in rows
    ]
    
    return PlanResult(
        task_id=task_id,
        task_description="",  # Not stored in DB
        subtasks=subtasks
    )

def fetch_plan(task_id: str):
    """Retrieve subtask details for a specific task from the database.
    
    This synchronous function queries the database to fetch all subtasks 
    associated with a given task ID, ordered by their step number.
    
    Args:
        task_id: Unique identifier of the task to retrieve subtasks for
    
    Returns:
        list: A list of tuples containing (step, description, status) 
              for each subtask in the task
    
    Notes:
        - Returns an empty list if no subtasks are found for the task
        - Subtasks are ordered by their step number
    
    Raises:
        sqlite3.Error: If there's an issue with the database query
    
    Example:
        >>> fetch_plan("task_abc123")
        [(1, "Design UI", "todo"), (2, "Implement backend", "in-progress")]
    """
    cursor = conn.cursor()
    cursor.execute('SELECT step, description, status FROM subtasks WHERE task_id = ? ORDER BY step',
                   (task_id,))
    return cursor.fetchall()

# Tool to update subtask status
@create_tool
async def update_status(task_id: str, step: int, status: Status) -> str:
    """Update the status of a specific subtask within a task.
    
    This asynchronous function allows changing the status of a particular 
    step in a task's workflow. It supports transitioning between different 
    predefined status states.
    
    Args:
        task_id: Unique identifier of the task containing the subtask
        step: The specific step number within the task to update
        status: New status for the subtask (todo, in-progress, review, done, or blocked)
    
    Returns:
        str: A human-readable confirmation message about the status update
    
    Raises:
        ValueError: If the task or step cannot be found
        sqlite3.Error: If there's an issue updating the database
    
    Workflow States:
        - todo: Task not yet started
        - in-progress: Task is currently being worked on
        - review: Task completed, awaiting verification
        - done: Task fully completed and verified
        - blocked: Task cannot progress due to external constraints
    
    Example:
        >>> await update_status("task_abc123", 1, Status.IN_PROGRESS)
        "Step 1 of task task_abc123 updated to 'in-progress'."
    """
    await asyncio.to_thread(update_subtask_status, task_id, step, status.value)
    return f"Step {step} of task {task_id} updated to '{status.value}'."

def update_subtask_status(task_id: str, step: int, status: str):
    """Synchronously update a subtask's status in the database.
    
    This low-level function performs the actual database update for 
    changing a subtask's status. It is typically called via the 
    asynchronous update_status function.
    
    Args:
        task_id: Unique identifier of the task
        step: The specific step number to update
        status: New status value to set for the subtask
    
    Notes:
        - Executes a direct SQL UPDATE query
        - Commits the transaction immediately
        - Does not validate the status value (validation happens in update_status)
    
    Raises:
        sqlite3.Error: If the database update fails
    
    Example:
        >>> update_subtask_status("task_abc123", 1, "in-progress")
        # Updates the status of step 1 in task_abc123 to "in-progress"
    """
    cursor = conn.cursor()
    cursor.execute('UPDATE subtasks SET status = ? WHERE task_id = ? AND step = ?',
                   (status, task_id, step))
    conn.commit()

async def main():
    """
    Comprehensive demonstration of the planning toolbox functionality.
    
    This main function showcases the entire workflow of:
    1. Generating a task plan
    2. Retrieving the plan
    3. Updating subtask statuses
    4. Handling different scenarios
    
    The scenario simulates developing a web application project.
    """
    try:
        # 1. Generate a plan for a web application project
        print("🚀 Generating project plan...")
        project_plan = await generate_plan("Develop a modern web application")
        
        print(f"\n📋 Project Details:")
        print(f"Task ID: {project_plan.task_id}")
        print(f"Task Description: {project_plan.task_description}")
        
        print("\n🔍 Initial Subtasks:")
        for subtask in project_plan.subtasks:
            print(f"Step {subtask.step}: {subtask.description} (Status: {subtask.status.value})")
        
        # 2. Update status of first subtask to in-progress
        first_step = project_plan.subtasks[0]
        print(f"\n🔄 Updating first step (Step {first_step.step}) status...")
        status_update = await update_status(
            project_plan.task_id, 
            first_step.step, 
            Status.IN_PROGRESS
        )
        print(status_update)
        
        # 3. Retrieve and display updated plan
        retrieved_plan = await get_plan(project_plan.task_id)
        
        print("\n🔍 Updated Subtasks:")
        for subtask in retrieved_plan.subtasks:
            print(f"Step {subtask.step}: {subtask.description} (Status: {subtask.status.value})")
        
        # 4. Demonstrate error handling
        try:
            await update_status(project_plan.task_id, 999, Status.DONE)
        except Exception as e:
            print(f"\n❌ Expected error handling: {e}")
        
        print("\n✅ Planning toolbox demonstration completed successfully!")
    
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())