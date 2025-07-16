# Flow Fluent API V2 - Evolution Plan

## Overview

The Quantalogic Flow Fluent API V2 is a **proposed evolution** that enhances the existing workflow system with production-ready features while maintaining 100% backward compatibility. This design focuses on the most valuable improvements that real users need.

## Design Principles

### 🎯 **Focused Enhancement**

- Build upon the solid V1 foundation
- Add only high-value features that solve real problems
- Maintain API simplicity and clarity
- Preserve backward compatibility

### 🔧 **Core Improvements**

- **Production Reliability**: Timeouts, retries, and error handling
- **Better LLM Integration**: Fallback models and streaming support
- **Enhanced Observability**: Event monitoring and basic metrics
- **Type Safety**: Proper typing without complexity
- **Async Support**: Gradual migration to async patterns

## What's New in V2

### ✅ **High-Value Additions**

- **Timeout & Retry Support**: `@Nodes.define(timeout=30, retries=3)`
- **Enhanced Error Handling**: `.catch()` and `.finally_node()`
- **LLM Fallbacks**: `fallback_models=["gpt-3.5-turbo"]`
- **Event Monitoring**: `.observe()` with basic metrics
- **Type Annotations**: Full typing support throughout

### � **Deliberately Excluded**

- Complex branching strategies ("weighted", "all_match")
- Multiple template formats (stick to Jinja2)
- Parallel API variants (`@Nodes.async_define`)
- Over-engineered abstractions (join strategies, etc.)

## Core Concepts

### Workflow Architecture

The V2 API enhances the existing declarative workflow model:

- **Nodes** represent individual processing units
- **Transitions** define the flow between nodes
- **Context** carries data throughout the workflow
- **Observers** monitor execution events
- **Conditions** control dynamic routing

```python
from quantalogic_flow.flow import Workflow, Nodes
from typing import Dict, Any

# Enhanced workflow with V2 features
workflow = (
    Workflow("data_ingestion")
    .then("data_validation", timeout=30)
    .branch([
        ("ml_processing", lambda ctx: ctx.get("data_type") == "ml"),
        ("standard_processing", lambda ctx: ctx.get("data_type") == "standard")
    ])
    .then("data_output")
    .catch(Exception, "error_handler")
    .observe(performance_monitor)
)
```

### Node Registration System

Enhanced node registration with production-ready features:

```python
from quantalogic_flow.flow.nodes import Nodes
from typing import Optional, List, Dict, Any

# V2 node with timeout and retry support
@Nodes.define(output="processed_data", timeout=30, retries=2)
async def process_data(
    raw_data: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Process raw data with timeout and retry support."""
    # Processing logic here
    return {"processed": raw_data, "config": config}
```

## Enhanced Workflow Methods

### Constructor

```python
Workflow(start_node: str)
```

Creates a new workflow instance (unchanged from V1 for backward compatibility).

**Parameters:**

- `start_node`: The name of the initial node

**Example:**

```python
workflow = Workflow("start_processing")
```

### Chain Building Methods

#### `.then(next_node, condition=None, timeout=None)`

Adds a transition with optional timeout support.

**Parameters:**

- `next_node`: Name of the node to transition to
- `condition`: Optional callable for conditional transitions
- `timeout`: Optional timeout in seconds

**Example:**

```python
workflow = (
    Workflow("fetch_data")
    .then("validate_data", timeout=30)
    .then("process_data",
          condition=lambda ctx: ctx.get("validation_status") == "passed")
    .then("store_results")
)
```

#### `.node(name, inputs_mapping=None, retries=0, timeout=None)`

Enhanced node addition with retry logic and timeout handling.

**Parameters:**

- `name`: Node name
- `inputs_mapping`: Input parameter mapping
- `retries`: Number of retry attempts
- `timeout`: Execution timeout

**Example:**

```python
workflow = (
    Workflow("start")
    .node("api_call",
          inputs_mapping={"endpoint": "api_endpoint", "params": "request_params"},
          retries=3,
          timeout=60)
    .node("process_response")
)
```

#### `.sequence(*nodes)`

Execute nodes in sequence (unchanged from V1).

**Parameters:**

- `*nodes`: Node names to execute

**Example:**

```python
workflow = (
    Workflow("start")
    .sequence("validate", "transform", "store")
    .then("notify")
)
```

### Enhanced Branching

#### `.branch(branches, default=None)`

Conditional branching (simplified from complex V2 proposal).

**Parameters:**

- `branches`: List of (node, condition) tuples
- `default`: Default node if no conditions match

**Example:**

```python
workflow = (
    Workflow("analyze_request")
    .branch([
        ("priority_handler", lambda ctx: ctx.get("priority") == "high"),
        ("standard_handler", lambda ctx: ctx.get("priority") == "medium"),
        ("batch_handler", lambda ctx: ctx.get("priority") == "low")
    ],
    default="error_handler")
)
```

#### `.switch(key, cases, default=None)`

Switch-case style branching for cleaner conditional logic.

**Parameters:**

- `key`: Context key or callable to evaluate
- `cases`: Dictionary of value -> node mappings
- `default`: Default node for unmatched cases

**Example:**

```python
workflow = (
    Workflow("classify_input")
    .switch("input_type", {
        "text": "text_processor",
        "image": "image_processor",
        "audio": "audio_processor",
        "video": "video_processor"
    }, default="unsupported_handler")
)
```

### Error Handling and Recovery

#### `.catch(exception_type, handler_node, retry_count=0)`

Enhanced error handling with specific exception types.

**Parameters:**

- `exception_type`: Exception type to catch
- `handler_node`: Node to handle the error
- `retry_count`: Number of retries before handling

**Example:**

```python
from requests.exceptions import RequestException

workflow = (
    Workflow("start")
    .node("api_call")
    .catch(RequestException, "network_error_handler", retry_count=3)
    .catch(ValueError, "validation_error_handler")
    .then("success_handler")
)
```

#### `.finally_node(cleanup_node)`

Ensure cleanup node always executes.

**Parameters:**

- `cleanup_node`: Node to execute for cleanup

**Example:**

```python
workflow = (
    Workflow("acquire_resource")
    .then("use_resource")
    .finally_node("release_resource")
)
```

### Observability

#### `.observe(observer, events=None)`

Enhanced observability with event filtering.

**Parameters:**

- `observer`: Observer function
- `events`: Optional list of events to observe

**Example:**

```python
def performance_observer(event):
    if event.event_type == "NODE_COMPLETED":
        duration = event.data.get("duration", 0)
        if duration > 5.0:
            print(f"Slow operation: {event.node_name} took {duration}s")

workflow = (
    Workflow("start")
    .observe(performance_observer)
    .then("process_data")
    .then("finish")
)
```

## Enhanced Node Decorators

### Core Decorators

#### `@Nodes.define(output=None, timeout=None, retries=0)`

Enhanced basic node decorator with timeout and retry support.

**Parameters:**

- `output`: Context key for output
- `timeout`: Execution timeout in seconds
- `retries`: Number of retry attempts

**Example:**

```python
@Nodes.define(output="processed_data", timeout=30, retries=2)
async def process_data(raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process raw data with timeout and retry support."""
    # Processing logic
    return {"processed": raw_data}
```

### Enhanced LLM Integration

#### `@Nodes.llm_node(model, system_prompt, prompt_template, fallback_models=None, **kwargs)`

Enhanced LLM node with fallback model support.

**Parameters:**

- `model`: Primary model name
- `system_prompt`: System prompt template
- `prompt_template`: User prompt template
- `fallback_models`: List of fallback models
- `**kwargs`: Additional LLM parameters

**Example:**

```python
@Nodes.llm_node(
    model="gpt-4",
    system_prompt="You are an expert data analyst.",
    prompt_template="Analyze this data: {{data}}",
    fallback_models=["gpt-3.5-turbo", "claude-3-sonnet"],
    output="analysis_result"
)
async def analyze_data(data: Dict[str, Any]) -> str:
    """Analyze data with LLM support and fallback models."""
    pass
```

#### `@Nodes.structured_llm_node(model, system_prompt, prompt_template, response_model, fallback_models=None, **kwargs)`

Enhanced structured LLM node with fallback support.

**Parameters:**

- `model`: Primary model name
- `system_prompt`: System prompt template
- `prompt_template`: User prompt template
- `response_model`: Pydantic model for response
- `fallback_models`: List of fallback models
- `**kwargs`: Additional LLM parameters

**Example:**

```python
class DataInsights(BaseModel):
    summary: str
    key_findings: List[str]
    recommendations: List[str]

@Nodes.structured_llm_node(
    model="gpt-4",
    system_prompt="You are a data scientist.",
    prompt_template="Analyze: {{data}}",
    response_model=DataInsights,
    fallback_models=["gpt-3.5-turbo"],
    output="insights"
)
async def generate_insights(data: Dict[str, Any]) -> DataInsights:
    """Generate structured insights from data."""
    pass
```

## Practical Examples

### 1. Production Data Processing Pipeline

```python
from quantalogic_flow.flow import Workflow, Nodes
from typing import List, Dict, Any
from pydantic import BaseModel

class ProcessingConfig(BaseModel):
    batch_size: int = 100
    timeout: int = 300

@Nodes.define(output="raw_data")
async def fetch_data_source() -> List[Dict[str, Any]]:
    """Fetch data from external source."""
    return [{"id": f"item_{i}", "value": i * 10} for i in range(1000)]

@Nodes.define(output="processed_data", timeout=60, retries=2)
async def process_data_batch(
    raw_data: List[Dict[str, Any]],
    config: ProcessingConfig
) -> Dict[str, Any]:
    """Process data with timeout and retry support."""
    # Processing logic
    return {
        "processed_count": len(raw_data),
        "total_value": sum(item.get("value", 0) for item in raw_data)
    }

@Nodes.define(output="results")
async def store_results(processed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Store processed results."""
    return {"success": True, "stored_count": processed_data["processed_count"]}

def error_handler(event):
    print(f"Error in {event.node_name}: {event.exception}")

# Build workflow with error handling
workflow = (
    Workflow("fetch_data_source")
    .then("process_data_batch", timeout=120)
    .then("store_results")
    .catch(Exception, "error_handler")
    .observe(error_handler)
)
```

### 2. Enhanced AI Content Generation

```python
from quantalogic_flow.flow import Workflow, Nodes
from pydantic import BaseModel
from typing import List, Dict, Any

class ContentRequest(BaseModel):
    topic: str
    target_audience: str
    content_type: str

class ContentPlan(BaseModel):
    title: str
    outline: List[str]
    key_points: List[str]

@Nodes.structured_llm_node(
    model="gpt-4",
    system_prompt="You are a content strategist.",
    prompt_template="Create a content plan for: {{topic}} targeting {{target_audience}}",
    response_model=ContentPlan,
    fallback_models=["gpt-3.5-turbo"],
    output="content_plan"
)
async def create_content_plan(request: ContentRequest) -> ContentPlan:
    """Create a structured content plan."""
    pass

@Nodes.llm_node(
    model="gpt-4",
    system_prompt="You are a skilled content writer.",
    prompt_template="Write {{content_type}} content based on: {{content_plan}}",
    fallback_models=["gpt-3.5-turbo"],
    output="content"
)
async def generate_content(
    content_plan: ContentPlan,
    request: ContentRequest
) -> str:
    """Generate content based on the plan."""
    pass

@Nodes.define(output="final_content")
async def finalize_content(content: str, content_plan: ContentPlan) -> Dict[str, Any]:
    """Finalize content with metadata."""
    return {
        "title": content_plan.title,
        "content": content,
        "word_count": len(content.split())
    }

# Build workflow
workflow = (
    Workflow("create_content_plan")
    .then("generate_content", timeout=60)
    .then("finalize_content")
    .catch(Exception, "content_error_handler")
)
```

### 3. Resilient API Integration

```python
from quantalogic_flow.flow import Workflow, Nodes
from typing import Dict, Any

@Nodes.define(output="api_data", timeout=30, retries=3)
async def fetch_primary_api(endpoint: str) -> Dict[str, Any]:
    """Fetch data from primary API with retries."""
    # API call logic
    return {"data": "primary_result", "source": "primary"}

@Nodes.define(output="api_data", timeout=20, retries=2)
async def fetch_fallback_api(endpoint: str) -> Dict[str, Any]:
    """Fetch data from fallback API."""
    # Fallback API call
    return {"data": "fallback_result", "source": "fallback"}

@Nodes.define(output="processed_result")
async def process_api_data(api_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process API data regardless of source."""
    return {
        "processed": api_data["data"],
        "source": api_data["source"],
        "timestamp": "2024-01-01T00:00:00Z"
    }

# Build resilient workflow
workflow = (
    Workflow("fetch_primary_api")
    .catch(Exception, "fetch_fallback_api")
    .then("process_api_data")
    .finally_node("cleanup_resources")
)
```

## Migration from V1 to V2

### Backward Compatibility

All existing V1 code continues to work unchanged:

```python
# V1 Code - Still works in V2
@Nodes.define(output="result")
def process_data(data):
    return data.upper()

workflow = Workflow("start").then("process_data").then("end")
```

### Gradual Enhancement

Add V2 features incrementally:

```python
# Enhanced with V2 features
@Nodes.define(output="result", timeout=30, retries=2)
async def process_data(data: str) -> str:
    """Enhanced with timeout and retry support."""
    return data.upper()

workflow = (
    Workflow("start")
    .then("process_data", timeout=60)
    .catch(Exception, "error_handler")
    .observe(performance_monitor)
)
```

### Key Migration Steps

1. **Add Timeouts**: Add timeout parameters to critical nodes
2. **Add Error Handling**: Use `.catch()` for better error management
3. **Add Observability**: Use `.observe()` for monitoring
4. **Enhance LLM Nodes**: Add fallback models for reliability

## Implementation Priority

### Phase 1: Core Reliability

- [ ] Timeout support in decorators and workflow methods
- [ ] Retry logic for node execution
- [ ] Enhanced error handling with `.catch()` and `.finally_node()`
- [ ] Basic observability with `.observe()`

### Phase 2: LLM Enhancements

- [ ] Fallback model support in LLM nodes
- [ ] Streaming response support
- [ ] Enhanced error recovery for LLM failures
- [ ] Better prompt templating

### Phase 3: Advanced Features

- [ ] Parallel execution improvements
- [ ] Workflow composition enhancements
- [ ] Performance monitoring
- [ ] Testing utilities

## Conclusion

The Flow Fluent API V2 evolution focuses on **production readiness** and **developer experience** while maintaining complete backward compatibility. By prioritizing high-value features like error handling, timeouts, and LLM resilience, V2 transforms the workflow system into a robust foundation for production applications.

The design deliberately avoids feature creep, focusing instead on making the existing system more reliable, observable, and maintainable. This approach ensures that V2 delivers real value to users while keeping the API simple and intuitive.
