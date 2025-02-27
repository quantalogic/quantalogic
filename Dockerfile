# Use Python 3.12 slim as base image
FROM python:3.12-slim AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_VERSION=1.8.5 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

# Add Poetry to PATH
ENV PATH="/root/.local/bin:$PATH"

# Install system dependencies and pipx
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        python3-venv \
        git \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --user pipx \
    && python -m pipx ensurepath

# Install Poetry using pipx
RUN pipx install poetry==${POETRY_VERSION}

# Set working directory
WORKDIR /app

# Copy only dependencies files first
COPY pyproject.toml poetry.lock ./

# Install dependencies only
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-cache --no-interaction --no-ansi

# Copy only the necessary application files
COPY quantalogic ./quantalogic
COPY examples ./examples
COPY README.md ./
COPY .env ./

# Install the project itself
RUN poetry install --only main --no-cache --no-interaction --no-ansi

# Expose the port the app runs on
EXPOSE 8082

# Command to run the application
CMD ["poetry", "run", "uvicorn", "examples.integration-with-fastapi-nextjs.agent_server:app", "--host", "0.0.0.0", "--port", "8082", "--reload"]