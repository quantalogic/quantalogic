import sqlite3
from dataclasses import dataclass
from typing import List

import instructor
import litellm
from nanoid import generate

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

# Dataclasses
@dataclass
class Subtask:
    """Represents a single subtask in a plan."""
    step: int  # The step number (must be positive)
    description: str  # The description of the subtask

@dataclass
class SubtaskList:
    """Container for a list of subtasks."""
    subtasks: List[Subtask]

@dataclass
class SubtaskWithStatus:
    """Subtask with additional status information."""
    step: int
    description: str
    status: str = "todo"  # Current status of the subtask. Must be one of: 'todo', 'in-progress', 'review', 'done', or 'blocked'.

@dataclass
class PlanResult:
    """Result container for plan generation."""
    task_id: str  # The generated task ID
    task_description: str  # The original task description
    subtasks: List[SubtaskWithStatus]  # List of generated subtasks

# Tool to generate a plan
async def create_project_plan(task_description: str) -> PlanResult:
    """Generate an AI-powered project plan by decomposing a task."""
    client = instructor.from_litellm(litellm)
    
    prompt = f"""
    Break down the following task into clear subtasks with steps:
    
    {task_description}
    
    Return the subtasks as a list of dictionaries with 'step' and 'description' fields.
    """
    
    response = await client.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
    )
    
    task_id = "task_" + generate()
    subtasks_with_status = [
        SubtaskWithStatus(
            step=subtask['step'], 
            description=subtask['description'], 
            status="todo"
        ) for subtask in response
    ]
    
    cursor = conn.cursor()
    cursor.executemany(
        'INSERT INTO subtasks (task_id, step, description, status) VALUES (?, ?, ?, ?)',
        [(task_id, s.step, s.description, s.status) for s in subtasks_with_status]
    )
    conn.commit()
    
    return PlanResult(
        task_id=task_id,
        task_description=task_description,
        subtasks=subtasks_with_status
    )

# Tool to retrieve the plan
async def retrieve_project_plan(task_id: str) -> PlanResult:
    """Retrieve a project plan for a specific task."""
    rows = await asyncio.to_thread(fetch_plan, task_id)
    if not rows:
        raise ValueError(f"No plan exists for task {task_id}")
    
    return PlanResult(
        task_id=task_id,
        task_description=rows[0][1],
        subtasks=[
            SubtaskWithStatus(step=step, description=desc, status=status)
            for step, desc, status in rows
        ]
    )

# Tool to update subtask status
async def update_subtask_status_by_id(task_id: str, step: int, status: str) -> str:
    """Update status of a specific subtask within a project plan."""
    await asyncio.to_thread(update_subtask_status, task_id, step, status)
    return f"Step {step} of task {task_id} updated to '{status}'."

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
    """Retrieve subtask details for a specific task from the database."""
    cursor = conn.cursor()
    cursor.execute('SELECT step, description, status FROM subtasks WHERE task_id = ? ORDER BY step',
                   (task_id,))
    return cursor.fetchall()

def update_subtask_status(task_id: str, step: int, status: str):
    """Synchronously update a subtask's status in the database."""
    cursor = conn.cursor()
    cursor.execute('UPDATE subtasks SET status = ? WHERE task_id = ? AND step = ?',
                   (status.lower(), task_id, step))
    conn.commit()

async def main():
    """Comprehensive demonstration of the planning toolbox functionality."""
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