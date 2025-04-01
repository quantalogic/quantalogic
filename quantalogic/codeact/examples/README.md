# Quantalogic Agent Configuration YAML Format

This document describes the YAML configuration format for the `AgentConfig` class in the Quantalogic framework, used to configure an AI agent’s behavior, tools, and components. The configuration is flexible, supporting both simple setups and advanced customizations, and is fully backward-compatible with earlier versions.

## Overview

The YAML configuration file defines the settings for an `Agent` instance, controlling aspects such as the language model, task-solving parameters, tool usage, and agent personality. You can provide this configuration via a file (passed as a string to `Agent`) or directly as arguments to `AgentConfig`. All fields are optional unless specified, with sensible defaults ensuring compatibility with minimal setups.

### Example Minimal Configuration
```yaml
model: "gemini/gemini-2.0-flash"
max_iterations: 5
personality: "witty"
```

### Example Advanced Configuration
```yaml
model: "deepseek/deepseek-chat"
max_iterations: 5
max_history_tokens: 2000
profile: "math_expert"
customizations:
  personality:
    traits:
      - "witty"
tools_config:
  - name: "math_tools"
    enabled: true
    config:
      precision: "high"
      api_key: "{{ env.MATH_API_KEY }}"
reasoner:
  name: "default"
  config:
    temperature: 0.7
executor:
  name: "default"
  config:
    timeout: 300
sop: |
  Always provide clear, concise answers.
  Prioritize mathematical accuracy.
```

## Configuration Fields

Below is a detailed breakdown of each field in the YAML configuration, including its purpose, type, default value, and usage examples.

---

### `model`
- **Description**: Specifies the language model used by the agent for reasoning and text generation. Must be compatible with the `litellm` library.
- **Type**: String
- **Default**: `"gemini/gemini-2.0-flash"`
- **Example**:
  ```yaml
  model: "deepseek/deepseek-chat"
  ```
- **Notes**: This is the primary model for all agent operations unless overridden by specific tools (e.g., `agent_tool`).

---

### `max_iterations`
- **Description**: Sets the maximum number of reasoning steps the agent will take to solve a task using the ReAct framework.
- **Type**: Integer
- **Default**: `5`
- **Example**:
  ```yaml
  max_iterations: 10
  ```
- **Notes**: Higher values allow more complex problem-solving but increase computation time.

---

### `tools`
- **Description**: A list of pre-instantiated tools (as Python objects) to include in the agent. Typically used programmatically rather than in YAML.
- **Type**: List of `Tool` or callable objects (optional)
- **Default**: `null`
- **Example** (Programmatic, not typical in YAML):
  ```python
  config = AgentConfig(tools=[my_custom_tool])
  ```
- **Notes**: For YAML, prefer `enabled_toolboxes` or `tools_config` to specify tools declaratively.

---

### `max_history_tokens`
- **Description**: Limits the number of tokens stored in the agent’s history, affecting memory usage and context retention.
- **Type**: Integer
- **Default**: `8000` (from `MAX_HISTORY_TOKENS` in `constants.py`)
- **Example**:
  ```yaml
  max_history_tokens: 4000
  ```

---

### `toolbox_directory`
- **Description**: Directory where custom toolbox modules are stored (used for local tool development).
- **Type**: String
- **Default**: `"toolboxes"`
- **Example**:
  ```yaml
  toolbox_directory: "custom_tools"
  ```
- **Notes**: Rarely changed unless integrating local toolsets.

---

### `enabled_toolboxes`
- **Description**: A list of toolbox names to load from registered entry points (e.g., installed Python packages).
- **Type**: List of strings (optional)
- **Default**: `null`
- **Example**:
  ```yaml
  enabled_toolboxes:
    - "math_tools"
    - "text_tools"
  ```
- **Notes**: Compatible with older configs; overridden by `tools_config` if specified.

---

### `reasoner_name` (Legacy)
- **Description**: Specifies the name of the reasoner plugin to use (older format, kept for compatibility).
- **Type**: String
- **Default**: `"default"`
- **Example**:
  ```yaml
  reasoner_name: "advanced_reasoner"
  ```
- **Notes**: Prefer the `reasoner` field for new configurations.

---

### `executor_name` (Legacy)
- **Description**: Specifies the name of the executor plugin to use (older format, kept for compatibility).
- **Type**: String
- **Default**: `"default"`
- **Example**:
  ```yaml
  executor_name: "secure_executor"
  ```
- **Notes**: Prefer the `executor` field for new configurations.

---

### `personality`
- **Description**: Defines the agent’s personality, influencing its system prompt. Can be a simple string (legacy) or a structured dictionary.
- **Type**: String or Dictionary (optional)
- **Default**: `null`
- **Subfields (when dictionary)**:
  - `traits`: List of personality traits (e.g., "witty", "helpful").
  - `tone`: Tone of responses (e.g., "formal", "casual").
  - `humor_level`: Level of humor (e.g., "low", "medium", "high").
- **Examples**:
  - Simple (legacy):
    ```yaml
    personality: "witty"
    ```
  - Structured:
    ```yaml
    personality:
      traits:
        - "witty"
        - "helpful"
      tone: "informal"
      humor_level: "medium"
    ```
- **Notes**: String format remains supported for backward compatibility.

---

### `backstory`
- **Description**: Provides a backstory for the agent, included in the system prompt. Can be a string (legacy) or a dictionary.
- **Type**: String or Dictionary (optional)
- **Default**: `null`
- **Subfields (when dictionary)**:
  - `origin`: Where the agent was created.
  - `purpose`: The agent’s intended purpose.
  - `experience`: Relevant past experience.
- **Examples**:
  - Simple (legacy):
    ```yaml
    backstory: "A seasoned AI assistant."
    ```
  - Structured:
    ```yaml
    backstory:
      origin: "Created by Quantalogic."
      purpose: "Solve complex problems."
      experience: "Trained on 10,000+ math tasks."
    ```

---

### `sop`
- **Description**: Standard Operating Procedure (SOP) as a multi-line string, guiding the agent’s behavior.
- **Type**: String (optional)
- **Default**: `null`
- **Example**:
  ```yaml
  sop: |
    Always provide clear, concise answers.
    Prioritize accuracy over speed.
  ```

---

### `tools_config`
- **Description**: Configures specific tools or toolboxes, allowing enabling/disabling and setting properties.
- **Type**: List of dictionaries (optional)
- **Default**: `null`
- **Subfields**:
  - `name`: Name of the tool or toolbox (matches `tool.name` or `tool.toolbox_name`).
  - `enabled`: Boolean to include/exclude the tool/toolbox (default: `true`).
  - Any additional key-value pairs: Properties to set on the tool (e.g., `config`, `precision`).
- **Example**:
  ```yaml
  tools_config:
    - name: "math_tools"
      enabled: true
      config:
        precision: "high"
    - name: "agent_tool"
      enabled: false
      model: "custom_model"
  ```
- **Notes**:
  - Properties are applied via `setattr(tool, key, value)`, supporting the hybrid configuration approach.
  - Tools with a `config` parameter receive the `config` dictionary; others use named properties (e.g., `precision`).
  - Secrets like `{{ env.API_KEY }}` are resolved to environment variables.

---

### `reasoner`
- **Description**: Configures the reasoning component, replacing `reasoner_name` with added flexibility.
- **Type**: Dictionary (optional)
- **Default**: `{"name": "default"}`
- **Subfields**:
  - `name`: Name of the reasoner plugin (e.g., `"default"`).
  - `config`: Dictionary of reasoner-specific settings (e.g., `temperature`, `max_tokens`).
- **Example**:
  ```yaml
  reasoner:
    name: "default"
    config:
      temperature: 0.7
      max_tokens: 1500
  ```
- **Notes**: Backward-compatible with `reasoner_name` if `reasoner` is omitted.

---

### `executor`
- **Description**: Configures the execution component, replacing `executor_name`.
- **Type**: Dictionary (optional)
- **Default**: `{"name": "default"}`
- **Subfields**:
  - `name`: Name of the executor plugin (e.g., `"default"`).
  - `config`: Dictionary of executor-specific settings (e.g., `timeout`).
- **Example**:
  ```yaml
  executor:
    name: "default"
    config:
      timeout: 600
  ```
- **Notes**: Backward-compatible with `executor_name` if `executor` is omitted.

---

### `profile`
- **Description**: Selects a predefined agent profile, setting defaults for other fields.
- **Type**: String (optional)
- **Default**: `null`
- **Supported Profiles**:
  - `"math_expert"`: Configures for mathematical tasks (precise/logical personality, math tools).
  - `"creative_writer"`: Configures for creative tasks (expressive personality, text tools).
- **Example**:
  ```yaml
  profile: "math_expert"
  ```
- **Notes**: Can be overridden with `customizations`.

---

### `customizations`
- **Description**: Overrides or extends profile defaults with custom settings.
- **Type**: Dictionary (optional)
- **Default**: `null`
- **Example**:
  ```yaml
  profile: "math_expert"
  customizations:
    personality:
      traits:
        - "witty"
    tools_config:
      - name: "advanced_calculus"
        enabled: true
  ```

---

## Tool Configuration Details

The `tools_config` field is particularly powerful for customizing tool behavior. Tools created with `create_tool` (from `quantalogic.tools.tool`) can receive configuration in two ways:

1. **Via `config` Parameter**:
   - If the tool function has a `config` parameter (e.g., `def my_tool(x, config=None)`), the `config` dictionary from `tools_config` is injected.
   - Example:
     ```yaml
     tools_config:
       - name: "my_tool"
         config:
           mode: "fast"
           limit: 100
     ```

2. **Via Named Parameters**:
   - If the tool function has specific parameters (e.g., `def my_tool(x, mode="slow")`), matching properties (e.g., `mode`) are set on the tool and injected.
   - Example:
     ```yaml
     tools_config:
       - name: "my_tool"
         mode: "fast"
     ```

### Example Tool Function
```python
from quantalogic.tools import create_tool

def calculate(x: float, precision: str = "medium", config: dict = None):
    config = config or {}
    precision = config.get("precision", precision)
    # Use precision in calculation
    return f"Result with {precision} precision"

tool = create_tool(calculate)
```

With this config:
```yaml
tools_config:
  - name: "calculate"
    precision: "high"
    config:
      precision: "high"  # Overrides named parameter if present
```
- The tool receives `precision="high"` either way, ensuring flexibility.

---

## Backward Compatibility

The configuration format maintains full compatibility with older versions:
- **Legacy Fields**: `reasoner_name`, `executor_name`, `personality` (string), and `backstory` (string) are still supported and mapped appropriately.
- **Default Behavior**: If new fields (`tools_config`, `profile`, etc.) are omitted, the agent uses the original defaults (e.g., all tools from `enabled_toolboxes`).
- **Minimal Configs**: A simple config like:
  ```yaml
  model: "gemini/gemini-2.0-flash"
  ```
  works as it did previously.

---

## Usage

### Loading from File
```python
from quantalogic.codeact.agent import Agent
agent = Agent(config="path/to/config.yaml")
```

### Inline Configuration
```python
from quantalogic.codeact.agent import AgentConfig, Agent
config = AgentConfig(
    model="deepseek/deepseek-chat",
    tools_config=[{"name": "math_tools", "config": {"precision": "high"}}]
)
agent = Agent(config=config)
```

### Command Line
```bash
python -m quantalogic.codeact.cli task "solve x^2 = 4" --profile "math_expert" --tools-config '[{"name": "math_tools", "precision": "high"}]'
```

---

## Best Practices

- **Use Profiles**: Start with `profile` for common use cases (e.g., `"math_expert"`) and tweak with `customizations`.
- **Tool Configuration**: Use `tools_config` to fine-tune tools rather than relying solely on `enabled_toolboxes`.
- **Secrets**: Store sensitive data (e.g., API keys) in environment variables and reference them with `{{ env.VAR_NAME }}`.
- **Structured Personality**: Prefer dictionary format for `personality` and `backstory` for richer customization.
