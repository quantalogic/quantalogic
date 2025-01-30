#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "openai",
#     "loguru"
# ]
# ///

import os
from typing import Dict, List

from loguru import logger
from openai import OpenAI, OpenAIError


def create_qwen_client() -> OpenAI:
    """
    Create and return an OpenAI client configured for Qwen.
    
    Returns:
        OpenAI: Configured client for Qwen API
    
    Raises:
        ValueError: If API key is not set
    """
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("DASHSCOPE_API_KEY is not set in the environment variables.")
    
    return OpenAI(
        api_key=api_key,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )

def generate_chat_completion(
    client: OpenAI, 
    messages: List[Dict[str, str]], 
    model: str = "qwen-plus"
) -> None:
    """
    Generate and stream a chat completion.
    
    Args:
        client (OpenAI): Configured OpenAI client
        messages (List[Dict]): List of message dictionaries
        model (str, optional): Model name. Defaults to "qwen-plus".
    """
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True}
        )
        
        logger.info(f"Generating completion using {model}")
        
        for chunk in completion:
            # Safely handle chunk processing
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta and hasattr(delta, 'content') and delta.content:
                    print(delta.content, end="", flush=True)
        
        logger.success("Completion generation finished")
    
    except OpenAIError as e:
        logger.error(f"API error occurred: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.exception("Error details:")

def main():
    """Main function to demonstrate Qwen chat completion."""
    try:
        client = create_qwen_client()
        messages = [
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': 'Who are you?'}
        ]
        generate_chat_completion(client, messages)

        print("\n")
    
    except Exception as e:
        logger.exception("Failed to run Qwen chat completion")

if __name__ == "__main__":
    main()