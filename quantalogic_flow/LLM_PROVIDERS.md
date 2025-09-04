# LLM Provider Configuration Guide

This guide provides comprehensive setup instructions for using Quantalogic Flow with various LLM providers through Instructor integration.

## Why Instructor?

Instructor provides a unified interface for structured outputs across 20+ LLM providers, offering:

- **Type-Safe Responses**: Native Pydantic validation with automatic retries
- **Unified API**: Single interface for all providers with `instructor.from_provider()`
- **Advanced Features**: Streaming, partial responses, batch processing
- **20+ Providers**: Support for OpenAI, Anthropic, Google, Meta, Mistral, and more
- **Future-Proof**: Active development with modern LLM patterns

## Quick Provider Setup

### OpenAI & Compatible APIs

```bash
export OPENAI_API_KEY="sk-your-openai-key"
# Models: openai/gpt-4o, openai/gpt-4o-mini, openai/gpt-3.5-turbo, etc.
```

### Anthropic Claude

```bash
export ANTHROPIC_API_KEY="your-anthropic-key"
# Models: anthropic/claude-3-5-sonnet, anthropic/claude-3-haiku, etc.
```

### Google Gemini

```bash
export GEMINI_API_KEY="your-gemini-api-key"
# Models: google/gemini-1.5-flash, google/gemini-1.5-pro, etc.
```

### Mistral AI

```bash
export MISTRAL_API_KEY="your-mistral-key"
# Models: mistral/mistral-large-latest, mistral/mistral-small, etc.
```

### Groq (Fast Inference)

```bash
export GROQ_API_KEY="your-groq-key"
# Models: groq/llama3-8b-8192, groq/llama3-70b-8192, etc.
```

## Comprehensive Provider Guide

### 🤖 **OpenAI**

The most popular cloud LLM provider with GPT models.

**Setup:**

```bash
export OPENAI_API_KEY="sk-your-openai-key"
# Optional: export OPENAI_BASE_URL="https://your-proxy.com/v1"
```

**Popular Models:**

- `openai/gpt-4o` - Latest flagship model
- `openai/gpt-4o-mini` - Fast and cost-effective
- `openai/gpt-3.5-turbo` - Legacy but reliable
- `openai/o1-mini` - Reasoning model

**Example Usage:**

```python
from quantalogic_flow import Workflow, Nodes

@Nodes.llm(model="openai/gpt-4o", output="response")
async def analyze_text(text: str):
    return f"Analyze this text: {text}"

workflow = Workflow().add(analyze_text, text="Hello World")
result = await workflow.build().run({})
```

📖 **Documentation:** [Instructor OpenAI Guide](https://python.useinstructor.com/integrations/openai)

---

### 🧠 **Anthropic Claude**

Advanced reasoning models with excellent tool calling capabilities.

**Setup:**

```bash
export ANTHROPIC_API_KEY="your-anthropic-key"
```

**Popular Models:**

- `anthropic/claude-3-5-sonnet-20240620` - Latest and most capable
- `anthropic/claude-3-haiku-20240307` - Fast and efficient
- `anthropic/claude-3-sonnet-20240229` - Balanced performance
- `anthropic/claude-3-opus-20240229` - Maximum reasoning capability

**Features:**

- Multimodal support (images, PDFs)
- Advanced tool calling
- Streaming responses
- Parallel tool execution

**Example Usage:**

```python
@Nodes.llm(model="anthropic/claude-3-haiku-20240307", output="analysis")
async def analyze_document(content: str):
    return f"Analyze this document: {content}"
```

📖 **Documentation:** [Instructor Anthropic Guide](https://python.useinstructor.com/integrations/anthropic)

---

### 🌐 **Google Gemini**

Google's multimodal AI models with excellent reasoning capabilities.

**Setup:**

```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

**Popular Models:**

- `google/gemini-1.5-flash` - Latest and fastest
- `google/gemini-1.5-pro` - Best for complex reasoning
- `google/gemini-1.0-pro` - Previous generation

**Features:**

- Multimodal capabilities
- Function calling
- Streaming support
- JSON mode

**Example Usage:**

```python
@Nodes.llm(model="google/gemini-1.5-flash", output="summary")
async def summarize_document(content: str):
    return f"Summarize this document in 3 bullet points: {content}"
```

📖 **Documentation:** [Instructor Gemini Guide](https://python.useinstructor.com/integrations/google)

---

### 🏠 **Ollama (Local Models)**

Run powerful open-source models locally for privacy and cost control.

**Setup:**

```bash
# 1. Install Ollama: https://ollama.ai/download
# 2. Start the server
ollama serve

# 3. Pull a model (optional, auto-pulled on first use)
ollama pull llama3.2
```

**Popular Models:**

- `ollama/llama3.2` - Meta's latest model
- `ollama/mistral` - Excellent for code and reasoning
- `ollama/codellama` - Specialized for programming
- `ollama/nous-hermes` - Great instruction following

**Example Usage:**

```python
@Nodes.llm(model="ollama/llama3.2", output="code", api_base="http://localhost:11434")
async def generate_code(requirements: str):
    return f"Write Python code for: {requirements}"
```

📖 **Documentation:** [Instructor Ollama Guide](https://python.useinstructor.com/integrations/ollama)

---

### ⚡ **Groq (Fast Inference)**

Ultra-fast inference with Llama models optimized for speed.

**Setup:**

```bash
export GROQ_API_KEY="your-groq-key"
```

**Popular Models:**

- `groq/llama3-70b-8192` - Large context window
- `groq/llama3-8b-8192` - Fast and efficient
- `groq/mixtral-8x7b-32768` - Mixture of experts

**Features:**

- Extremely fast inference
- Large context windows
- Tool calling support

**Example Usage:**

```python
@Nodes.llm(model="groq/llama3-8b-8192", output="response")
async def quick_analysis(text: str):
    return f"Quick analysis: {text}"
```

📖 **Documentation:** [Instructor Groq Guide](https://python.useinstructor.com/integrations/groq)

---

### 🌪️ **Mistral AI**

European AI models with strong performance and reasoning capabilities.

**Setup:**

```bash
export MISTRAL_API_KEY="your-mistral-key"
```

**Popular Models:**

- `mistral/mistral-large-latest` - Latest large model
- `mistral/mistral-small` - Fast and efficient
- `mistral/mistral-medium` - Balanced performance

**Features:**

- Function calling
- Streaming support
- PDF processing

**Example Usage:**

```python
@Nodes.llm(model="mistral/mistral-large-latest", output="analysis")
async def analyze_text(text: str):
    return f"Analyze this text: {text}"
```

📖 **Documentation:** [Instructor Mistral Guide](https://python.useinstructor.com/integrations/mistral)

---

### 🔥 **Fireworks AI**

High-performance inference with optimized models.

**Setup:**

```bash
export FIREWORKS_API_KEY="your-fireworks-key"
```

**Popular Models:**

- `fireworks/llama-v3-70b-instruct` - Llama 3 optimized
- `fireworks/mixtral-8x7b-instruct` - Mixture of experts

**Example Usage:**

```python
@Nodes.llm(model="fireworks/llama-v3-70b-instruct", output="response")
async def generate_response(prompt: str):
    return f"Generate response for: {prompt}"
```

📖 **Documentation:** [Instructor Fireworks Guide](https://python.useinstructor.com/integrations/fireworks)

---

### 🚀 **Together AI**

Access to a wide variety of open-source models.

**Setup:**

```bash
export TOGETHER_API_KEY="your-together-key"
```

**Popular Models:**

- `together/llama-2-70b-chat` - Popular Llama model
- `together/mistral-7b-instruct-v0.1` - Mistral optimized

**Example Usage:**

```python
@Nodes.llm(model="together/llama-2-70b-chat", output="response")
async def chat_response(message: str):
    return f"Respond to: {message}"
```

📖 **Documentation:** [Instructor Together Guide](https://python.useinstructor.com/integrations/together)

---

### 🧠 **Cerebras**

High-performance AI inference with Cerebras wafers.

**Setup:**

```bash
export CEREBRAS_API_KEY="your-cerebras-key"
```

**Popular Models:**

- `cerebras/llama3.1-70b` - Optimized Llama 3.1
- `cerebras/llama3.1-8b` - Fast inference

**Example Usage:**

```python
@Nodes.llm(model="cerebras/llama3.1-70b", output="analysis")
async def analyze_content(content: str):
    return f"Analyze: {content}"
```

📖 **Documentation:** [Instructor Cerebras Guide](https://python.useinstructor.com/integrations/cerebras)

---

### 📝 **Writer**

Specialized models for content generation and editing.

**Setup:**

```bash
export WRITER_API_KEY="your-writer-key"
```

**Popular Models:**

- `writer/palmyra-x-004` - Content generation
- `writer/palmyra-large` - Large context model

**Example Usage:**

```python
@Nodes.llm(model="writer/palmyra-x-004", output="content")
async def generate_content(topic: str):
    return f"Generate content about: {topic}"
```

📖 **Documentation:** [Instructor Writer Guide](https://python.useinstructor.com/integrations/writer)

---

### 🔍 **Perplexity**

AI-powered search and reasoning models.

**Setup:**

```bash
export PERPLEXITY_API_KEY="your-perplexity-key"
```

**Popular Models:**

- `perplexity/sonar-small` - Fast search
- `perplexity/sonar-medium` - Balanced performance

**Example Usage:**

```python
@Nodes.llm(model="perplexity/sonar-medium", output="search_results")
async def search_topic(query: str):
    return f"Search for: {query}"
```

📖 **Documentation:** [Instructor Perplexity Guide](https://python.useinstructor.com/integrations/perplexity)

---

### 🌐 **Cohere**

Canadian AI models with strong language understanding.

**Setup:**

```bash
export COHERE_API_KEY="your-cohere-key"
```

**Popular Models:**

- `cohere/command-r` - Latest command model
- `cohere/command-r-plus` - Enhanced version

**Example Usage:**

```python
@Nodes.llm(model="cohere/command-r", output="response")
async def cohere_response(prompt: str):
    return f"Respond to: {prompt}"
```

📖 **Documentation:** [Instructor Cohere Guide](https://python.useinstructor.com/integrations/cohere)

---

### 🔷 **Azure OpenAI**

Enterprise-grade OpenAI models with enhanced security and compliance.

**Setup:**

```bash
export AZURE_API_KEY="your-azure-api-key"
export AZURE_API_BASE="https://your-resource.openai.azure.com/"
export AZURE_API_VERSION="2024-02-15-preview"
```

**Model Format:**
Use `azure/<your-deployment-name>` format.

**Example Usage:**

```python
@Nodes.llm(model="azure/gpt-4o-deployment", output="analysis")
async def enterprise_analysis(data: str):
    return f"Provide enterprise-grade analysis of: {data}"
```

📖 **Documentation:** [Instructor Azure Guide](https://python.useinstructor.com/integrations/azure)

---

### ☁️ **AWS Bedrock**

Amazon's managed service for foundation models with enterprise security.

**Setup:**

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION_NAME="us-east-1"
```

**Popular Models:**

- `bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0` - Claude 3.5 Sonnet
- `bedrock/meta.llama3-70b-instruct-v1:0` - Llama 3 70B
- `bedrock/amazon.titan-text-express-v1` - Amazon Titan

**Example Usage:**

```python
@Nodes.llm(model="bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0", output="response")
async def bedrock_analysis(prompt: str):
    return f"Enterprise analysis: {prompt}"
```

📖 **Documentation:** [Instructor Bedrock Guide](https://python.useinstructor.com/integrations/bedrock)

---

### 🌐 **VertexAI**

Google Cloud's AI platform with Gemini and other foundation models.

**Setup:**

```bash
# Method 1: Service Account
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export VERTEXAI_PROJECT="your-project-id"
export VERTEXAI_LOCATION="us-central1"

# Method 2: gcloud CLI
gcloud auth application-default login
```

**Popular Models:**

- `vertexai/gemini-1.5-pro` - Advanced Gemini Pro
- `vertexai/claude-3-5-sonnet@20240620` - Claude on Vertex
- `vertexai/meta/llama3-405b-instruct-maas` - Llama 3 405B

**Example Usage:**

```python
@Nodes.llm(model="vertexai/gemini-1.5-pro", output="response")
async def vertex_analysis(data: str):
    return f"Analyze with VertexAI: {data}"
```

📖 **Documentation:** [Instructor VertexAI Guide](https://python.useinstructor.com/integrations/vertex)

---

### 🖥️ **LM Studio**

Desktop application for running local LLMs with a user-friendly interface.

**Setup:**

```bash
# 1. Download and install LM Studio: https://lmstudio.ai/
# 2. Start the local server from LM Studio
export LM_STUDIO_API_BASE="http://localhost:1234"
# No API key needed for local server
```

**Example Usage:**

```python
@Nodes.llm(model="lm_studio/your-model-name", output="response")
async def local_chat(message: str):
    return f"Chat with local model: {message}"
```

📖 **Documentation:** [Instructor LM Studio Guide](https://docs.litellm.ai/docs/providers/lm_studio)

---

### 🔄 **OpenRouter**

Unified API for accessing multiple providers through a single endpoint.

**Setup:**

```bash
export OPENROUTER_API_KEY="your-openrouter-key"
```

**Popular Models:**

- `openrouter/anthropic/claude-3.5-sonnet` - Claude via OpenRouter
- `openrouter/openai/gpt-4o` - GPT-4 via OpenRouter
- `openrouter/google/gemini-pro` - Gemini via OpenRouter

**Example Usage:**

```python
@Nodes.llm(model="openrouter/anthropic/claude-3.5-sonnet", output="response")
async def routed_response(prompt: str):
    return f"Generate response: {prompt}"
```

📖 **Documentation:** [Instructor OpenRouter Guide](https://python.useinstructor.com/integrations/openrouter)

---

### 🏭 **Anyscale**

Ray-based distributed computing for large-scale AI workloads.

**Setup:**

```bash
export ANYSCALE_API_KEY="your-anyscale-key"
```

**Popular Models:**

- `anyscale/llama-2-70b` - Distributed Llama
- `anyscale/mistral-7b` - Distributed Mistral

**Example Usage:**

```python
@Nodes.llm(model="anyscale/llama-2-70b", output="analysis")
async def distributed_analysis(data: str):
    return f"Analyze at scale: {data}"
```

📖 **Documentation:** [Instructor Anyscale Guide](https://python.useinstructor.com/integrations/anyscale)

---

### 🌊 **SambaNova**

Specialized AI hardware and software for efficient inference.

**Setup:**

```bash
export SAMBANOVA_API_KEY="your-sambanova-key"
```

**Popular Models:**

- `sambanova/llama-2-70b` - Optimized Llama
- `sambanova/mistral-7b` - Optimized Mistral

**Example Usage:**

```python
@Nodes.llm(model="sambanova/llama-2-70b", output="response")
async def optimized_response(prompt: str):
    return f"Optimized response: {prompt}"
```

📖 **Documentation:** [Instructor SambaNova Guide](https://python.useinstructor.com/integrations/sambanova)

---

### 🏢 **TrueFoundry**

Enterprise AI platform for deploying and managing ML models.

**Setup:**

```bash
export TRUEFOUNDRY_API_KEY="your-truefoundry-key"
```

**Example Usage:**

```python
@Nodes.llm(model="truefoundry/your-model", output="response")
async def enterprise_response(prompt: str):
    return f"Enterprise response: {prompt}"
```

📖 **Documentation:** [Instructor TrueFoundry Guide](https://python.useinstructor.com/integrations/truefoundry)

---

### 🏗️ **Databricks**

Unified analytics platform with AI capabilities.

**Setup:**

```bash
export DATABRICKS_TOKEN="your-databricks-token"
export DATABRICKS_HOST="your-databricks-host"
```

**Example Usage:**

```python
@Nodes.llm(model="databricks/your-model", output="response")
async def analytics_response(prompt: str):
    return f"Analytics response: {prompt}"
```

📖 **Documentation:** [Instructor Databricks Guide](https://python.useinstructor.com/integrations/databricks)

---

### 🧊 **Cortex**

Snowflake's AI platform for enterprise applications.

**Setup:**

```bash
export CORTEX_API_KEY="your-cortex-key"
```

**Example Usage:**

```python
@Nodes.llm(model="cortex/your-model", output="response")
async def snowflake_response(prompt: str):
    return f"Snowflake response: {prompt}"
```

📖 **Documentation:** [Instructor Cortex Guide](https://python.useinstructor.com/integrations/cortex)

---

### 🤖 **xAI**

Elon Musk's AI company focused on understanding the universe.

**Setup:**

```bash
export XAI_API_KEY="your-xai-key"
```

**Popular Models:**

- `xai/grok-1` - Grok model
- `xai/grok-beta` - Latest Grok version

**Example Usage:**

```python
@Nodes.llm(model="xai/grok-beta", output="response")
async def grok_response(prompt: str):
    return f"Grok response: {prompt}"
```

📖 **Documentation:** [Instructor xAI Guide](https://python.useinstructor.com/integrations/xai)

---

### 🔍 **DeepSeek**

Chinese AI company focused on advanced reasoning models.

**Setup:**

```bash
export DEEPSEEK_API_KEY="your-deepseek-key"
```

**Popular Models:**

- `deepseek/deepseek-chat` - Chat model
- `deepseek/deepseek-coder` - Code-focused model

**Example Usage:**

```python
@Nodes.llm(model="deepseek/deepseek-chat", output="response")
async def deepseek_response(prompt: str):
    return f"DeepSeek response: {prompt}"
```

📖 **Documentation:** [Instructor DeepSeek Guide](https://python.useinstructor.com/integrations/deepseek)

---

## 🚀 **Quick Model Comparison**

| Provider | Best For | Speed | Cost | Key Features |
|----------|----------|-------|------|--------------|
| **OpenAI** | General purpose, reliable | Medium | $$$ | Best overall performance |
| **Anthropic** | Reasoning, tool calling | Medium | $$$ | Excellent reasoning, multimodal |
| **Google Gemini** | Multimodal, fast | Fast | $$ | Great multimodal, streaming |
| **Groq** | Speed-critical tasks | Very Fast | $$ | Ultra-fast inference |
| **Mistral** | European compliance | Medium | $$ | Strong performance, European |
| **Ollama** | Privacy, local | Variable | Free | Local models, privacy |
| **Fireworks** | Performance | Fast | $$ | Optimized inference |
| **Together** | Open-source variety | Medium | $$ | Many open-source models |
| **Azure** | Enterprise compliance | Medium | $$$ | Enterprise security |
| **Bedrock** | AWS ecosystem | Medium | $$$ | AWS integration |
| **VertexAI** | Google Cloud | Medium | $$ | GCP integration |

## 💡 **Pro Tips**

1. **Environment Variables**: Store API keys in `.env` files for security
2. **Model Fallbacks**: Use different providers as backups for reliability
3. **Cost Optimization**: Start with smaller models like `openai/gpt-4o-mini` or `google/gemini-1.5-flash`
4. **Local Development**: Use Ollama for development to avoid API costs
5. **Production**: Consider enterprise providers (Azure, Bedrock, VertexAI) for production workloads
6. **Streaming**: Use Instructor's streaming features for real-time applications
7. **Structured Outputs**: Leverage Pydantic models for type-safe responses

## 🔗 **Additional Resources**

- **Instructor Documentation**: [https://python.useinstructor.com/](https://python.useinstructor.com/)
- **Provider Comparison**: [Instructor Integrations](https://python.useinstructor.com/integrations/)
- **Model Pricing**: Compare pricing across providers
- **Error Handling**: Instructor provides automatic retries and validation
- **Migration Guide**: [From LiteLLM to Instructor](./specs/instructor_integration_analysis.md)

> **Need Help?** Check the main README [Troubleshooting](./README.md#troubleshooting) section or visit our [Community](https://discord.gg/quantalogic) for support.
