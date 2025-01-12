# Command Line Interface (CLI)

QuantaLogic provides a powerful command-line interface for running AI agents and executing tasks directly from your terminal.

## Installation

You can install QuantaLogic using any of these methods:

```bash
# Via pip
pip install quantalogic

# Via pipx (recommended for CLI tools)
pipx install quantalogic

# From source
git clone https://github.com/quantalogic/quantalogic.git
cd quantalogic
python -m venv .venv
source ./venv/bin/activate 
poetry install
```

## Basic Usage

```bash
quantalogic [OPTIONS] COMMAND [ARGS]...
```

## Global Options

| Option | Description | Default |
|--------|-------------|---------|
| `--version` | Show version information | - |
| `--model-name` | Specify the model (litellm format, e.g., "openrouter/deepseek/deepseek-chat") | - |
| `--log` | Set logging level (info/debug/warning) | `info` |
| `--verbose` | Enable verbose output | `False` |
| `--mode` | Agent mode (code/search/full) | `code` |
| `--vision-model-name` | Specify the vision model (litellm format, e.g., "openrouter/A/gpt-4o-mini") | - |
| `--max-iterations` | Maximum iterations for task solving | `30` |
| `--max-tokens-working-memory` | Maximum tokens to keep in working memory | `None` |
| `--compact-every-n-iteration` | Compact memory every N iterations | `None` |
| `--help` | Show help message and exit | - |

### Available Modes

- `code`: Full coding capabilities with advanced reasoning
- `basic`: Simple task execution without additional features
- `interpreter`: Interactive REPL mode for dynamic interaction
- `full`: All features enabled including advanced tools
- `code-basic`: Basic coding features without advanced capabilities
- `search`: Web search capabilities for information gathering
- `search-full`: Enhanced search features with comprehensive analysis

## Commands

### task

Execute a task with the QuantaLogic AI Assistant:

```bash
quantalogic task [OPTIONS] [TASK]
```

#### Task-Specific Options

| Option | Description | Default |
|--------|-------------|---------|
| `--file` | Path to task file | - |
| `--model-name` | Specify the model (litellm format) | - |
| `--verbose` | Enable verbose output | `False` |
| `--mode` | Agent mode (code/search/full) | - |
| `--log` | Set logging level (info/debug/warning) | - |
| `--vision-model-name` | Specify the vision model (litellm format) | - |
| `--max-iterations` | Maximum iterations for task solving | `30` |
| `--no-stream` | Disable streaming output | `False` |
| `--help` | Show help message and exit | - |

## Examples

### Basic Task Execution

```bash
# Simple code generation
quantalogic --mode code "Create a Python function that calculates factorial"

# Using a task file
quantalogic task --file path/to/task.txt

# Interactive mode with custom model
quantalogic --mode interpreter --model-name "openai/gpt-4" "Explain quantum computing"

# Debugging with verbose output and no streaming
quantalogic task --log debug --verbose --no-stream "Debug this Python script"
```

## Best Practices

1. **Start Simple**: 
   - Begin with `--mode basic` for straightforward tasks
   - Gradually increase complexity as needed

2. **Debugging**:
   - Use `--log debug` for troubleshooting
   - Enable `--verbose` for detailed execution information
   - Disable streaming with `--no-stream` when needed for clearer output

3. **Model Selection**:
   - Choose models based on task complexity
   - Consider using specialized models for specific tasks (e.g., vision models for image analysis)

4. **Task Management**:
   - Use task files for complex or repetitive tasks
   - Adjust `--max-iterations` based on task complexity
   - Break down complex tasks into smaller subtasks

## Security Considerations

- API keys should be set via environment variables (litellm will use env vars by default)
- Code execution is sandboxed by default for security
- Always review generated code before execution
- Use appropriate permissions when working with file system operations

## Error Handling

- The CLI provides detailed error messages for common issues
- Check logs with `--log debug` for troubleshooting
- Use `--verbose` for additional context when errors occur

## Requirements

- Python 3.12+
- Docker (optional, required for code execution tools)
- Internet connection for model API access
