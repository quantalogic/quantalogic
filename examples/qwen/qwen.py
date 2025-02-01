#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "openai",
# ]
# ///

import os

from openai import OpenAI

# Replace this with your actual DASHSCOPE_API_KEY
# You can obtain this key from the DashScope console
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

# Model name for the Qwen API
# Available models: https://www.alibabacloud.com/help/en/model-studio/getting-started/models
MODEL_NAME = "qwen-plus"

if not DASHSCOPE_API_KEY:
    raise ValueError("DASHSCOPE_API_KEY is not set in the environment variables.")


# Initialize OpenAI client with DashScope configuration
client = OpenAI(
    # If the environment variable is not configured, replace the following line with: api_key="sk-xxx",
    api_key=os.getenv("DASHSCOPE_API_KEY"), 
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",  # DashScope API endpoint
)
completion = client.chat.completions.create(
    model=MODEL_NAME, # Model list: https://www.alibabacloud.com/help/en/model-studio/getting-started/models
    messages=[
        {'role': 'system', 'content': 'You are a helpful assistant.'},
        {'role': 'user', 'content': 'Who are you?'}],
    )
    
print(completion.model_dump_json())