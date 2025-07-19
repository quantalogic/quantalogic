# Quantalogic Flow YAML DSL Specification 🚀

## 1. Introduction 🌟

The **Quantalogic Flow YAML DSL** is a human-readable, declarative language for defining workflows within the `quantalogic_flow` Python package. Based on the current codebase analysis, it provides comprehensive features for workflow automation:

- **Function Execution** ⚙️: Run async Python functions from embedded code or external modules (PyPI, local files, URLs).
- **Execution Flow** ➡️: Support sequential, conditional, parallel, and branching transitions.
- **Sub-Workflows** 🌳: Enable hierarchical, modular designs.
- **LLM Integration** 🤖: Harness Large Language Models for text or structured outputs with dynamic model selection.
- **Template Nodes** 📝: Render dynamic content with Jinja2 templates.
- **Input Mapping** 🔗: Flexibly map node parameters to context or custom logic (including lambda expressions).
- **Context Management** 📦: Share state dynamically across nodes.
- **Robustness** 🛡️: Include retries, delays, and timeouts.
- **Observers** 👀: Monitor execution with custom event handlers.
- **Validation** 🕵️: Comprehensive workflow validation including circular dependency detection.

This DSL integrates with `Workflow`, `WorkflowEngine`, and `Nodes` classes, making it versatile for everything from simple scripts to complex AI-driven workflows.

---

## 2. Workflow Structure 🗺️

A workflow YAML file comprises these core sections:

```yaml
functions:
  # Python function definitions (embedded or external)
nodes:
  # Task specifications with comprehensive configuration
workflow:
  # Flow orchestration with transitions and control logic
dependencies:
  # Python module dependencies (optional)
observers:
  # Event monitoring functions (optional)
```

---

## 3. Functions ⚙️

The `functions` section defines reusable Python code that can be called by nodes.

### Fields 📋

- `type` (string, required): Must be `"embedded"` or `"external"`.
- `code` (string, optional): Inline Python code for `embedded` functions.
- `module` (string, optional): Source module for `external` functions (PyPI package, file path, or URL).
- `function` (string, optional): Function name within the module for `external` functions.

### Rules ✅

- **Embedded functions**: Must include `code` field, no `module` or `function` fields.
- **External functions**: Must include both `module` and `function` fields, no `code` field.
- Function names in YAML must match the actual function names in the code.

### Examples 🌈

**Embedded function:**
```yaml
functions:
  process_data:
    type: embedded
    code: |
      async def process_data(data: str) -> str:
          return data.upper()
```

**External function:**
```yaml
functions:
  fetch_data:
    type: external
    module: requests
    function: get
```

---

## 4. Nodes 🧩

Nodes define the computational tasks in your workflow. Each node can be one of four types:

### Node Types

1. **Function nodes**: Execute Python functions
2. **LLM nodes**: Use Large Language Models
3. **Template nodes**: Apply Jinja2 templates
4. **Sub-workflow nodes**: Execute nested workflows

### Fields 📋

- `function` (string, optional): Reference to a function in the `functions` section
- `llm_config` (object, optional): LLM configuration for AI-powered nodes
- `template_config` (object, optional): Template configuration for formatting nodes
- `sub_workflow` (object, optional): Sub-workflow definition
- `inputs_mapping` (object, optional): Map node inputs to context keys or lambda expressions
- `output` (string, optional): Context key for storing the node's result
- `retries` (integer, default: 3): Number of retry attempts on failure
- `delay` (float, default: 1.0): Delay between retries in seconds
- `timeout` (float, optional): Maximum execution time in seconds
- `parallel` (boolean, default: false): Whether this node can run in parallel

### Rules ✅

- Exactly one of `function`, `llm_config`, `template_config`, or `sub_workflow` must be specified
- `inputs_mapping` can reference context keys directly or use lambda expressions as strings
- LLM and template node inputs are derived from templates but can be overridden by `inputs_mapping`

### Examples 🌈

**Function node:**
```yaml
nodes:
  process:
    function: process_data
    inputs_mapping:
      data: "raw_input"
    output: processed_result
```

**LLM node:**
```yaml
nodes:
  generate_story:
    llm_config:
      model: "gemini/gemini-2.0-flash"
      system_prompt: "You are a creative writer."
      prompt_template: "Write a {{ genre }} story about {{ topic }}."
      temperature: 0.7
      max_tokens: 2000
    inputs_mapping:
      genre: "story_genre"
      topic: "story_topic"
    output: story_content
```

**Template node:**
```yaml
nodes:
  format_output:
    template_config:
      template: "Result: {{ data }}\nProcessed at: {{ timestamp }}"
    inputs_mapping:
      data: "processed_result"
      timestamp: "lambda ctx: datetime.now().isoformat()"
    output: formatted_result
```

---

## 5. LLM Configuration 🤖

LLM nodes support comprehensive configuration for AI model interaction:

### Fields 📋

- `model` (string): Model name or lambda expression for dynamic selection
- `system_prompt` (string, optional): System prompt defining the LLM's role
- `system_prompt_file` (string, optional): Path to Jinja2 template file for system prompt
- `prompt_template` (string): Jinja2 template for user prompt
- `prompt_file` (string, optional): Path to external prompt template file
- `temperature` (float, 0.0-1.0): Controls randomness of output
- `max_tokens` (integer, optional): Maximum response tokens
- `top_p` (float, 0.0-1.0): Nucleus sampling parameter
- `presence_penalty` (float, -2.0-2.0): Penalty for topic repetition
- `frequency_penalty` (float, -2.0-2.0): Penalty for word repetition
- `stop` (list of strings, optional): Stop sequences
- `response_model` (string, optional): Path to Pydantic model for structured output
- `api_key` (string, optional): Custom API key

### Dynamic Model Selection

```yaml
llm_config:
  model: "lambda ctx: ctx.get('model_name', 'gpt-3.5-turbo')"
  prompt_template: "Answer this question: {{ question }}"
```

### Structured Output

```yaml
llm_config:
  model: "gpt-4"
  response_model: "my_models:PersonDetails"
  prompt_template: "Extract person details from: {{ text }}"
```

---

## 6. Template Configuration 📝

Template nodes use Jinja2 for dynamic content generation:

### Fields 📋

- `template` (string): Inline Jinja2 template
- `template_file` (string, optional): Path to external template file

### Example

```yaml
nodes:
  format_report:
    template_config:
      template: |
        # Report: {{ title }}
        
        ## Summary
        {{ summary }}
        
        ## Details
        {% for item in items %}
        - {{ item }}
        {% endfor %}
    inputs_mapping:
      title: "report_title"
      summary: "report_summary"
      items: "report_items"
    output: formatted_report
```

---

## 7. Workflow Structure 🌐

The `workflow` section orchestrates node execution:

### Fields 📋

- `start` (string): Name of the first node to execute
- `transitions` (list): Defines how nodes connect and flow
- `loops` (list): Loop definitions (legacy, use conditions instead)
- `convergence_nodes` (list): Nodes where multiple paths converge

### Transition Structure

Each transition contains:
- `from_node` (string): Source node name
- `to_node` (string): Target node name
- `condition` (string, optional): Lambda expression for conditional transitions

### Examples 🌈

**Sequential workflow:**
```yaml
workflow:
  start: node_a
  transitions:
    - from_node: node_a
      to_node: node_b
    - from_node: node_b
      to_node: node_c
```

**Conditional branching:**
```yaml
workflow:
  start: validate
  transitions:
    - from_node: validate
      to_node: process_success
      condition: "lambda ctx: ctx['validation_result'] == 'valid'"
    - from_node: validate
      to_node: handle_error
      condition: "lambda ctx: ctx['validation_result'] == 'invalid'"
```

**Loop pattern:**
```yaml
workflow:
  start: initialize
  transitions:
    - from_node: initialize
      to_node: process_item
    - from_node: process_item
      to_node: check_complete
    - from_node: check_complete
      to_node: process_item
      condition: "lambda ctx: ctx['current_index'] < ctx['total_items']"
    - from_node: check_complete
      to_node: finalize
      condition: "lambda ctx: ctx['current_index'] >= ctx['total_items']"
```

---

## 8. Input Mapping 🔗

Input mapping allows flexible parameter passing to nodes:

### Mapping Types

1. **Direct context reference**: `"context_key"`
2. **Lambda expression**: `"lambda ctx: expression"`
3. **Static value**: Any JSON-serializable value

### Examples

```yaml
nodes:
  advanced_node:
    llm_config:
      model: "lambda ctx: ctx['selected_model']"
      prompt_template: "Process {{ data }} with style {{ style }}"
    inputs_mapping:
      data: "raw_data"  # Direct reference
      style: "lambda ctx: 'formal' if ctx['is_business'] else 'casual'"  # Lambda
      temperature: 0.5  # Static value
    output: result
```

---

## 9. Observers 👀

Observers monitor workflow execution events:

```yaml
functions:
  log_progress:
    type: embedded
    code: |
      def log_progress(event):
          print(f"[{event.event_type.value}] {event.node_name}")

observers:
  - log_progress
```

**Available event types:**
- `WORKFLOW_STARTED`
- `WORKFLOW_COMPLETED`
- `WORKFLOW_FAILED`
- `NODE_STARTED`
- `NODE_COMPLETED`
- `NODE_FAILED`

---

## 10. Dependencies 🐍

Specify Python packages required by your workflow:

```yaml
dependencies:
  - "requests>=2.25.0"
  - "pandas"
  - "numpy>=1.20.0"
```

---

## 11. Validation 🕵️‍♀️

The workflow engine provides comprehensive validation:

### Validation Features

- **Node connectivity**: Ensures all referenced nodes exist
- **Circular dependencies**: Detects infinite loops
- **Unreachable nodes**: Identifies orphaned nodes
- **Syntax validation**: Checks lambda expression syntax
- **Configuration validation**: Validates LLM and template configs

### Using Validation

```python
from quantalogic_flow.flow.flow_manager import WorkflowManager
from quantalogic_flow.flow.flow_validator import WorkflowValidator

manager = WorkflowManager()
manager.load_from_yaml("workflow.yaml")

validator = WorkflowValidator()
result = validator.validate(manager.workflow)

if not result.is_valid:
    for error in result.errors:
        print(f"Error in {error.node_name}: {error.message}")
```

---

## 12. Complete Example: Story Generator 📖

This example demonstrates a complete workflow with LLM integration, conditional logic, and template formatting:

```yaml
functions:
  update_progress:
    type: embedded
    code: |
      async def update_progress(chapters, chapter_content, completed_chapters):
          updated_chapters = chapters + [chapter_content]
          return {
              "chapters": updated_chapters, 
              "completed_chapters": completed_chapters + 1
          }

  compile_story:
    type: embedded
    code: |
      async def compile_story(title, chapters):
          story = f"# {title}\n\n"
          for i, chapter in enumerate(chapters, 1):
              story += f"## Chapter {i}\n\n{chapter}\n\n"
          return story

nodes:
  generate_title:
    llm_config:
      model: "gemini/gemini-2.0-flash"
      system_prompt: "You are a creative writer specializing in compelling titles."
      prompt_template: "Generate a captivating title for a {{ genre }} story."
      temperature: 0.8
      max_tokens: 50
    inputs_mapping:
      genre: "story_genre"
    output: title

  generate_outline:
    llm_config:
      model: "gemini/gemini-2.0-flash"
      system_prompt: "You are an expert story planner."
      prompt_template: |
        Create a detailed outline for "{{ title }}" - a {{ genre }} story 
        with {{ num_chapters }} chapters.
      temperature: 0.7
      max_tokens: 1000
    inputs_mapping:
      genre: "story_genre"
      num_chapters: "chapter_count"
    output: outline

  write_chapter:
    llm_config:
      model: "gemini/gemini-2.0-flash"
      system_prompt: "You are a skilled storyteller."
      prompt_template: |
        Write chapter {{ chapter_num }} for "{{ title }}".
        Outline: {{ outline }}
        Previous chapters: {{ completed_chapters }}
      temperature: 0.7
      max_tokens: 2000
    inputs_mapping:
      chapter_num: "lambda ctx: ctx['completed_chapters'] + 1"
      completed_chapters: "lambda ctx: len(ctx['chapters'])"
    output: chapter_content

  update_progress:
    function: update_progress
    output: progress_update

  check_completion:
    template_config:
      template: "{{ completed_chapters >= total_chapters }}"
    inputs_mapping:
      completed_chapters: "completed_chapters"
      total_chapters: "chapter_count"
    output: is_complete

  finalize_story:
    function: compile_story
    output: final_story

workflow:
  start: generate_title
  transitions:
    - from_node: generate_title
      to_node: generate_outline
    - from_node: generate_outline
      to_node: write_chapter
    - from_node: write_chapter
      to_node: update_progress
    - from_node: update_progress
      to_node: check_completion
    - from_node: check_completion
      to_node: write_chapter
      condition: "lambda ctx: not ctx['is_complete']"
    - from_node: check_completion
      to_node: finalize_story
      condition: "lambda ctx: ctx['is_complete']"

observers: []
dependencies:
  - "jinja2>=3.0.0"
```

**Usage:**
```python
import asyncio
from quantalogic_flow.flow.flow_manager import WorkflowManager

async def main():
    manager = WorkflowManager()
    manager.load_from_yaml("story_workflow.yaml")
    
    workflow = manager.instantiate_workflow()
    engine = workflow.build()
    
    context = {
        "story_genre": "science fiction",
        "chapter_count": 3,
        "chapters": [],
        "completed_chapters": 0
    }
    
    result = await engine.run(context)
    print(result["final_story"])

asyncio.run(main())
```

---

## 13. WorkflowManager API 🧑‍💻

The `WorkflowManager` class provides programmatic workflow management:

### Core Methods

```python
from quantalogic_flow.flow.flow_manager import WorkflowManager

# Create and configure
manager = WorkflowManager()

# Load from YAML
manager.load_from_yaml("workflow.yaml")

# Save to YAML
manager.save_to_yaml("output.yaml")

# Add nodes programmatically
manager.add_node(
    name="custom_node",
    llm_config={
        "model": "gpt-4",
        "prompt_template": "Process {{ input }}"
    },
    inputs_mapping={"input": "raw_data"},
    output="processed_data"
)

# Set workflow structure
manager.set_start_node("custom_node")
manager.add_transition("custom_node", "next_node")

# Build executable workflow
workflow = manager.instantiate_workflow()
engine = workflow.build()
```

---

## 14. Conversion Tools 🔄

Convert between YAML and Python representations:

### YAML to Python

```python
from quantalogic_flow.flow.flow_generator import generate_executable_script
from quantalogic_flow.flow.flow_manager import WorkflowManager

manager = WorkflowManager()
manager.load_from_yaml("workflow.yaml")
generate_executable_script(manager.workflow, {}, "workflow.py")
```

### Python to YAML

```python
from quantalogic_flow.flow.flow_extractor import extract_workflow_from_file
from quantalogic_flow.flow.flow_manager import WorkflowManager

workflow_def, globals_dict = extract_workflow_from_file("workflow.py")
manager = WorkflowManager(workflow_def)
manager.save_to_yaml("workflow.yaml")
```

---

## 15. Best Practices 🌟

### Performance
- Use `inputs_mapping` to avoid unnecessary context passing
- Set appropriate `timeout` values for long-running operations
- Configure `retries` and `delay` based on operation reliability

### Debugging
- Use observers to monitor execution flow
- Validate workflows before deployment
- Test lambda expressions in isolation

### Maintainability
- Keep templates simple and focused
- Use external template files for complex formatting
- Document lambda expressions with comments
- Group related functions logically

### Error Handling
- Configure appropriate retry policies
- Use validation to catch errors early
- Implement graceful failure paths

---

## 16. Conclusion 🎉

The Quantalogic Flow YAML DSL provides a powerful, flexible foundation for workflow automation. With comprehensive support for LLM integration, template processing, dynamic input mapping, and robust validation, it enables everything from simple data processing pipelines to complex AI-driven applications.

Key advantages:
- **Declarative**: Human-readable workflow definitions
- **Flexible**: Multiple node types and execution patterns
- **Robust**: Built-in validation and error handling
- **Interoperable**: Seamless Python integration
- **Scalable**: Support for complex, hierarchical workflows

Whether you're building content generation systems, data processing pipelines, or AI-powered applications, the Quantalogic Flow YAML DSL provides the tools you need for efficient, maintainable workflow automation. 🚀
