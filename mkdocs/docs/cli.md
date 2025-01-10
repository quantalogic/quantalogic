# CLI Reference

## Usage

```bash
quantalogic [OPTIONS] COMMAND [ARGS]...
```

## Options

| Option | Description | Example |
|--------|-------------|---------|
| `--model-name` | Specify LLM model | `openrouter/deepseek/deepseek-chat` |
| `--mode` | Agent operation mode | `code`, `search`, `full` |
| `--max-iterations` | Task solving iterations | `30` (default) |
| `--verbose` | Enable detailed output | |

## Examples

### Code Generation
```bash
quantalogic task "Create a Flask API for a todo list"
```

### Web Search
```bash
quantalogic --mode search task "Research AI trends in healthcare"
```
