# Quick Start

Get up and running with QuantaLogic in minutes! This guide covers basic usage for **ReAct**, **CodeAct**, **Flow**, and **Chat** modes using the CLI and Python API.

---

## Installation

1. **Install QuantaLogic**:
   ```bash
   pip install quantalogic
   ```

2. **Set API Keys**:
   ```bash
   export DEEPSEEK_API_KEY="your-api-key"
   ```
   Or use a `.env` file:
   ```env
   DEEPSEEK_API_KEY=your-api-key
   ```

See [Installation Guide](installation.md) for details.

---

## Basic Usage

### Python API

#### ReAct/CodeAct Example
Solve a task with an agent:
```python
import os
from quantalogic import Agent

if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY is not set")

agent = Agent(model_name="deepseek/deepseek-chat")
result = agent.solve_task("Calculate the 6th Fibonacci number")
print(result)
# Output: A Python function or direct result (e.g., 8)
```

#### Flow Example
Create a simple workflow:
```python
from quantalogic_flow import Workflow, Nodes
import asyncio

@Nodes.define(output="processed")
def uppercase(text: str) -> str:
    return text.upper()

workflow = Workflow("uppercase").build()
result = asyncio.run(workflow.run({"text": "hello world"}))
print(result["processed"])  # "HELLO WORLD"
```

#### Chat Example
Start a conversation:
```python
from quantalogic import Agent, DuckDuckGoSearchTool

agent = Agent(
    model_name="gpt-4o-mini",
    chat_system_prompt="You’re a curious explorer",
    tools=[DuckDuckGoSearchTool()]
)
response = agent.chat("What’s new in quantum computing?")
print(response)
```

### CLI Usage

#### ReAct/CodeAct Task
```bash
quantalogic task "Write a Python script to reverse a string"
# Output: A string-reversal script
```

#### CodeAct-Specific Task
```bash
quantalogic_codeact task "Calculate the square root of 16" --model gemini/gemini-2.0-flash
# Output: 4
```

#### Chat Mode
```bash
quantalogic chat --persona "AI expert" "What’s the latest in machine learning?"
# Output: A detailed response, possibly with search results
```

#### Flow Task
```bash
quantalogic task --mode flow "Run a workflow from simple_workflow.yaml"
```

---

## CLI Options

| Option              | Description                              | Example                              |
|---------------------|------------------------------------------|--------------------------------------|
| `--model-name`      | Specify LLM (LiteLLM format)             | `deepseek/deepseek-chat`             |
| `--mode`            | Operation mode                           | `react`, `codeact`, `flow`, `chat`   |
| `--max-iterations`  | Max task-solving iterations              | `30`                                 |
| `--verbose`         | Enable detailed output                   | `--verbose`                          |
| `--persona`         | Set chat persona                         | `"Cosmic guide"`                     |

**Available Modes**:
- `react`: General reasoning and tool use.
- `codeact`: Code-driven task automation.
- `flow`: Structured workflow execution.
- `chat`: Conversational interactions.
- `interpreter`: Interactive REPL for dynamic tasks.

See [CLI Reference](cli-reference.md) for all options.

---

## Example Scenarios

### Code Generation (CodeAct)
```bash
quantalogic_codeact task "Write a Flask API for a todo list app"
```

### Workflow Automation (Flow)
```bash
quantalogic task --mode flow "Generate a report from data.yaml"
```

### Conversational Research (Chat)
```bash
quantalogic chat "Research AI trends in healthcare"
```

---

## Troubleshooting

- **API Key Error**: Ensure `DEEPSEEK_API_KEY` or other keys are set in `.env` or environment variables.
- **Model Unavailable**: Try `deepseek/deepseek-chat` if region-restricted models (e.g., Anthropic) fail.
- **Docker Issues**: Verify Docker is running for CodeAct/ReAct code execution tools.

See [Troubleshooting Guide](troubleshooting.md) for solutions.

---

## Next Steps
- Explore [Core Concepts](core-concepts.md)
- Learn about [CodeAct](codeact.md) and [Flow](quantalogic-flow.md)
- Try [Examples](examples/simple-agent.md)