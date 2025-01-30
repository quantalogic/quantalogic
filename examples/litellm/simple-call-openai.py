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

print(os.environ["OPENROUTER_API_KEY"])
response = completion(
    model="openrouter/openai/gpt-4o-mini",
    messages=[{"role": "user", "content": "hello from litellm"}],
)
print(response)
