#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "quantalogic>=0.50.13",
#     "pathspec",
# ]
# ///

import os

from quantalogic import Agent

# Veirify that is set DEEPSEEK_API_KEY

MODEL_NAME = "deepseek/deepseek-chat"
#MODEL_NAME = "ovh/DeepSeek-R1-Distill-Llama-70B"

if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

# OpenAI model options (gpt-4o or gpt-4o-mini)
# Requires OPENAI_API_KEY environment variable
# Used when preferring OpenAI's models over DeepSeek

# AWS Bedrock model configuration (bedrock/amazon.nova-pro-v1:0)
# Requires AWS credentials for Amazon's AI service
# Alternative option for enterprise-grade AI models

# Mistral AI model configuration (mistral/mistral-large-2411)
# Requires MISTRAL_API_KEY for Mistral's open-source models
# Good choice for open-source AI model integration

# Initialize the AI agent with default configuration
# Using DeepSeek as the primary model for this example
# Configuration can be customized for different use cases
agent = Agent(model_name=MODEL_NAME)

# Execute a sample task to demonstrate agent capabilities
# This example creates a Fibonacci sequence function
# Shows how the agent can generate code solutions

# Define a simple task to create a Fibonacci sequence function
fibonacci_task = "Create a Python function that calculates the Fibonacci sequence"

# The streaming parameter controls whether responses are generated incrementally or all at once
# With our fix, both streaming=True and streaming=False should work correctly
streaming_enabled = False  # Try with both True and False

# Execute the agent with the task
result = agent.solve_task(fibonacci_task, streaming=streaming_enabled)
print(result)
