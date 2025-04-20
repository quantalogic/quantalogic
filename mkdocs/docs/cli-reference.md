# Command Line Interface (CLI)

QuantaLogic’s CLI provides a powerful interface for running AI agents in ReAct, CodeAct, Flow, and Chat modes directly from your terminal.

---

## Installation

```bash
# Via pip
pip install quantalogic

# Via pipx
pipx install quantalogic

# From source
git clone https://github.com/quantalogic/quantalogic.git
cd quantalogic
python -m venv .venv
source .venv/bin/activate
poetry install
```

See [Installation Guide](installation.md).

---

## Basic Usage

```bash
quantalogic [OPTIONS] COMMAND [ARGS]...
```

### Global Options

| Option                    | Description                              | Default       |
|---------------------------|------------------------------------------|---------------|
| `--version`               | Show version information                 | -             |
| `--model-name`            | Specify LLM (LiteLLM format)             | -             |
| `--log`                   | Set logging level (info/debug/warning)   | `info`        |
| `--verbose`               | Enable verbose output                    | `False`       |
| `--mode`                  | Agent mode (react/codeact/flow/chat)     | `react`       |
| `--vision-model-name`     | Specify vision model                     | -             |
| `--max-iterations`        | Max iterations for task solving          | `30`          |
| `--max-tokens-working-memory` | Max tokens in working memory         | `None`        |
| `--compact-every-n-iteration` | Compact memory every N iterations     | `None`        |
| `--help`                  | Show help message and exit               | -             |

**Available Modes**:
- `react`: General reasoning and tool use.
- `codeact`: Code-driven automation.
- `flow`: Structured workflow execution.
- `chat`: Conversational interactions.
- `interpreter`: Interactive REPL mode.

---

## Commands

### task
Run a task in ReAct, CodeAct, or Flow mode:
```bash
quantalogic task [OPTIONS] [TASK]
```

#### Options
| Option              | Description                              | Default |
|---------------------|------------------------------------------|---------|
| `--file`            | Path to task file                        | -       |
| `--model-name`      | Specify LLM                              | -       |
| `--mode`            | Agent mode                               | -       |
| `--verbose`         | Enable verbose output                    | `False` |
| `--log`             | Set logging level                        | -       |
| `--no-stream`       | Disable streaming output                 | `False` |

### chat
Start a conversation:
```bash
quantalogic chat [OPTIONS] [MESSAGE]
```

#### Options
| Option              | Description                              | Default |
|---------------------|------------------------------------------|---------|
| `--persona`         | Set chat persona                         | -       |
| `--model-name`      | Specify LLM                              | -       |
| `--verbose`         | Enable verbose output                    | `False` |

### list-models
List available LLMs:
```bash
quantalogic list-models
```

### CodeAct-Specific Commands
```bash
quantalogic_codeact [OPTIONS] COMMAND [ARGS]...
```

- **shell**: Start interactive shell.
  ```bash
  quantalogic_codeact shell
  ```
- **task**: Run a CodeAct task.
  ```bash
  quantalogic_codeact task "Calculate sqrt(16)"
  ```
- **list-toolboxes**: List installed toolboxes.
  ```bash
  quantalogic_codeact list-toolboxes
  ```

---

## Examples

### ReAct Task
```bash
quantalogic task --mode react "Create a Python function to validate emails"
```

### CodeAct Task
```bash
quantalogic_codeact task "Calculate the 6th Fibonacci number" --streaming
```

### Flow Workflow
```bash
quantalogic task --mode flow --file workflow.yaml
```

### Chat Interaction
```bash
quantalogic chat --persona "AI expert" "Explain quantum computing"
```

---

## Best Practices

- **Start Simple**: Use `--mode react` or `chat` for quick tasks.
- **Debugging**: Enable `--log debug` and `--verbose` for troubleshooting.
- **Model Selection**: Choose models based on task needs (e.g., `gpt-4o` for reasoning).
- **Task Files**: Use `--file` for complex tasks to ensure repeatability.

---

## Security Considerations

- Store API keys in `.env` files, not in scripts.
- Review generated code before execution (especially in CodeAct).
- Ensure Docker is configured securely for code execution tools.

---

## Requirements
- Python 3.12+
- Docker (optional, for CodeAct/ReAct)
- Internet connection for LLM APIs

See [Troubleshooting Guide](troubleshooting.md) for help with issues.