# Development Setup

## Prerequisites

- Python 3.12+
- Poetry
- Docker (optional)

## Installation Steps

```bash
# Clone the repository
git clone https://github.com/quantalogic/quantalogic.git
cd quantalogic

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
poetry install --with dev

# Run tests
poetry run pytest
```

## Local Development

```bash
# Start development server
poetry run quantalogic

# Run documentation
poetry run docs-serve
```
