import asyncio
import sqlite3
from dataclasses import dataclass
from typing import List

import instructor
import litellm
from nanoid import generate

# Constants
MODEL_NAME = "gemini/gemini-2.0-flash"
DB_PATH = "agent_tasks.db"
VALID_STATUSES = {'todo', 'in-progress', 'review', 'done', 'blocked'}

# Global client for AI interactions
client = instructor.from_litellm(litellm.acompletion)

# Database setup
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Create tasks table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        task_description TEXT NOT NULL
    )
''')

# Create subtasks table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS subtasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT NOT NULL,
        step INTEGER NOT NULL,
        description TEXT NOT NULL,
        status TEXT DEFAULT 'todo' CHECK(status IN ('todo', 'in-progress', 'review', 'done', 'blocked')),
        FOREIGN KEY (task_id) REFERENCES tasks(task_id)
    )
''')
conn.commit()

# Dataclasses
@dataclass
class SubtaskWithStatus:
    """Subtask with status information.
    
    Attributes:
        step: The step number in the plan (1-based)
        description: Detailed description of the subtask
        status: Current status of the subtask. Must be one of: 
            'todo', 'in-progress', 'review', 'done', or 'blocked'
    """
    step: int
    description: str
    status: str = "todo"

@dataclass
class SubtaskResponse:
    step: int
    description: str

@dataclass
class PlanResult:
    """Result container for plan generation and retrieval."""
    task_id: str
    task_description: str
    subtasks: List[SubtaskWithStatus]

# Existing Tools
async def create_project_plan(task_description: str, tools_description: str = None) -> PlanResult:
    """Generate an AI-powered project plan by decomposing a task.

    Args:
        task_description: Description of the main task to be planned.
        tools_description: Optional description of available tools to consider.

    Returns:
        PlanResult: A dataclass object containing the generated project plan with the following attributes:
            - task_id (str): A unique identifier for the task, prefixed with "task_" followed by a random nanoid (e.g., "task_abc123").
            - task_description (str): The original task description provided as input, preserved verbatim.
            - subtasks (List[SubtaskWithStatus]): A list of subtask objects, where each SubtaskWithStatus has:
                - step (int): A positive integer indicating the subtask's order in the plan (e.g., 1, 2, 3).
                - description (str): A detailed description of the subtask, generated by the AI model.
                - status (str): The initial status of the subtask, always set to "todo" for newly created subtasks.

    Raises:
        ValueError: If the AI response is malformed (not a list or missing required fields).
    """
    if tools_description:
        tools_str = f"Consider the following tools for the task:\n\n{tools_description}\n\n"
    else:
        tools_str = ""
    prompt = f"Break down the following task into clear subtasks with steps:\n\n{task_description}\n\n{tools_str}Return the subtasks as a JSON array of objects, each with 'step' (integer) and 'description' (string) fields."

    response = await client.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_model=List[SubtaskResponse]
    )

    # Validate AI response
    if not isinstance(response, list):
        raise ValueError(
            "The AI model returned an invalid response format. Expected a list of subtasks, "
            "but got a different type. Please check your prompt and try again with a different task description."
        )
    for subtask in response:
        if not isinstance(subtask, SubtaskResponse):
            raise ValueError(
                "Invalid subtask format in AI response. Each subtask must have 'step' (integer) "
                "and 'description' (string) fields. Please verify the model output format."
            )

    task_id = "task_" + generate()
    subtasks_with_status = [
        SubtaskWithStatus(step=subtask.step, description=subtask.description, status="todo")
        for subtask in response
    ]

    # Store in database within a transaction
    with conn:
        conn.execute('INSERT INTO tasks (task_id, task_description) VALUES (?, ?)', 
                     (task_id, task_description))
        conn.executemany(
            'INSERT INTO subtasks (task_id, step, description, status) VALUES (?, ?, ?, ?)',
            [(task_id, s.step, s.description, s.status) for s in subtasks_with_status]
        )

    return PlanResult(task_id=task_id, task_description=task_description, subtasks=subtasks_with_status)

async def retrieve_project_plan(task_id: str) -> PlanResult:
    """Retrieve a project plan for a specific task."""
    cursor = conn.cursor()
    cursor.execute('SELECT task_description FROM tasks WHERE task_id = ?', (task_id,))
    task_row = cursor.fetchone()
    if not task_row:
        raise ValueError(
            f"No project plan found for task ID '{task_id}'. "
            "Possible reasons:\n"
            "1. The task ID may be incorrect - verify the ID and try again\n"
            "2. The plan may have been deleted - create a new plan if needed"
        )
    
    cursor.execute('SELECT step, description, status FROM subtasks WHERE task_id = ? ORDER BY step', 
                   (task_id,))
    subtasks_rows = cursor.fetchall()
    
    subtasks = [SubtaskWithStatus(step=step, description=desc, status=status) 
                for step, desc, status in subtasks_rows]

    return PlanResult(task_id=task_id, task_description=task_row[0], subtasks=subtasks)

async def update_subtask_status_by_id(task_id: str, step: int, status: str) -> str:
    """Update status of a specific subtask within a project plan.
    
    Args:
        task_id: ID of the task containing the subtask
        step: Step number of the subtask to update
        status: New status for the subtask. Must be one of:
            'todo', 'in-progress', 'review', 'done', or 'blocked'
    
    Returns:
        str: Confirmation message of the update
    
    Raises:
        ValueError: If the status is invalid or subtask not found
    """
    status = status.lower()
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Valid statuses are: {sorted(VALID_STATUSES)}. "
            "Please use one of these predefined status values."
        )

    cursor = conn.cursor()
    cursor.execute('UPDATE subtasks SET status = ? WHERE task_id = ? AND step = ?', 
                   (status, task_id, step))
    conn.commit()
    
    if cursor.rowcount == 0:
        raise ValueError(
            f"Could not update subtask - no subtask found for task ID '{task_id}' and step {step}. "
            "Possible solutions:\n"
            f"1. Verify the task ID is correct using retrieve_project_plan('{task_id}')\n"
            f"2. Check the step number exists in the plan (valid steps: 1-{step})"
        )

    return f"Step {step} of task {task_id} updated to '{status}'."

# New Tools
async def get_subtasks_by_status(task_id: str, status: str) -> List[SubtaskWithStatus]:
    """Retrieve all subtasks of a task that have a specific status.
    
    Args:
        task_id: ID of the task
        status: Status to filter by. Must be one of: 'todo', 'in-progress', 'review', 'done', 'blocked'
    
    Returns:
        List[SubtaskWithStatus]: List of subtasks matching the status
    
    Raises:
        ValueError: If the status is invalid or task_id does not exist
    """
    status = status.lower()
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Valid statuses are: {sorted(VALID_STATUSES)}")
    
    cursor = conn.cursor()
    cursor.execute('SELECT task_id FROM tasks WHERE task_id = ?', (task_id,))
    if cursor.fetchone() is None:
        raise ValueError(f"Task ID '{task_id}' does not exist")
    
    cursor.execute('SELECT step, description, status FROM subtasks WHERE task_id = ? AND status = ? ORDER BY step', 
                   (task_id, status))
    subtasks = [SubtaskWithStatus(step=step, description=desc, status=status) 
                for step, desc, status in cursor.fetchall()]
    return subtasks

async def update_subtasks_status(task_id: str, steps: List[int], status: str) -> str:
    """Update the status of multiple subtasks in a task.
    
    Args:
        task_id: ID of the task
        steps: List of step numbers to update
        status: New status for the subtasks. Must be one of: 'todo', 'in-progress', 'review', 'done', 'blocked'
    
    Returns:
        str: Confirmation message of the updates
    
    Raises:
        ValueError: If the status is invalid, task_id does not exist, or any step is invalid
    """
    if not steps:
        return "No steps provided to update."
    
    status = status.lower()
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Valid statuses are: {sorted(VALID_STATUSES)}")
    
    cursor = conn.cursor()
    cursor.execute('SELECT task_id FROM tasks WHERE task_id = ?', (task_id,))
    if cursor.fetchone() is None:
        raise ValueError(f"Task ID '{task_id}' does not exist")
    
    cursor.execute('SELECT step FROM subtasks WHERE task_id = ?', (task_id,))
    existing_steps = {row[0] for row in cursor.fetchall()}
    invalid_steps = [step for step in steps if step not in existing_steps]
    if invalid_steps:
        raise ValueError(f"Invalid step numbers: {invalid_steps}. Valid steps for task '{task_id}' are: {sorted(existing_steps)}")
    
    with conn:
        conn.executemany('UPDATE subtasks SET status = ? WHERE task_id = ? AND step = ?', 
                         [(status, task_id, step) for step in steps])
    
    return f"Updated status to '{status}' for steps {steps} in task '{task_id}'."

# Demonstration
async def main():
    """Demonstrate the planning toolbox functionality."""
    try:
        print("🚀 Generating project plan...")
        plan = await create_project_plan("Develop a modern web application")
        print(f"\n📋 Project Details:\nTask ID: {plan.task_id}\nTask Description: {plan.task_description}")
        print("\n🔍 Initial Subtasks:")
        for s in plan.subtasks:
            print(f"Step {s.step}: {s.description} (Status: {s.status})")

        print(f"\n🔄 Updating status of Step {plan.subtasks[0].step}...")
        msg = await update_subtask_status_by_id(plan.task_id, plan.subtasks[0].step, "in-progress")
        print(msg)

        print("\n🔍 Getting all 'todo' subtasks:")
        todo_subtasks = await get_subtasks_by_status(plan.task_id, "todo")
        for s in todo_subtasks:
            print(f"Step {s.step}: {s.description}")

        if len(todo_subtasks) >= 2:
            steps_to_update = [s.step for s in todo_subtasks[:2]]
            msg = await update_subtasks_status(plan.task_id, steps_to_update, "in-progress")
            print(f"\n{msg}")

            print("\n🔍 Updated 'in-progress' subtasks:")
            in_progress_subtasks = await get_subtasks_by_status(plan.task_id, "in-progress")
            for s in in_progress_subtasks:
                print(f"Step {s.step}: {s.description}")

        try:
            await update_subtasks_status(plan.task_id, [999], "done")
        except ValueError as e:
            print(f"\n❌ Expected error: {e}")

        print("\n✅ Demonstration completed successfully!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())