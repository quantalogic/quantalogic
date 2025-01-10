# Quick Start

## Basic Usage

### Python API

```python
from quantalogic import Agent

# Initialize the agent
agent = Agent(model_name="openai/gpt-4")

# Execute a task
result = agent.solve_task("Create a Python function that calculates the Fibonacci sequence")
print(result)
```

### CLI Usage

```bash
# Basic task execution
quantalogic task "Create a Python script to analyze stock market trends"

# Specify model and mode
quantalogic --model-name "openrouter/deepseek-chat" \
            --mode code \
            task "Develop a web scraping utility"
```

## CLI Options

| Option | Description | Example |
|--------|-------------|---------|
| `--model-name` | Specify LLM (LiteLLM format) | `openrouter/deepseek-chat` |
| `--mode` | Agent operation mode | `code`, `search`, `full` |
| `--max-iterations` | Task solving iterations | `30` (default) |
| `--verbose` | Enable detailed output | |

## Example Scenarios

### Code Generation
```bash
quantalogic task "Write a Flask API for a todo list app"
```

### Web Search & Analysis
```bash
quantalogic --mode search task "Research latest AI trends in healthcare"
```

## Next Steps
- [Components Overview](/components/react)
- [CLI Reference](/cli)
