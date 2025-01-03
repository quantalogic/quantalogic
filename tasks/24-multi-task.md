Here's a specification for adding multi-task submission support to the API:

# Multi-Task Support Specification

## 1. Data Models

Add new models to handle task submission and tracking:

```python
class TaskSubmission(BaseModel):
    """Request model for task submission."""
    task: str
    model_name: Optional[str] = MODEL_NAME
    max_iterations: Optional[int] = 30
    
    model_config = {
        "extra": "forbid"
    }

class TaskStatus(BaseModel):
    """Task status response model."""
    task_id: str
    status: str  # "pending", "running", "completed", "failed"
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    total_tokens: Optional[int] = None
    model_name: Optional[str] = None
```

## 2. AgentState Modifications

Extend AgentState to track multiple tasks:

```python
class AgentState:
    def __init__(self):
        # Existing initialization
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.task_queues: Dict[str, asyncio.Queue] = {}
        
    async def submit_task(self, task_request: TaskSubmission) -> str:
        task_id = str(uuid.uuid4())
        self.tasks[task_id] = {
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "request": task_request.dict()
        }
        self.task_queues[task_id] = asyncio.Queue()
        return task_id
        
    async def execute_task(self, task_id: str):
        try:
            task = self.tasks[task_id]
            task["status"] = "running"
            task["started_at"] = datetime.now().isoformat()
            
            # Execute task with existing solve_task logic
            result = await self.agent.solve_task(
                task["request"]["task"],
                max_iterations=task["request"]["max_iterations"]
            )
            
            task["status"] = "completed"
            task["completed_at"] = datetime.now().isoformat()
            task["result"] = result
            task["total_tokens"] = self.agent.total_tokens
            task["model_name"] = self.get_current_model_name()
            
        except Exception as e:
            task["status"] = "failed"
            task["completed_at"] = datetime.now().isoformat()
            task["error"] = str(e)
```

## 3. New API Endpoints

Add these endpoints to the FastAPI application:

```python
@app.post("/tasks")
async def submit_task(request: TaskSubmission) -> Dict[str, str]:
    """Submit a new task and return its ID."""
    task_id = await agent_state.submit_task(request)
    # Start task execution in background
    asyncio.create_task(agent_state.execute_task(task_id))
    return {"task_id": task_id}

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str) -> TaskStatus:
    """Get the status of a specific task."""
    if task_id not in agent_state.tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = agent_state.tasks[task_id]
    return TaskStatus(**task)

@app.get("/tasks")
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 10,
    offset: int = 0
) -> List[TaskStatus]:
    """List all tasks with optional filtering."""
    tasks = []
    for task_id, task in agent_state.tasks.items():
        if status is None or task["status"] == status:
            tasks.append(TaskStatus(task_id=task_id, **task))
    
    return tasks[offset:offset + limit]
```

## 4. Event System Updates

Modify the event system to include task IDs:

```python
class EventMessage(BaseModel):
    id: str
    event: str
    task_id: Optional[str]  # Add task_id field
    data: Dict[str, Any]
    timestamp: str
```

## 5. Usage Example

```python
# Submit a task
response = await client.post("/tasks", json={
    "task": "Analyze this text...",
    "model_name": "gpt-4",
    "max_iterations": 30
})
task_id = response.json()["task_id"]

# Check task status
status = await client.get(f"/tasks/{task_id}")
print(status.json())

# Subscribe to task events
async for event in client.stream("/events"):
    if event.task_id == task_id:
        print(f"Task event: {event.event}")
```

## 6. Implementation Notes

1. Tasks are persisted in memory only - consider adding database storage for production
2. Each task gets its own event stream identified by task_id
3. Tasks are executed asynchronously in the background
4. Failed tasks store error information
5. Task cleanup should be implemented (e.g., removing old completed tasks)
6. Consider adding task cancellation functionality
7. Add rate limiting for task submission
8. Implement task priority queuing if needed

This specification provides the foundation for handling multiple concurrent tasks while maintaining the existing functionality of the system.