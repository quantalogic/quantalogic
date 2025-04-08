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

class SubtaskWithStatus(BaseModel):
    """Subtask with additional status information."""
    step: int
    description: str
    status: str = Field("todo", description="Current status of the subtask. Must be one of: 'todo', 'in-progress', 'review', 'done', or 'blocked'.")

class PlanResult(BaseModel):
    """Result container for plan generation."""
    task_id: str = Field(..., description="The generated task ID")
    task_description: str = Field(..., description="The original task description")
    subtasks: List[SubtaskWithStatus] = Field(..., description="List of generated subtasks")

# Tool to generate a plan
@create_tool
async def create_project_plan(task_description: str) -> PlanResult:
    """Generate a detailed, AI-powered project plan by decomposing a high-level task.
    
    This asynchronous tool leverages an AI model to break down complex tasks into 
    manageable, sequential subtasks with automatic tracking and status management.
    
    Key Features:
    - AI-driven task decomposition
    - Automatic subtask generation
    - Unique task ID generation
    - Persistent subtask storage
    
    Args:
        task_description (str): A clear, concise description of the project or task
            to be decomposed. The more specific the description, the more 
            precise the generated subtasks will be.
    
    Returns:
        PlanResult: A comprehensive plan containing:
        - task_id (str): A unique identifier for tracking the project
        - task_description (str): The original task description
        - subtasks (List[SubtaskWithStatus]): Sequentially ordered subtasks
    
    Raises:
        Exception: Propagates any errors from the LLM completion process
    
    Workflow Scenarios:
    1. Software Development Project:
        >>> project_plan = await create_project_plan("Build a task management web app")
        # Generates subtasks like: 
        # 1. Design UI/UX
        # 2. Set up backend infrastructure
        # 3. Implement user authentication
        # 4. Develop task CRUD operations
        # 5. Add real-time collaboration features
    
    2. Research Project Planning:
        >>> research_plan = await create_project_plan("Conduct market research for AI startups")
        # Might generate subtasks like:
        # 1. Define research objectives
        # 2. Identify target market segments
        # 3. Collect industry reports
        # 4. Conduct expert interviews
        # 5. Analyze and synthesize findings
    
    3. Product Launch Preparation:
        >>> launch_plan = await create_project_plan("Launch a new SaaS product")
        # Could include subtasks such as:
        # 1. Product positioning
        # 2. Competitive analysis
        # 3. Pricing strategy development
        # 4. Marketing campaign design
        # 5. Sales channel preparation
    
    Best Practices:
    - Provide clear, specific task descriptions
    - Use the returned task_id for subsequent tracking
    - Monitor and update subtask statuses as work progresses
    
    Example Usage:
    ```python
    async def main():
        project = await create_project_plan("Develop an AI-powered chatbot")
        print(f"Project ID: {project.task_id}")
        for subtask in project.subtasks:
            print(f"Step {subtask.step}: {subtask.description}")
    ```
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
            status="todo"
        ) for subtask in response.subtasks
    ]
    
    # Store subtasks in database
    await asyncio.to_thread(store_subtasks, task_id, subtasks_with_status)
    
    return PlanResult(
        task_id=task_id,
        task_description=task_description,
        subtasks=subtasks_with_status
    )

# Tool to retrieve the plan
@create_tool
async def retrieve_project_plan(task_id: str) -> PlanResult:
    """Retrieve a comprehensive project plan for a specific task.
    
    This asynchronous tool fetches the complete details of a previously 
    generated project plan, including all subtasks and their current statuses.
    
    Key Features:
    - Retrieve full project details by task ID
    - Access current status of all subtasks
    - Supports tracking project progress
    
    Args:
        task_id (str): Unique identifier of the project plan to retrieve
    
    Returns:
        PlanResult: Comprehensive project plan containing:
        - task_id: The unique identifier of the project
        - task_description: Original task description
        - subtasks: List of subtasks with their current statuses
    
    Raises:
        ValueError: If no plan exists for the given task_id
    
    Workflow Scenarios:
    1. Project Progress Tracking:
        >>> project = await create_project_plan("Build a mobile app")
        >>> retrieved_plan = await retrieve_project_plan(project.task_id)
        # Allows checking the current state of all subtasks
    
    2. Status Monitoring:
        >>> plan = await retrieve_project_plan("existing_project_id")
        >>> for subtask in plan.subtasks:
        ...     if subtask.status == "done":
        ...         print(f"Currently working on: {subtask.description}")
    
    3. Collaborative Project Management:
        >>> team_project = await retrieve_project_plan("team_project_id")
        >>> print(f"Project Overview: {team_project.task_description}")
        >>> print("Subtask Progress:")
        >>> for subtask in team_project.subtasks:
        ...     print(f"Step {subtask.step}: {subtask.description} - {subtask.status}")
    
    Best Practices:
    - Always use the task_id from create_project_plan
    - Regularly retrieve and monitor project plans
    - Use status tracking for team coordination
    
    Example Usage:
    ```python
    async def track_project_progress(project_id):
        project_plan = await retrieve_project_plan(project_id)
        completed_tasks = [
            task for task in project_plan.subtasks 
            if task.status == "done"
        ]
        print(f"Completed {len(completed_tasks)} out of {len(project_plan.subtasks)} tasks")
    ```
    """
    rows = await asyncio.to_thread(fetch_plan, task_id)
    if not rows:
        raise ValueError(f"No plan exists for task {task_id}")
    
    subtasks = [
        SubtaskWithStatus(
            step=row[0],
            description=row[1],
            status=row[2]  # Convert string to Status enum
        ) for row in rows
    ]
    
    return PlanResult(
        task_id=task_id,
        task_description="",  # Not stored in DB
        subtasks=subtasks
    )

def store_subtasks(task_id: str, subtasks: List[SubtaskWithStatus]):
    """Store subtasks in the database (synchronous)."""
    cursor = conn.cursor()
    for subtask in subtasks:
        cursor.execute(
            'INSERT INTO subtasks (task_id, step, description, status) VALUES (?, ?, ?, ?)',
            (task_id, subtask.step, subtask.description, subtask.status)
        )
    conn.commit()

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
async def update_subtask_status_by_id(task_id: str, step: int, status: str) -> str:
    """Update the status of a specific subtask within a project plan.
    
    This asynchronous tool allows precise tracking and management of 
    individual subtask progress across different workflow states.
    
    Key Features:
    - Fine-grained subtask status management
    - Supports predefined workflow states
    - Persistent status updates in database
    
    Args:
        task_id (str): Unique identifier of the project
        step (int): The specific step number to update
        status (str): New status for the subtask. Must be one of: 'todo', 'in-progress', 'review', 'done', or 'blocked'.
    
    Returns:
        str: A human-readable confirmation of the status update
    
    Raises:
        ValueError: If the task or step cannot be found
        sqlite3.Error: If there's an issue updating the database
    
    Workflow Scenarios:
    1. Task Progression:
        >>> await update_subtask_status_by_id("web_app_project", 1, "in-progress")
        # Marks the first step of web app project as in progress
    
    2. Blocking and Unblocking:
        >>> await update_subtask_status_by_id("research_project", 3, "blocked")
        # Indicates that step 3 is currently blocked
        >>> await update_subtask_status_by_id("research_project", 3, "todo")
        # Unblocks the task, ready to be worked on
    
    3. Quality Assurance Workflow:
        >>> await update_subtask_status_by_id("product_launch", 2, "review")
        # Moves a subtask to review status for verification
        >>> await update_subtask_status_by_id("product_launch", 2, "done")
        # Marks the subtask as completed after successful review
    
    Best Practices:
    - Update status sequentially and logically
    - Use BLOCKED status when external dependencies prevent progress
    - Regularly update statuses to maintain accurate project tracking
    
    Example Usage:
    ```python
    async def manage_project_workflow(project_id):
        # Start working on the first task
        await update_subtask_status_by_id(project_id, 1, "in-progress")
        
        # Simulate task completion
        await asyncio.sleep(5)  # Simulating work
        await update_subtask_status_by_id(project_id, 1, "done")
    ```
    """
    # Use asyncio.to_thread to run database update in a separate thread
    await asyncio.to_thread(update_subtask_status, task_id, step, status)
    return f"Step {step} of task {task_id} updated to '{status}'."

def update_subtask_status(task_id: str, step: int, status: str):
    """Synchronously update a subtask's status in the database.
    
    This low-level function performs the actual database update for 
    changing a subtask's status. It is typically called via the 
    asynchronous update_subtask_status_by_id function.
    
    Args:
        task_id: Unique identifier of the task
        step: The specific step number to update
        status: New status value to set for the subtask (will be converted to lowercase).
               Must be one of: 'todo', 'in-progress', 'review', 'done', or 'blocked'.
    
    Notes:
        - Executes a direct SQL UPDATE query
        - Commits the transaction immediately
        - Converts status to lowercase before updating
        - Does not validate the status value (validation happens in update_subtask_status_by_id)
    
    Raises:
        sqlite3.Error: If the database update fails
    
    Example:
        >>> update_subtask_status("task_abc123", 1, "in-progress")
        # Updates the status of step 1 in task_abc123 to "in-progress"
    """
    cursor = conn.cursor()
    cursor.execute('UPDATE subtasks SET status = ? WHERE task_id = ? AND step = ?',
                   (status.lower(), task_id, step))
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
        project_plan = await create_project_plan("Develop a modern web application")
        
        print("\n📋 Project Details:")
        print(f"Task ID: {project_plan.task_id}")
        print(f"Task Description: {project_plan.task_description}")
        
        print("\n🔍 Initial Subtasks:")
        for subtask in project_plan.subtasks:
            print(f"Step {subtask.step}: {subtask.description} (Status: {subtask.status})")
        
        # 2. Update status of first subtask to in-progress
        first_step = project_plan.subtasks[0]
        print(f"\n🔄 Updating first step (Step {first_step.step}) status...")
        status_update = await update_subtask_status_by_id(
            project_plan.task_id, 
            first_step.step, 
            "in-progress"
        )
        print(status_update)
        
        # 3. Retrieve and display updated plan
        retrieved_plan = await retrieve_project_plan(project_plan.task_id)
        
        print("\n🔍 Updated Subtasks:")
        for subtask in retrieved_plan.subtasks:
            print(f"Step {subtask.step}: {subtask.description} (Status: {subtask.status})")
        
        # 4. Demonstrate error handling
        try:
            await update_subtask_status_by_id(project_plan.task_id, 999, "done")
        except Exception as e:
            print(f"\n❌ Expected error handling: {e}")
        
        print("\n✅ Planning toolbox demonstration completed successfully!")
    
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())