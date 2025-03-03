#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "litellm>=1.59.8",
# ]
# ///

import os

import litellm
from litellm import completion

litellm.set_verbose = True

print(os.environ["DEEPSEEK_API_KEY"])
response = completion(
    model="deepseek/deepseek-chat",
    messages=[{"role": "user", "content": "hello from litellm"}],
)
print(response)
