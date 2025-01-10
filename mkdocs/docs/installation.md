# Installation Guide

This guide will help you get QuantaLogic up and running quickly. Choose the installation method that best suits your needs.

## System Requirements

- Python 3.12 or later

## Quick Install (Recommended)

```bash
pip install quantalogic
```

That's it! Skip to [Verify Installation](#verify-installation) to confirm everything works.

## Detailed Installation Options

### Option 1: Using pip (Simple)

```bash
# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install QuantaLogic
pip install quantalogic
```

### Option 2: Using Poetry (Development)

```bash
# Install Poetry if you haven't already
curl -sSL https://install.python-poetry.org | python3 -

# Clone and install
git clone https://github.com/quantalogic/quantalogic.git
cd quantalogic
poetry install
```

### Option 3: Using pipx (Isolated)

```bash
# Install pipx
python -m pip install --user pipx
pipx ensurepath

# Install QuantaLogic
pipx install quantalogic
```

## Required Configuration

### 1. LLM API Keys

Choose at least one LLM provider and set its API key:

```bash
# DeepSeek (Recommended)
export DEEPSEEK_API_KEY="your-api-key"

# Or OpenAI
export OPENAI_API_KEY="your-api-key"

# Or Anthropic
export ANTHROPIC_API_KEY="your-api-key"
```

!!! tip "Secure Key Storage"
    Never commit API keys to version control. Consider using:
    - Environment variables
    - `.env` files (add to .gitignore)
    - Your OS's keychain

## Optional Components

### Docker Setup (For Code Execution)

1. Install Docker from [docker.com](https://www.docker.com/get-started)
2. Start the Docker daemon
3. Verify with:
   ```bash
   docker run hello-world
   ```

## Verify Installation

Run these commands to verify your setup:

```bash
# Check version
quantalogic --version

```

## Troubleshooting

### Common Issues

1. **Python Version Error**
   ```bash
   python --version  # Should be 3.12 or later
   ```



### Error Messages

| Error | Solution |
|-------|----------|
| `ModuleNotFoundError` | Re-run `pip install quantalogic` |
| `ImportError` | Check Python version (3.12+) |
| `API key not found` | Set environment variables |

