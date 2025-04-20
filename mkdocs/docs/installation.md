# Installation Guide

This guide helps you install and configure QuantaLogic for **ReAct**, **CodeAct**, **Flow**, and **Chat** modes.

> **Important**: QuantaLogic requires **Python 3.12+** (3.10+ for Flow). Check with:
> ```bash
> python --version
> ```

---

## Installation Options

### Option 1: pip (Recommended)
```bash
pip install quantalogic
```

### Option 2: pipx (Isolated)
```bash
pipx install quantalogic
```

### Option 3: From Source (Development)
```bash
git clone https://github.com/quantalogic/quantalogic.git
cd quantalogic
python -m venv .venv
source .venv/bin/activate
poetry install
```

---

## Required Configuration

### LLM API Keys

Set at least one LLM provider’s API key:
```bash
# Recommended
export DEEPSEEK_API_KEY="your-api-key"

# Optional
export OPENAI_API_KEY="your-api-key"
export ANTHROPIC_API_KEY="your-api-key"
```

**Tip**: Use a `.env` file for security:
```env
DEEPSEEK_API_KEY=your-api-key
OPENAI_API_KEY=your-api-key
ANTHROPIC_API_KEY=your-api-key
```
Add `.env` to `.gitignore`.

**Warning**: Some models (e.g., Anthropic) may have regional restrictions. Use `deepseek/deepseek-chat` if issues arise.

---

## Optional Components

### Docker (CodeAct/ReAct)
Required for code execution tools (e.g., `PythonTool`):
1. Install Docker from [docker.com](https://www.docker.com/get-started).
2. Start the Docker daemon.
3. Verify:
   ```bash
   docker run hello-world
   ```

### Flow Dependencies
For Flow mode, install:
```bash
pip install quantalogic-flow
```

---

## Verify Installation

```bash
# Check QuantaLogic version
quantalogic --version

# Verify CodeAct shell
quantalogic_codeact shell
```

---

## Troubleshooting

| Issue                    | Solution                                      |
|--------------------------|-----------------------------------------------|
| `ModuleNotFoundError`    | Re-run `pip install quantalogic`             |
| `API key not found`      | Set keys in `.env` or environment variables  |
| `Docker not running`     | Start Docker daemon and verify with `docker ps` |
| `Model access error`     | Use `deepseek/deepseek-chat`                 |

See [Troubleshooting Guide](troubleshooting.md).

---

## Next Steps
- Try the [Quick Start](quickstart.md)
- Explore [CodeAct](codeact.md) and [Flow](quantalogic-flow.md)
- Learn [Best Practices](best-practices/agent-design.md)