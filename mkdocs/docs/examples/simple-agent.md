# Creating a Simple Agent

This guide demonstrates how to create and use a basic QuantaLogic agent. We'll walk through setting up the agent and solving a coding task.

## Prerequisites

- Python 3.12 or later
- QuantaLogic library installed
- API key for your chosen LLM provider

## Environment Setup

Before creating an agent, ensure you have the necessary API keys set:

```python
import os

# Set API keys for different LLM providers
os.environ["DEEPSEEK_API_KEY"] = "your-deepseek-key"
os.environ["OPENAI_API_KEY"] = "your-openai-key"  # Optional
os.environ["MISTRAL_API_KEY"] = "your-mistral-key"  # Optional
```

!!! warning "API Key Configuration"
    - Always set API keys as environment variables
    - Never hardcode sensitive credentials in your script
    - Supports multiple LLM providers for flexibility

## Creating an Agent

Initialize an agent with your preferred language model:

```python
from quantalogic import Agent

# DeepSeek model (default)
agent = Agent(model_name="deepseek/deepseek-chat")

# Alternative model configurations
# agent = Agent(model_name="openai/gpt-4")
# agent = Agent(model_name="mistral/mistral-large-2411")
# agent = Agent(model_name="bedrock/amazon.nova-pro-v1:0")  # Requires AWS credentials
```

## Solving a Task

Use the agent to generate code or solve programming challenges:

```python
# Generate a Fibonacci sequence function
result = agent.solve_task("Create a Python function that calculates the Fibonacci sequence")
print(result)
```

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

## Best Practices

- Choose models based on your specific requirements
- Validate API keys before initializing the agent
- Handle potential errors gracefully
- Experiment with different models to find the best fit

## Supported LLM Providers

- DeepSeek
- OpenAI
- Mistral AI
- AWS Bedrock (enterprise)

!!! tip "Flexibility"
    The QuantaLogic Agent supports multiple language models, giving you the freedom to choose the best AI for your task.

## Complete Code

Here's the complete example:

```python
import os
from quantalogic import Agent

# Set API keys for different LLM providers
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

# Initialize agent
agent = Agent(model_name="deepseek/deepseek-chat")

# Solve a task
result = agent.solve_task("Create a Python function that calculates the Fibonacci sequence")
print(result)
```

!!! tip "Best Practice"
    Always verify API keys are set before creating the agent to avoid runtime errors.
