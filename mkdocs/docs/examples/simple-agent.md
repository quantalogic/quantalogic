# Creating a Simple Agent

This guide shows you how to create and use a basic QuantaLogic agent. We'll walk through setting up the agent and using it to solve a coding task.

## Prerequisites

- Python 3.12 or later
- QuantaLogic installed
- API key for your chosen LLM provider

## Basic Setup

First, import the necessary modules and set up your environment:

```python
import os
from quantalogic import Agent

# Set up your API key
os.environ["DEEPSEEK_API_KEY"] = "your-api-key"  # Replace with your actual key
```

!!! warning "API Key Required"
    Make sure you have the appropriate API key set in your environment variables before running the code.

## Creating the Agent

Create an agent with your preferred LLM:

```python
# Initialize with DeepSeek's model
agent = Agent(model_name="deepseek/deepseek-chat")
```

### Available Models

You can use different LLM providers:

```python
# OpenAI
agent = Agent(model_name="openai/gpt-4")  # Requires OPENAI_API_KEY

# AWS Bedrock
agent = Agent(model_name="bedrock/amazon.nova-pro-v1:0")  # Requires AWS credentials

# Mistral AI
agent = Agent(model_name="mistral/mistral-large-2411")  # Requires MISTRAL_API_KEY
```

## Solving Tasks

Ask your agent to solve a task:

```python
result = agent.solve_task(
    "Create a Python function that calculates the Fibonacci sequence"
)
print(result)
```

The agent will:
1. Understand the task requirements
2. Generate appropriate code
3. Test the solution
4. Return the working code

## Example Output

Here's what you might see:

```python
def fibonacci(n: int) -> list[int]:
    """Generate Fibonacci sequence up to n numbers.
    
    Args:
        n: Number of Fibonacci numbers to generate
        
    Returns:
        List of Fibonacci numbers
    """
    if n <= 0:
        return []
    elif n == 1:
        return [0]
        
    sequence = [0, 1]
    while len(sequence) < n:
        sequence.append(sequence[-1] + sequence[-2])
        
    return sequence

# Example usage
print(fibonacci(10))  # [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
```

## Next Steps

- Learn about [Event Monitoring](event-monitoring.md)
- Explore [Code Generation](code-generation.md)
- Try [Task Automation](task-automation.md)

## Complete Code

Here's the complete example:

```python
import os
from quantalogic import Agent

# Set up API key
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

# Initialize agent
agent = Agent(model_name="deepseek/deepseek-chat")

# Solve a task
result = agent.solve_task(
    "Create a Python function that calculates the Fibonacci sequence"
)
print(result)
```

!!! tip "Best Practice"
    Always verify API keys are set before creating the agent to avoid runtime errors.
