# Quantalogic Agent Configuration YAML Format

This document describes the YAML configuration format for the `AgentConfig` class in the Quantalogic framework, used to configure an AI agent’s behavior, tools, and components. The configuration is flexible, supporting both simple setups and advanced customizations, and is fully backward-compatible with earlier versions.

## Overview

The YAML configuration file defines the settings for an `Agent` instance, controlling aspects such as the language model, task-solving parameters, tool usage, and agent personality. You can provide this configuration via a file (passed as a string to `Agent`) or directly as arguments to `AgentConfig`. All fields are optional unless specified, with sensible defaults ensuring compatibility with minimal setups.

### Example Minimal Configuration
```yaml
model: "gemini/gemini-2.0-flash"
max_iterations: 5
name: "MathBot"
personality: "witty"
```

### Example Advanced Configuration
```yaml
name: "EquationSolver"
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

Below is a detailed breakdown of each field in the YAML configuration, including the new `name` field.

---

### `name`
- **Description**: A unique identifier or nickname for the agent, included in the system prompt to personalize its identity.
- **Type**: String (optional)
- **Default**: `null`
- **Example**:
  ```yaml
  name: "MathBot"
  ```
- **Notes**: If provided, the agent introduces itself with this name in the system prompt (e.g., "I am MathBot, an AI assistant.").

---

### `model`
- **Description**: Specifies the language model used by the agent for reasoning and text generation. Must be compatible with the `litellm` library.
- **Type**: String
- **Default**: `"gemini/gemini-2.0-flash"`
- **Example**:
  ```yaml
  model: "deepseek/deepseek-chat"
  ```

---

### `max_iterations`
- **Description**: Sets the maximum number of reasoning steps the agent will take to solve a task using the ReAct framework.
- **Type**: Integer
- **Default**: `5`
- **Example**:
  ```yaml
  max_iterations: 10
  ```

---

### `tools`
- **Description**: A list of pre-instantiated tools (as Python objects) to include in the agent. Typically used programmatically rather than in YAML.
- **Type**: List of `Tool` or callable objects (optional)
- **Default**: `null`
- **Example** (Programmatic):
  ```python
  config = AgentConfig(tools=[my_custom_tool])
  ```

---

### `max_history_tokens`
- **Description**: Limits the number of tokens stored in the agent’s history, affecting memory usage and context retention.
- **Type**: Integer
- **Default**: `8000` (from `MAX_HISTORY_TOKENS`)
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

---

### `reasoner_name` (Legacy)
- **Description**: Specifies the name of the reasoner plugin to use (older format, kept for compatibility).
- **Type**: String
- **Default**: `"default"`
- **Example**:
  ```yaml
  reasoner_name: "advanced_reasoner"
  ```

---

### `executor_name` (Legacy)
- **Description**: Specifies the name of the executor plugin to use (older format, kept for compatibility).
- **Type**: String
- **Default**: `"default"`
- **Example**:
  ```yaml
  executor_name: "secure_executor"
  ```

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
  - Simple:
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
  - Simple:
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
  - Additional key-value pairs: Properties to set on the tool (e.g., `config`, `precision`).
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

---

### `profile`
- **Description**: Selects a predefined agent profile, setting defaults for other fields.
- **Type**: String (optional)
- **Default**: `null`
- **Supported Profiles**:
  - `"math_expert"`: Configures for mathematical tasks.
  - `"creative_writer"`: Configures for creative tasks.
- **Example**:
  ```yaml
  profile: "math_expert"
  ```

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
(unchanged from previous documentation, included for completeness)

---

## Backward Compatibility

The updated configuration format remains fully compatible with older versions:
- **New Field (`name`)**: Optional, defaults to `null`, so existing configs without `name` work unchanged.
- **Legacy Fields**: `reasoner_name`, `executor_name`, `personality` (string), and `backstory` (string) are still supported.
- **Minimal Configs**: A simple config like:
  ```yaml
  model: "gemini/gemini-2.0-flash"
  ```
  functions as before.

---

## Usage

### Example with Name
```yaml
name: "MathWizard"
model: "gemini/gemini-2.0-flash"
max_iterations: 5
profile: "math_expert"
```

The agent will introduce itself as: "I am MathWizard, an AI assistant with the following personality traits: precise, logical."

---

## Best Practices

- **Use `name`**: Assign a unique name to distinguish agents in multi-agent setups or logs.
- **Profiles**: Leverage `profile` for quick setup, refining with `customizations`.
- **Secrets**: Use `{{ env.VAR_NAME }}` for sensitive data in `tools_config`.

