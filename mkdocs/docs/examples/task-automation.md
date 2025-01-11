# Task Automation with AI

Learn how to automate complex tasks using QuantaLogic's intelligent agent system, combining multiple tools and reasoning capabilities.

## Overview

Task automation enables your agent to:
- Process web content
- Analyze and summarize information
- Integrate multiple tools
- Perform multi-step reasoning tasks

## Prerequisites

- Python 3.12 or later
- QuantaLogic library installed
- OpenAI API key (or alternative LLM provider)

## Setting Up Task Automation Tools

```python
import os
from quantalogic import Agent
from quantalogic.console_print_events import console_print_events
from quantalogic.console_print_token import console_print_token
from quantalogic.tools import (
    LLMTool, 
    MarkitdownTool
)

# Set API key
os.environ["OPENAI_API_KEY"] = "your-openai-key"

# Define model and tools
MODEL_NAME = "gpt-4o-mini"
agent = Agent(
    model_name=MODEL_NAME,
    tools=[
        MarkitdownTool(),
        LLMTool(
            model_name=MODEL_NAME, 
            on_token=console_print_token
        ),
    ],
)
```

## Available Automation Tools

| Tool | Description |
|------|-------------|
| `MarkitdownTool` | Read and process web content |
| `LLMTool` | Perform advanced reasoning tasks |

## Example Tasks

### 1. Web Content Analysis

```python
# Analyze and summarize latest AI research
result = agent.solve_task(
    """
    1. Read the latest news about AI from arxiv.org
    2. Select the top 5 articles based on impact
    3. Summarize key points of each article
    """,
    streaming=True
)
print(result)
```

### 2. Multi-Step Research Task

```python
# Comprehensive research task
result = agent.solve_task(
    """
    1. Research emerging AI technologies
    2. Compare different machine learning approaches
    3. Create a summary report with pros and cons
    """,
    streaming=True
)
print(result)
```

### 3. Content Summarization

```python
# Summarize complex documents
result = agent.solve_task(
    """
    1. Read a long research paper
    2. Extract key findings
    3. Write an executive summary
    """,
    streaming=True
)
print(result)
```

## Event Monitoring

Track task execution and debug complex workflows:

```python
# Configure event listeners
agent.event_emitter.on(
    event=[
        "task_complete",
        "task_think_start",
        "task_think_end",
        "tool_execution_start",
        "tool_execution_end",
    ],
    listener=console_print_events
)

# Optional token streaming
agent.event_emitter.on(
    event=["stream_chunk"],
    listener=console_print_token
)
```

## Best Practices

- Break complex tasks into clear steps
- Use streaming for long-running tasks
- Leverage multiple tools
- Monitor task execution
- Validate results

!!! tip "Intelligent Automation"
    Combine tools creatively to solve complex, multi-step tasks.

## Complete Code Example

```python
import os
from quantalogic import Agent
from quantalogic.console_print_events import console_print_events
from quantalogic.console_print_token import console_print_token
from quantalogic.tools import (
    LLMTool, 
    MarkitdownTool
)

# Set API key
os.environ["OPENAI_API_KEY"] = "your-openai-key"

# Initialize agent with task automation tools
MODEL_NAME = "gpt-4o-mini"
agent = Agent(
    model_name=MODEL_NAME,
    tools=[
        MarkitdownTool(),
        LLMTool(
            model_name=MODEL_NAME, 
            on_token=console_print_token
        ),
    ],
)

# Configure event monitoring
agent.event_emitter.on(
    event=[
        "task_complete",
        "task_think_start",
        "task_think_end",
        "tool_execution_start",
        "tool_execution_end",
    ],
    listener=console_print_events
)

# Execute a complex task
result = agent.solve_task(
    """
    1. Read the latest news about AI from arxiv.org
    2. Select the top 5 articles based on impact
    3. Summarize key points of each article
    """,
    streaming=True
)
print(result)
```

!!! warning "Task Complexity"
    Start with simple tasks and gradually increase complexity.
