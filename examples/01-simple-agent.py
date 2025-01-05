import os

from quantalogic import Agent

# Veirify that is set DEEPSEEK_API_KEY

if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

# For openai model use gpt-4o or gpt-4o-mini
# And set OPENAI_API_KEY

# For bedrock model use bedrock/amazon.nova-pro-v1:0 
# And set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY

# For mistral model use mistral/mistral-large-2411
# And set MISTRAL_API_KEY

# Initialize agent with default configuration
agent = Agent(model_name="deepseek/deepseek-chat")

# Execute a task
result = agent.solve_task(
    "Create a Python function that calculates the Fibonacci sequence"
)
print(result)
