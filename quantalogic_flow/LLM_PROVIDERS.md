# LLM Provider Configuration Guide

This guide provides comprehensive setup instructions for using Quantalogic Flow with various LLM providers through LiteLLM integration.

## Why LiteLLM?

Quantalogic Flow leverages **LiteLLM** for seamless integration with 100+ LLM providers, giving you the flexibility to use any model from any provider with a unified API.

- **Universal API**: One consistent interface for all providers
- **100+ Models**: Support for OpenAI, Anthropic, Google, Meta, Mistral, and more
- **Easy Switching**: Change providers without rewriting code
- **Cost Optimization**: Track usage and costs across providers
- **Reliability**: Built-in retry logic and fallback mechanisms

## Quick Provider Setup

**OpenAI & Compatible APIs**
```bash
export OPENAI_API_KEY="sk-your-openai-key"
# Models: gpt-4o, gpt-4o-mini, gpt-3.5-turbo, etc.
```

**Google Gemini**
```bash
export GEMINI_API_KEY="your-gemini-api-key"
# Models: gemini/gemini-2.0-flash, gemini/gemini-1.5-pro, etc.
```

**Ollama (Local Models)**
```bash
# Start Ollama server first: ollama serve
# No API key needed for local models
# Models: ollama/llama3.2, ollama/mistral, ollama/codellama, etc.
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
- `gpt-4o` - Latest flagship model
- `gpt-4o-mini` - Fast and cost-effective
- `gpt-3.5-turbo` - Legacy but reliable
- `o1-mini` - Reasoning model

**Example Usage:**
```python
from quantalogic_flow import Workflow, Nodes

@Nodes.llm(model="gpt-4o", output="response")
async def analyze_text(text: str):
    return f"Analyze this text: {text}"

workflow = Workflow().add(analyze_text, text="Hello World")
result = await workflow.build().run({})
```

📖 **Documentation:** [LiteLLM OpenAI Guide](https://docs.litellm.ai/docs/providers/openai)

---

### 🧠 **Google Gemini**
Google's advanced multimodal AI models with excellent reasoning capabilities.

**Setup:**
```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

**Popular Models:**
- `gemini/gemini-2.0-flash` - Latest and fastest
- `gemini/gemini-1.5-pro` - Best for complex reasoning
- `gemini/gemini-1.5-flash` - Balanced speed and quality

**Example Usage:**
```python
@Nodes.llm(model="gemini/gemini-2.0-flash", output="summary")
async def summarize_document(content: str):
    return f"Summarize this document in 3 bullet points: {content}"
```

📖 **Documentation:** [LiteLLM Gemini Guide](https://docs.litellm.ai/docs/providers/gemini)

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

📖 **Documentation:** [LiteLLM Ollama Guide](https://docs.litellm.ai/docs/providers/ollama)

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

📖 **Documentation:** [LiteLLM Azure Guide](https://docs.litellm.ai/docs/providers/azure)

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

📖 **Documentation:** [LiteLLM Bedrock Guide](https://docs.litellm.ai/docs/providers/bedrock)

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

📖 **Documentation:** [LiteLLM LM Studio Guide](https://docs.litellm.ai/docs/providers/lm_studio)

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
- `vertex_ai/gemini-1.5-pro` - Advanced Gemini Pro
- `vertex_ai/claude-3-5-sonnet@20240620` - Claude on Vertex
- `vertex_ai/meta/llama3-405b-instruct-maas` - Llama 3 405B

**Example Usage:**
```python
@Nodes.llm(model="vertex_ai/gemini-1.5-pro", output="response")
async def vertex_analysis(data: str):
    return f"Analyze with VertexAI: {data}"
```

📖 **Documentation:** [LiteLLM VertexAI Guide](https://docs.litellm.ai/docs/providers/vertex)

---

### 🔮 **POE (Poe by Quora)**
Access Claude, Gemini, Grok, and other frontier models through POE's unified API.

**API Details:**
- Base URL: `https://api.poe.com/v1`
- Authentication: API key via `POE_API_KEY`
- Compatible with OpenAI API format

**Setup:**
```bash
export POE_API_KEY="your-poe-api-key"
```

**Popular Models:**
- `poe/Claude-Sonnet-4` - Latest Claude Sonnet
- `poe/Claude-Opus-4.1` - Claude Opus 4.1 
- `poe/Claude-Haiku-3.5` - Claude Haiku 3.5
- `poe/Gemini-2.0-Flash` - Latest Gemini Flash
- `poe/Gemini-1.5-Pro` - Gemini 1.5 Pro
- `poe/Grok-4` - Latest Grok model
- `poe/GPT-4o` - OpenAI GPT-4o
- `poe/o3-mini` - OpenAI o3-mini
- `poe/DeepSeek-R1` - DeepSeek R1

**Example Usage:**
```python
@Nodes.llm_node(model="poe/Claude-Sonnet-4", output="analysis")
async def analyze_with_claude(text: str):
    return f"Analyze this text: {text}"
```

📖 **Documentation:** [POE API Documentation](https://developer.poe.com/api-key)

---

## 🚀 **Quick Model Comparison**

| Provider | Best For | Cost | Setup Complexity | Popular Models |
|----------|----------|------|------------------|----------------|
| **OpenAI** | General purpose, reliable | $$$ | Easy | gpt-4o, gpt-4o-mini |
| **Gemini** | Multimodal, reasoning | $$ | Easy | gemini-2.0-flash |
| **Ollama** | Privacy, local inference | Free | Medium | llama3.2, mistral |
| **Azure** | Enterprise compliance | $$$ | Medium | azure/gpt-4o |
| **Bedrock** | AWS ecosystem | $$$ | Medium | claude-3-5-sonnet |
| **LM Studio** | Desktop local models | Free | Easy | Any local model |
| **VertexAI** | Google Cloud integration | $$ | Medium | vertex_ai/gemini-pro |
| **POE** | Multiple frontier models | $$ | Easy | claude-sonnet-4, grok-4 |

## 💡 **Pro Tips**

1. **Environment Variables**: Store API keys in `.env` files for security
2. **Model Fallbacks**: Use different providers as backups for reliability
3. **Cost Optimization**: Start with smaller models like `gpt-4o-mini` or `gemini-flash`
4. **Local Development**: Use Ollama for development to avoid API costs
5. **Production**: Consider enterprise providers (Azure, Bedrock) for production workloads

## 🔗 **Additional Resources**

- **LiteLLM Documentation**: [https://docs.litellm.ai/](https://docs.litellm.ai/)
- **Model Pricing**: [LiteLLM Model Costs](https://docs.litellm.ai/docs/proxy/cost_tracking)
- **Provider Comparison**: [LiteLLM Providers](https://docs.litellm.ai/docs/providers)
- **Error Handling**: [LiteLLM Debugging](https://docs.litellm.ai/docs/debugging/debug_llm_api_calls)

> **Need Help?** Check the main README [Troubleshooting](./README.md#troubleshooting) section or visit our [Community](https://discord.gg/quantalogic) for support.
