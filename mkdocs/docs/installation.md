# Installation

This guide will help you install QuantaLogic and set up your development environment.

## Prerequisites

### Required
- Python 3.12 or later
- pip (Python package installer)
- Git (for source installation)

### Optional but Recommended
- Docker (for secure code execution)
- Poetry (for development)
- pipx (for isolated installations)

## Installation Methods

### 1. Via pip (Recommended)

The simplest way to install QuantaLogic:

```bash
pip install quantalogic
```

For a specific version:
```bash
pip install quantalogic==1.0.0
```

### 2. From Source (Development)

Clone and install from the repository:

```bash
# Clone the repository
git clone https://github.com/quantalogic/quantalogic.git
cd quantalogic

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies with Poetry
poetry install
```

### 3. Using pipx (Isolated)

Install in an isolated environment:

```bash
# Install pipx if you haven't already
python -m pip install --user pipx
pipx ensurepath

# Install QuantaLogic
pipx install quantalogic
```

## Configuration

### 1. API Keys

Set up your LLM provider API keys:

```bash
# DeepSeek (default)
export DEEPSEEK_API_KEY="your-api-key"

# OpenAI (optional)
export OPENAI_API_KEY="your-api-key"

# Anthropic (optional)
export ANTHROPIC_API_KEY="your-api-key"
```

!!! tip "API Keys"
    Store API keys in your environment or use a secure key management system.

### 2. Docker Setup (Optional)

If you plan to use code execution tools:

1. Install Docker from [docker.com](https://www.docker.com/get-started)
2. Verify installation:
```bash
docker --version
```

## Verification

Verify your installation:

```bash
# Check version
quantalogic --version

# Run a simple test
quantalogic --mode basic "Hello, World!"
```

## Troubleshooting

### Common Issues

1. **Python Version Error**
```bash
# Check Python version
python --version

# If needed, upgrade Python
# On macOS/Linux:
brew install python@3.12  # or your package manager
# On Windows: Download from python.org
```

2. **Virtual Environment Issues**
```bash
# Remove and recreate venv
rm -rf .venv
python -m venv .venv
```

3. **Docker Permission Error**
```bash
# Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in
```

### Getting Help

If you encounter issues:

1. Check our [Troubleshooting Guide](troubleshooting.md)
2. Search [GitHub Issues](https://github.com/quantalogic/quantalogic/issues)
3. Join our [Community Discord](https://discord.gg/quantalogic)

## Next Steps

- Follow the [Quick Start Guide](quickstart.md) to create your first agent
- Learn about [Core Concepts](core-concepts.md)
- Try our [Examples](examples/simple-agent.md)
- Read the [CLI Reference](cli.md)

## Development Setup

For contributors:

1. Fork the repository
2. Install development dependencies:
```bash
poetry install --with dev
```
3. Set up pre-commit hooks:
```bash
pre-commit install
```

See our [Contributing Guide](dev/contributing.md) for more details.
