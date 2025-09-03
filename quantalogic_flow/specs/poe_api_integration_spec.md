# POE API Integration Specification for Quantalogic Flow

## Overview

This specification outlines the implementation plan for integrating POE API support into Quantalogic Flow using LiteLLM, enabling users to access POE's extensive model ecosystem with the familiar syntax `poe/model_name`.

## Background

### POE API Characteristics
- **OpenAI-Compatible**: POE API uses standard OpenAI chat completion interface
- **Base URL**: `https://api.poe.com/v1`
- **Authentication**: Uses API key via `POE_API_KEY` environment variable
- **Models**: Access to Claude, Gemini, Grok, and other frontier models
- **Pricing**: Same pricing as underlying model providers

### Current Quantalogic Flow Architecture
- Uses LiteLLM for unified LLM provider access
- Custom providers configured in `quantalogic_react/quantalogic/quantlitellm.py`
- LLM nodes use `@Nodes.llm_node(model="provider/model")` syntax
- Supports dynamic model selection and streaming

## Implementation Plan

### Phase 1: Core Integration

#### 1.1 Add POE Provider Configuration
**File**: `quantalogic_react/quantalogic/quantlitellm.py`

Add POE to the PROVIDERS dictionary:

```python
"poe": ModelProviderConfig(
    prefix="poe/",
    provider="openai",
    base_url="https://api.poe.com/v1",
    env_var="POE_API_KEY",
),
```

#### 1.2 Update Documentation
**File**: `quantalogic_flow/LLM_PROVIDERS.md`

Add POE section with:
- Setup instructions
- Available models
- Usage examples
- Environment variable configuration

### Phase 2: Model Discovery and Validation

#### 2.1 Model List Integration
**File**: `quantalogic_react/quantalogic/llm_util/data.py`

Add POE model fetching capability:
- Implement `list_poe_models()` function
- Add POE models to the unified model list
- Handle model metadata (pricing, context windows)

#### 2.2 Model Validation
**File**: `quantalogic_react/quantalogic/get_model_info.py`

Add POE model information:
- Max input/output tokens
- Pricing information
- Model capabilities

### Phase 3: Enhanced Features

#### 3.1 Streaming Support
Ensure POE models work with existing streaming functionality in:
- `GenerativeModel.async_generate_with_history()`
- `@Nodes.llm_node` streaming parameter

#### 3.2 Error Handling
Add POE-specific error handling for:
- Rate limits
- Authentication failures
- Model availability

#### 3.3 Cost Tracking
Integrate POE usage costs with existing cost tracking in:
- Token usage reporting
- Cost calculation functions

### Phase 4: Testing and Documentation

#### 4.1 Unit Tests
**File**: `tests/test_poe_integration.py`

Test cases for:
- POE provider configuration
- Model validation
- Error handling
- Streaming functionality

#### 4.2 Integration Tests
**File**: `tests/integration/test_poe_workflow.py`

End-to-end tests for:
- POE models in workflows
- Cost tracking
- Error scenarios

#### 4.3 Example Usage
**File**: `examples/poe_integration_example.py`

Demonstrate:
- Basic POE model usage
- Streaming with POE
- Cost tracking

## Usage Examples

### Basic Usage
```python
from quantalogic_flow import Workflow, Nodes

@Nodes.llm_node(model="poe/Claude-Sonnet-4", output="response")
async def analyze_text(text: str):
    return f"Analyze this text: {text}"

workflow = Workflow().add(analyze_text, text="Hello World")
result = await workflow.build().run({})
```

### Advanced Usage with Dynamic Models
```python
@Nodes.llm_node(
    model=lambda ctx: f"poe/{ctx['model_name']}",
    temperature=0.7,
    output="analysis"
)
async def dynamic_analysis(text: str, model_name: str):
    return f"Analyze: {text}"
```

### Streaming Usage
```python
@Nodes.llm_node(
    model="poe/Grok-4",
    output="stream_response",
    temperature=0.8
)
async def stream_response(query: str):
    return f"Answer: {query}"
```

## Environment Setup

### Required Environment Variables
```bash
export POE_API_KEY="your-poe-api-key"
```

### Optional Configuration
```bash
export POE_BASE_URL="https://api.poe.com/v1"  # Default value
export POE_TIMEOUT="30"  # Request timeout in seconds
```

## Available POE Models

Based on POE API documentation, the following models are available:

### Claude Models
- `Claude-Sonnet-4` - Latest Claude Sonnet
- `Claude-Opus-4.1` - Claude Opus 4.1
- `Claude-Haiku-3.5` - Claude Haiku 3.5

### Gemini Models
- `Gemini-2.0-Flash` - Latest Gemini Flash
- `Gemini-1.5-Pro` - Gemini 1.5 Pro

### Grok Models
- `Grok-4` - Latest Grok model
- `Grok-3` - Grok 3

### Other Models
- `GPT-4o` - OpenAI GPT-4o
- `o3-mini` - OpenAI o3-mini
- `DeepSeek-R1` - DeepSeek R1

## Implementation Considerations

### 1. Model Name Mapping
POE uses different model names than other providers. Need to:
- Map POE model names to standardized names
- Handle model versioning
- Support model aliases

### 2. Rate Limiting
POE has subscription-based rate limits:
- Handle rate limit errors gracefully
- Implement exponential backoff
- Provide clear error messages

### 3. Cost Calculation
POE charges the same as underlying providers:
- Integrate with existing cost tracking
- Update pricing data regularly
- Handle different pricing tiers

### 4. Backward Compatibility
Ensure changes don't break existing functionality:
- Maintain existing provider configurations
- Preserve API compatibility
- Add opt-in POE support

## Success Criteria

### Functional Requirements
- [ ] Users can use `poe/model_name` syntax in `@Nodes.llm_node`
- [ ] POE models appear in model discovery
- [ ] Streaming works with POE models
- [ ] Cost tracking includes POE usage
- [ ] Error handling covers POE-specific scenarios

### Non-Functional Requirements
- [ ] No performance impact on existing providers
- [ ] Clear documentation and examples
- [ ] Comprehensive test coverage
- [ ] Backward compatibility maintained

## Risk Assessment

### High Risk
- POE API changes breaking compatibility
- Authentication issues with API keys
- Rate limiting affecting user experience

### Medium Risk
- Model availability changes
- Pricing updates
- Documentation becoming outdated

### Mitigation Strategies
- Implement robust error handling
- Add configuration validation
- Create comprehensive tests
- Monitor API changes regularly

## Timeline

### Week 1: Core Integration
- Add POE provider configuration
- Update documentation
- Basic testing

### Week 2: Model Discovery
- Implement model list fetching
- Add model validation
- Update model information

### Week 3: Enhanced Features
- Streaming support
- Error handling improvements
- Cost tracking integration

### Week 4: Testing and Documentation
- Comprehensive testing
- Example implementations
- Final documentation updates

## Dependencies

### Required Packages
- `litellm>=1.73.6` (already included)
- `openai` (for API compatibility)
- `requests` (for model discovery)

### Optional Packages
- `instructor` (for structured outputs)

## Conclusion

Integrating POE API into Quantalogic Flow will significantly expand the available model ecosystem while maintaining the unified interface that users expect. The implementation leverages existing LiteLLM infrastructure with minimal changes required to the core codebase.

The phased approach ensures thorough testing and validation at each step, minimizing risk and ensuring a smooth rollout.
