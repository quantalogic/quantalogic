# LiteLLM Guide

LiteLLM provides a unified interface to interact with various Large Language Models (LLMs) using a consistent API similar to OpenAI's interface.

## Installation

```bash
pip install litellm
```

## Basic Usage

### 1. Simple Completion

```python
from litellm import completion

# Basic completion
response = completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "What is the capital of France?"}]
)
print(response.choices[0].message.content)
```

### 2. Using Environment Variables

Create a `.env` file:
```env
OPENAI_API_KEY=your_api_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

Load and use environment variables:
```python
from dotenv import load_dotenv
import os
from litellm import completion

load_dotenv()

response = completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello, how are you?"}],
    api_key=os.getenv("OPENAI_API_KEY")
)
```

### 3. Model Fallbacks

```python
from litellm import completion

# Set up model fallbacks
fallback_models = ["gpt-4o-mini", "claude-2", "palm-2"]

for model in fallback_models:
    try:
        response = completion(
            model=model,
            messages=[{"role": "user", "content": "Write a short poem about Python"}]
        )
        print(f"Success with model: {model}")
        print(response.choices[0].message.content)
        break
    except Exception as e:
        print(f"Error with {model}: {str(e)}")
        continue
```

### 4. Async Operations

```python
import asyncio
from litellm import acompletion

async def get_completion(message):
    response = await acompletion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": message}]
    )
    return response.choices[0].message.content

async def main():
    messages = [
        "What is Python?",
        "What is JavaScript?",
        "What is Rust?"
    ]
    
    tasks = [get_completion(msg) for msg in messages]
    responses = await asyncio.gather(*tasks)
    
    for msg, response in zip(messages, responses):
        print(f"Q: {msg}")
        print(f"A: {response}\n")

# Run async code
asyncio.run(main())
```

### 5. Streaming Responses

```python
from litellm import completion

response = completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Write a story about a robot"}],
    stream=True
)

for chunk in response:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="")
```

## Advanced Features

### 1. Token Counting

```python
from litellm import completion

response = completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello, how are you?"}],
    get_token_count=True
)

print(f"Input tokens: {response.usage.prompt_tokens}")
print(f"Output tokens: {response.usage.completion_tokens}")
print(f"Total tokens: {response.usage.total_tokens}")
```

### 2. Cost Tracking

```python
from litellm import completion, get_cost_per_token

# Get cost for a specific model
cost_per_token = get_cost_per_token("gpt-4o-mini")
print(f"Cost per token: ${cost_per_token}")

# Track cost of completion
response = completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Write a haiku"}],
    get_token_count=True
)

total_cost = (
    response.usage.total_tokens * cost_per_token
)
print(f"Total cost: ${total_cost:.4f}")
```

## Best Practices

1. **API Key Management**
   - Always use environment variables for API keys
   - Never hardcode API keys in your code
   - Use a `.env` file for local development

2. **Error Handling**
   - Implement proper try-except blocks
   - Use model fallbacks for reliability
   - Log errors for debugging

3. **Performance Optimization**
   - Use async operations for multiple requests
   - Implement caching when appropriate
   - Monitor token usage and costs

4. **Security**
   - Keep API keys secure
   - Validate user inputs
   - Implement rate limiting
   - Monitor usage patterns

## Common Issues and Solutions

1. **Rate Limiting**
```python
from litellm import completion
import time

def rate_limited_completion(message, max_retries=3, delay=1):
    for attempt in range(max_retries):
        try:
            return completion(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": message}]
            )
        except Exception as e:
            if "rate_limit" in str(e).lower():
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))
                    continue
            raise
```

2. **Handling Timeouts**
```python
from litellm import completion

try:
    response = completion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Long prompt here..."}],
        timeout=30  # 30 seconds timeout
    )
except Exception as e:
    print(f"Request timed out: {str(e)}")
```

## Model Support and Compatibility

### Supported Models

LiteLLM supports a wide range of models across different providers:

| Provider | Models | Aliases |
|----------|---------|---------|
| OpenAI | gpt-4, gpt-3.5-turbo | openai/gpt-4, openai/gpt-3.5-turbo |
| Anthropic | claude-2, claude-instant-1 | anthropic/claude-2 |
| Google | palm-2 | google/palm-2 |
| Azure OpenAI | Same as OpenAI | azure/gpt-4, azure/gpt-3.5-turbo |

### Model-Specific Parameters

```python
from litellm import completion

# OpenAI-specific parameters
response = completion(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}],
    temperature=0.7,
    top_p=1.0,
    presence_penalty=0,
    frequency_penalty=0
)

# Anthropic-specific parameters
response = completion(
    model="claude-2",
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens_to_sample=100,
    temperature=0.7
)
```

## Configuration Options

### Basic Configuration

```python
from litellm import completion, set_verbose, set_timeout

# Enable debug logging
set_verbose(True)

# Set global timeout
set_timeout(30)

# Custom retry configuration
response = completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
    num_retries=3,
    retry_delay=1
)
```

### Enterprise Setup

```python
from litellm import completion

# Proxy configuration
response = completion(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}],
    proxy="http://proxy.example.com:8080",
    custom_headers={
        "Authorization": "Bearer your-token",
        "X-Custom-Header": "value"
    }
)
```

## Testing and Quality Assurance

### Unit Testing

```python
import unittest
from unittest.mock import patch
from litellm import completion

class TestLiteLLM(unittest.TestCase):
    def test_completion(self):
        response = completion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}]
        )
        self.assertIsNotNone(response)
        self.assertTrue(hasattr(response, 'choices'))

    @patch('litellm.completion')
    def test_completion_mock(self, mock_completion):
        # Mock response
        mock_completion.return_value.choices = [{
            "message": {"content": "Hello there!"},
            "finish_reason": "stop"
        }]
        
        response = completion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}]
        )
        self.assertEqual(
            response.choices[0].message.content,
            "Hello there!"
        )
```

## Monitoring and Observability

### Logging Setup

```python
import logging
from litellm import completion

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('litellm')

def log_completion(response, error=None):
    if error:
        logger.error(f"Completion error: {error}")
    else:
        logger.info(
            f"Completion success: {len(response.choices[0].message.content)} chars"
        )

# Usage with logging
try:
    response = completion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}]
    )
    log_completion(response)
except Exception as e:
    log_completion(None, error=e)
```

### Cost and Usage Tracking

```python
from litellm import completion
from datetime import datetime

class UsageTracker:
    def __init__(self):
        self.total_tokens = 0
        self.total_cost = 0
        self.requests = 0

    def track(self, response):
        self.total_tokens += response.usage.total_tokens
        self.total_cost += (
            response.usage.total_tokens * 
            get_cost_per_token(response.model)
        )
        self.requests += 1

# Usage
tracker = UsageTracker()
response = completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
    get_token_count=True
)
tracker.track(response)
```

## Performance Optimization

### Caching

```python
import hashlib
import json
from functools import lru_cache
from litellm import completion

@lru_cache(maxsize=1000)
def cached_completion(message_hash):
    return completion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": message_hash}]
    )

def get_completion(message):
    # Create a hash of the message for caching
    message_hash = hashlib.md5(
        json.dumps(message, sort_keys=True).encode()
    ).hexdigest()
    return cached_completion(message_hash)
```

### Batch Processing

```python
import asyncio
from litellm import acompletion

async def process_batch(messages, batch_size=5):
    """Process messages in batches to avoid rate limits"""
    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        tasks = [
            acompletion(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": msg}]
            )
            for msg in batch
        ]
        yield await asyncio.gather(*tasks)
        # Add delay between batches to respect rate limits
        await asyncio.sleep(1)

# Usage
async def main():
    messages = ["Hello", "Hi", "Hey", "Greetings", "Good day"]
    async for batch_responses in process_batch(messages):
        for response in batch_responses:
            print(response.choices[0].message.content)

asyncio.run(main())
```

## LiteLLM Exception Mapping

## Overview

LiteLLM provides a robust exception mapping system that standardizes error handling across different LLM providers. This allows for more consistent and predictable error management in your applications.

## Exception Types

LiteLLM maps exceptions to standardized error types, inheriting from OpenAI's error classes. The base case returns a `litellm.APIConnectionError` exception.

### Key Exception Types

- `APIConnectionError`
- `Timeout`
- `ContextWindowExceededError`
- `BadRequestError`
- `NotFoundError`
- `ContentPolicyViolationError`
- `AuthenticationError`
- `APIError`
- `RateLimitError`
- `ServiceUnavailableError`
- `PermissionDeniedError`
- `UnprocessableEntityError`

## Usage Examples

### Basic Exception Handling

```python
import litellm
import openai

try:
    response = litellm.completion(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant designed to output JSON."
            },
            {
                "role": "user",
                "content": "Who won the world series in 2020?"
            }
        ],
        response_format={ "type": "json_object" },
        timeout=0.01  # Intentionally short timeout to trigger an exception
    )
except openai.APITimeoutError as e:
    # Check if the exception should be retried
    should_retry = litellm._should_retry(e.status_code)
    print(f"Should retry: {should_retry}")
```

### Streaming Exception Handling

```python
import litellm

try:
    response = litellm.completion(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": "Hello"}],
        stream=True
    )
    
    for chunk in response:
        print(chunk)
except Exception as e:
    print(f"Error during streaming: {e}")
```

## Provider-Specific Exception Mapping

LiteLLM supports exception mapping for various providers. Here's a summary of supported exceptions:

| Provider | Timeout | Context Window | Bad Request | Authentication | Rate Limit | Other Notable Exceptions |
|----------|---------|----------------|-------------|----------------|------------|--------------------------|
| OpenAI | ✓ | ✓ | ✓ | ✓ | - | Content Policy Violation |
| Anthropic | ✓ | ✓ | ✓ | ✓ | - | Service Unavailable |
| Azure | ✓ | ✓ | ✓ | ✓ | - | Service Unavailable |
| Bedrock | ✓ | ✓ | ✓ | ✓ | ✓ | Permission Denied |
| Vertex AI | ✓ | - | ✓ | - | - | Unprocessable Entity |

## Retry Logic

Use `litellm._should_retry()` to determine if an exception warrants a retry:

```python
import litellm

def handle_llm_call(model, messages):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = litellm.completion(
                model=model,
                messages=messages
            )
            return response
        except Exception as e:
            if not litellm._should_retry(getattr(e, 'status_code', None)):
                raise
            print(f"Retry attempt {attempt + 1}")
```

## Best Practices

1. Always use try-except blocks when making LLM calls
2. Check `_should_retry()` for potential retry scenarios
3. Log exceptions for debugging
4. Handle provider-specific nuances
5. Implement appropriate fallback mechanisms

## Notes

- `ContextWindowExceededError` is a sub-class of `InvalidRequestError`
- For OpenAI and Azure, the original exception is returned with an added `llm_provider` attribute
- Contributions to improve exception mapping are welcome

## Resources

- [LiteLLM GitHub Repository](https://github.com/BerriAI/litellm)
- [Exception Mapping Implementation](https://github.com/BerriAI/litellm/blob/main/litellm/utils.py)

## LiteLLM Streaming and Async Responses

### Streaming Responses

#### Usage

LiteLLM supports streaming responses across different models. Here's a basic example:

```python
import litellm

# Basic Streaming
response = litellm.completion(
    model="gpt-3.5-turbo", 
    messages=[{"role": "user", "content": "Hey"}],
    stream=True
)

for chunk in response:
    print(chunk)
```

#### Helper Function

You can use a helper function to simplify streaming:

```python
def stream_response(model, messages):
    response = litellm.completion(
        model=model, 
        messages=messages,
        stream=True
    )
    
    for chunk in response:
        yield chunk
```

### Async Completion

#### Usage

For asynchronous completions:

```python
import litellm
import asyncio

async def async_completion():
    response = await litellm.acompletion(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello"}]
    )
    print(response)

asyncio.run(async_completion())
```

### Async Streaming

#### Usage

Combining async and streaming:

```python
import litellm
import asyncio

async def async_stream_completion():
    response = await litellm.acompletion(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello"}],
        stream=True
    )
    
    async for chunk in response:
        print(chunk)

asyncio.run(async_stream_completion())
```

### Error Handling - Infinite Loops

To prevent infinite loops, LiteLLM provides configuration options:

```yaml
# In config.yaml
litellm_settings:
    REPEATED_STREAMING_CHUNK_LIMIT: 100  # Prevents excessive streaming
```

### Proxy Configuration

When using the LiteLLM proxy, you can configure streaming settings in the `config.yaml`:

```yaml
litellm_settings:
    REPEATED_STREAMING_CHUNK_LIMIT: 100  # Override default streaming limit
```

### Best Practices

1. Always handle streaming responses in a loop
2. Use async methods for non-blocking operations
3. Set appropriate chunk limits to prevent excessive streaming
4. Handle potential exceptions during streaming

## Resources

- [LiteLLM GitHub Repository](https://github.com/BerriAI/litellm)
- [Official Documentation](https://docs.litellm.ai/)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)

## Structured Outputs (JSON Mode)

### Quick Start

#### SDK
```python
from litellm import completion
import os 

os.environ["OPENAI_API_KEY"] = ""

response = completion(
  model="gpt-4o-mini",
  response_format={ "type": "json_object" },
  messages=[
    {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
    {"role": "user", "content": "Who won the world series in 2020?"}
  ]
)
print(response.choices[0].message.content)
```

### Check Model Support

#### 1. Check if model supports response_format
Call `litellm.get_supported_openai_params` to check if a model/provider supports `response_format`.

```python
from litellm import get_supported_openai_params

params = get_supported_openai_params(model="anthropic.claude-3", custom_llm_provider="bedrock")

assert "response_format" in params
```

#### 2. Check if model supports json_schema
This is used to check if you can pass:
- `response_format={ "type": "json_schema", "json_schema": … , "strict": true }`
- `response_format=<Pydantic Model>`

```python
from litellm import supports_response_schema

assert supports_response_schema(model="gemini-1.5-pro-preview-0215", custom_llm_provider="bedrock")
```

Check out `model_prices_and_context_window.json` for a full list of models and their support for response_schema.

### Pass in 'json_schema'
To use Structured Outputs, simply specify:
`response_format: { "type": "json_schema", "json_schema": … , "strict": true }`

Works for:
- OpenAI models
- Azure OpenAI models
- Google AI Studio - Gemini models
- Vertex AI models (Gemini + Anthropic)
- Bedrock Models
- Anthropic API Models
- Groq Models
- Ollama Models
- Databricks Models

#### SDK
```python
import os
from litellm import completion 
from pydantic import BaseModel

# add to env var 
os.environ["OPENAI_API_KEY"] = ""

messages = [{"role": "user", "content": "List 5 important events in the XIX century"}]

class CalendarEvent(BaseModel):
  name: str
  date: str
  participants: list[str]

class EventsList(BaseModel):
    events: list[CalendarEvent]

resp = completion(
    model="gpt-4o-2024-08-06",
    messages=messages,
    response_format=EventsList
)

print("Received={}".format(resp))
```

### Validate JSON Schema
Not all vertex models support passing the json_schema to them (e.g. gemini-1.5-flash). To solve this, LiteLLM supports client-side validation of the json schema.

`litellm.enable_json_schema_validation=True`

If `litellm.enable_json_schema_validation=True` is set, LiteLLM will validate the json response using jsonvalidator.

#### SDK
```python
# !gcloud auth application-default login - run this to add vertex credentials to your env
import litellm, os
from litellm import completion 
from pydantic import BaseModel 

messages=[
        {"role": "system", "content": "Extract the event information."},
        {"role": "user", "content": "Alice and Bob are going to a science fair on Friday."},
    ]

litellm.enable_json_schema_validation = True
litellm.set_verbose = True # see the raw request made by litellm

class CalendarEvent(BaseModel):
  name: str
  date: str
  participants: list[str]

resp = completion(
    model="gemini/gemini-1.5-pro",
    messages=messages,
    response_format=CalendarEvent,
)

print("Received={}".format(resp))
