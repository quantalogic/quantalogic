# Command Line Interface (CLI)

The QuantaLogic CLI provides powerful command-line capabilities for running AI agents directly from your terminal.

## Basic Usage

```bash
quantalogic [OPTIONS] COMMAND [ARGS]...
```

## Global Options

| Option | Description | Default |
|--------|-------------|---------|
| `--version` | Show version information | - |
| `--model-name` | Specify the text model (litellm format) | `openrouter/deepseek-chat` |
| `--vision-model-name` | Specify the vision model (litellm format) | `openrouter/A/gpt-4o-mini` |
| `--log` | Set logging level (info/debug/warning) | `info` |
| `--verbose` | Enable verbose output | `False` |
| `--max-iterations` | Maximum iterations for task solving | `30` |
| `--mode` | Agent mode | `code` |

### Available Modes

- `code`: Full coding capabilities
- `basic`: Simple task execution
- `interpreter`: Interactive REPL mode
- `full`: All features enabled
- `code-basic`: Basic coding features
- `search`: Web search capabilities
- `search-full`: Enhanced search features

## Examples

### Basic Code Generation

```bash
quantalogic --mode code "Create a Python function that calculates factorial"
```

### Using a Specific Model

```bash
quantalogic --model-name "openai/gpt-4" --mode full "Analyze this dataset"
```

### Debug Mode with Verbose Logging

```bash
quantalogic --log debug --verbose --mode code "Debug this Python script"
```



## Best Practices

1. **Start Simple**: Begin with `--mode basic` for simple tasks
2. **Debug Issues**: Use `--log debug` when troubleshooting
3. **Model Selection**: Choose models based on task complexity
4. **Iteration Control**: Adjust `--max-iterations` for complex tasks

## Security Notes

- API keys should be set via environment variables (litellm will use env vars by default)
- Code execution is sandboxed by default
- Review generated code before execution
