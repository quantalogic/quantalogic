# Logging Configuration

## Overview

Quantalogic CodeAct uses a configurable logging system that provides clean output for end-users while still supporting detailed debugging when needed.

## Default Behavior

By default, the CLI uses **ERROR** level logging to provide the cleanest possible output for end-users. This means:

- Only actual errors are displayed
- No debug or info messages clutter the output
- External dependency logging is also suppressed

## Customizing Log Levels

### Using the Shell

You can change the log level interactively in the shell:

```bash
/loglevel DEBUG   # Show detailed debug information
/loglevel INFO    # Show informational messages
/loglevel WARNING # Show warnings and errors
/loglevel ERROR   # Show only errors (default)
```

### Using the CLI

Set the log level via command line:

```bash
python -m quantalogic_codeact.cli task "Calculate 2+2" --loglevel DEBUG
```

### Via Configuration File

Add to your `~/.quantalogic/config.yaml`:

```yaml
log_level: "INFO"  # or DEBUG, WARNING, ERROR, CRITICAL
```

### Via Environment Variable

Set the environment variable before running commands:

```bash
export LOGURU_LEVEL=DEBUG
python -m quantalogic_codeact.cli --help
```

## Log Level Details

| Level | Description | What You'll See |
|-------|-------------|-----------------|
| **ERROR** | Default - Only errors | Clean output, errors only |
| **WARNING** | Warnings and errors | Important warnings + errors |
| **INFO** | General information | Toolbox loading, agent status |
| **DEBUG** | Detailed debugging | Full execution traces, tool details |

## External Dependencies

The logging system automatically manages verbose external libraries:

- **LiteLLM**: HTTP debugging suppressed by default
- **External Toolboxes**: Only warnings/errors shown
- **HTTP Libraries**: Debug output filtered

## Troubleshooting

If you need to debug issues:

1. **Enable DEBUG logging**: Use `/loglevel DEBUG` in the shell
2. **Check specific components**: Look for error patterns in debug output
3. **Reset to clean output**: Use `/loglevel ERROR` to return to clean mode

## Implementation Notes

The logging configuration is implemented in `quantalogic_codeact/utils/logging_config.py` and automatically:

- Intercepts standard library logging
- Configures loguru with appropriate formatting
- Silences known verbose external libraries
- Respects user configuration preferences

This ensures a professional, clean user experience while maintaining full debugging capabilities when needed.
