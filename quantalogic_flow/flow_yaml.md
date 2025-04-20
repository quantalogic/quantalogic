# Quantalogic Flow YAML DSL Specification 🚀

## 1. Introduction 🌟

The **Quantalogic Flow YAML DSL** is a human-readable, declarative language for defining workflows within the `quantalogic.flow` Python package. As of **March 8, 2025**, it’s packed with features for task automation:

- **Function Execution** ⚙️: Run async Python functions from embedded code, PyPI, local files, or URLs.
- **Execution Flow** ➡️: Support sequential, conditional, parallel, branching, and converging transitions.
- **Sub-Workflows** 🌳: Enable hierarchical, modular designs.
- **LLM Integration** 🤖: Harness Large Language Models for text or structured outputs, with dynamic model selection.
- **Template Nodes** 📝: Render dynamic content with Jinja2 templates.
- **Input Mapping** 🔗: Flexibly map node parameters to context or custom logic (including lambdas).
- **Context Management** 📦: Share state dynamically across nodes.
- **Robustness** 🛡️: Include retries, delays, and timeouts.
- **Observers** 👀: Monitor execution with custom handlers.
- **Programmatic Control** 🧑‍💻: Manage workflows via `WorkflowManager`.

This DSL integrates with `Workflow`, `WorkflowEngine`, and `Nodes` classes, making it versatile for everything from simple scripts to complex AI-driven workflows. We’ll use an updated **Story Generator Workflow** as a running example, derived from `examples/flow/simple_story_generator/story_generator_agent.py`, now enhanced with branching, convergence, input mapping, template nodes, and dynamic model selection. Let’s dive in! 🎉

---

## 2. Workflow Structure 🗺️

A workflow YAML file comprises five core sections:

- **`functions`**: Python code definitions.
- **`nodes`**: Task specifications with input mappings and template support.
- **`workflow`**: Flow orchestration with branching and convergence.
- **`dependencies`**: Python module dependencies.
- **`observers`**: Event monitoring.

Here’s the skeleton:

```yaml
functions:
  # Python magic ✨
nodes:
  # Tasks with input mappings & templates 🎯
workflow:
  # Flow control with branches & convergence 🚦
dependencies:
  # Python module dependencies (optional)
observers:
  # Event watchers 👀 (optional)
```

### 3. LLM Configuration

In the `llm_config` section of a node definition, you can specify a file-based system prompt using the `system_prompt_file` key (takes precedence over `system_prompt`) and a dynamic `model` using a lambda expression (e.g., `"lambda ctx: ctx['model_name']"`). This enhances flexibility for LLM-driven tasks.

Example:

```yaml
llm_config:
  model: "lambda ctx: ctx['model_name']"  # Dynamic model selection
  system_prompt: "You are a creative writer."
  system_prompt_file: "path/to/system_prompt_template.jinja"
  prompt_template: "Write a story about {topic}."
```

### Story Generator Example
We’ll evolve the Story Generator to include branching (based on story tone), convergence (finalizing the story), **input mapping** with lambdas, a **template node** for chapter summaries, and a dynamic `model`—showcasing these shiny new features step-by-step.

---

## 3. Case Study: Story Generator Workflow 📖

### Python Version (`story_generator_agent.py`)

This updated script generates a story with tone-based branching, convergence, input mapping, a template node, and dynamic model selection:

```python
#!/usr/bin/env python
from quantalogic.flow import Nodes, Workflow
import anyio

MODEL = "gemini/gemini-2.0-flash"
DEFAULT_LLM_PARAMS = {"temperature": 0.7, "max_tokens": 1000}

@Nodes.llm_node(system_prompt="You are a creative writer skilled at generating stories.", 
                prompt_template="Create a story outline for a {genre} story with {num_chapters} chapters.", 
                model=lambda ctx: ctx.get("model_name", MODEL),
                output="outline", **DEFAULT_LLM_PARAMS)
async def generate_outline(genre: str, num_chapters: int):
    return ""

@Nodes.llm_node(system_prompt="You are a creative writer.", 
                prompt_template="Analyze the tone of this outline: {outline}.", 
                model=lambda ctx: ctx.get("model_name", MODEL),
                output="tone", **DEFAULT_LLM_PARAMS)
async def analyze_tone(outline: str):
    return ""

@Nodes.llm_node(system_prompt="You are a creative writer.", 
                prompt_template="Write chapter {chapter_num} for this story outline: {outline}. Style: {style}.", 
                model=lambda ctx: ctx.get("model_name", MODEL),
                output="chapter", **DEFAULT_LLM_PARAMS)
async def generate_chapter(outline: str, chapter_num: int, style: str):
    return ""

@Nodes.llm_node(system_prompt="You are a dramatic writer.", 
                prompt_template="Write a dramatic chapter {chapter_num} for this outline: {outline}.", 
                model=lambda ctx: ctx.get("model_name", MODEL),
                output="chapter", **DEFAULT_LLM_PARAMS)
async def generate_dramatic_chapter(outline: str, chapter_num: int):
    return ""

@Nodes.template_node(output="chapter_summary", template="Chapter {chapter_num}: {chapter}")
async def summarize_chapter(rendered_content: str, chapter: str, chapter_num: int):
    return rendered_content

@Nodes.define(output="updated_context")
async def update_progress(**context):
    chapters = context.get('chapters', [])
    completed_chapters = context.get('completed_chapters', 0)
    chapter_summary = context.get('chapter_summary', '')
    updated_chapters = chapters + [chapter_summary]
    return {**context, "chapters": updated_chapters, "completed_chapters": completed_chapters + 1}

@Nodes.define(output="continue_generating")
async def check_if_complete(completed_chapters: int = 0, num_chapters: int = 0, **kwargs):
    return completed_chapters < num_chapters

@Nodes.define(output="final_story")
async def finalize_story(chapters: list):
    return "\n".join(chapters)

workflow = (
    Workflow("generate_outline")
    .node("generate_outline", inputs_mapping={"genre": "story_genre", "num_chapters": "chapter_count"})
    .then("analyze_tone")
    .branch([
        ("generate_chapter", lambda ctx: ctx.get("tone") == "light"),
        ("generate_dramatic_chapter", lambda ctx: ctx.get("tone") == "dark")
    ])
    .then("summarize_chapter")
    .then("update_progress")
    .then("check_if_complete")
    .then("generate_chapter", condition=lambda ctx: ctx.get("continue_generating", False))
    .then("summarize_chapter")
    .then("update_progress")
    .then("check_if_complete")
    .converge("finalize_story")
)

def story_observer(event):
    print(f"Event: {event.event_type.value} - Node: {event.node_name}")
workflow.add_observer(story_observer)

if __name__ == "__main__":
    async def main():
        initial_context = {
            "story_genre": "science fiction",
            "chapter_count": 3,
            "chapters": [],
            "completed_chapters": 0,
            "style": "descriptive",
            "model_name": "gemini/gemini-2.0-flash"  # Dynamic model selection
        }
        engine = workflow.build()
        result = await engine.run(initial_context)
        print(f"Final Story:\n{result.get('final_story', '')}")
    anyio.run(main)
```

### YAML Version (`story_generator_workflow.yaml`)

Here’s the updated YAML with branching, convergence, input mapping with lambdas, a template node, and dynamic model selection:

```yaml
functions:
  update_progress:
    type: embedded
    code: |
      async def update_progress(**context):
          chapters = context.get('chapters', [])
          completed_chapters = context.get('completed_chapters', 0)
          chapter_summary = context.get('chapter_summary', '')
          updated_chapters = chapters + [chapter_summary]
          return {**context, "chapters": updated_chapters, "completed_chapters": completed_chapters + 1}
  check_if_complete:
    type: embedded
    code: |
      async def check_if_complete(completed_chapters=0, num_chapters=0, **kwargs):
          return completed_chapters < num_chapters
  finalize_story:
    type: embedded
    code: |
      async def finalize_story(chapters):
          return "\n".join(chapters)
  story_observer:
    type: embedded
    code: |
      def story_observer(event):
          print(f"Event: {event.event_type.value} - Node: {event.node_name}")

nodes:
  generate_outline:
    llm_config:
      model: "lambda ctx: ctx['model_name']"  # Dynamic model selection
      system_prompt: "You are a creative writer skilled at generating stories."
      system_prompt_file: "path/to/system_prompt_template.jinja"
      prompt_template: "Create a story outline for a {genre} story with {num_chapters} chapters."
      temperature: 0.7
      max_tokens: 1000
    inputs_mapping:
      genre: "story_genre"
      num_chapters: "chapter_count"
    output: outline
  analyze_tone:
    llm_config:
      model: "lambda ctx: ctx['model_name']"  # Dynamic model selection
      system_prompt: "You are a creative writer."
      prompt_template: "Analyze the tone of this outline: {outline}."
      temperature: 0.7
      max_tokens: 1000
    output: tone
  generate_chapter:
    llm_config:
      model: "lambda ctx: ctx['model_name']"  # Dynamic model selection
      system_prompt: "You are a creative writer."
      prompt_template: "Write chapter {chapter_num} for this story outline: {outline}. Style: {style}."
      temperature: 0.7
      max_tokens: 1000
    inputs_mapping:
      chapter_num: "completed_chapters"
      style: "style"
    output: chapter
  generate_dramatic_chapter:
    llm_config:
      model: "lambda ctx: ctx['model_name']"  # Dynamic model selection
      system_prompt: "You are a dramatic writer."
      prompt_template: "Write a dramatic chapter {chapter_num} for this outline: {outline}."
      temperature: 0.7
      max_tokens: 1000
    inputs_mapping:
      chapter_num: "completed_chapters"
    output: chapter
  summarize_chapter:
    template_config:
      template: "Chapter {chapter_num}: {chapter}"
    inputs_mapping:
      chapter_num: "completed_chapters"
    output: chapter_summary
  update_progress:
    function: update_progress
    output: updated_context
  check_if_complete:
    function: check_if_complete
    output: continue_generating
  finalize_story:
    function: finalize_story
    output: final_story

workflow:
  start: generate_outline
  transitions:
    - from_node: generate_outline
      to_node: analyze_tone
    - from_node: analyze_tone
      to_node:
        - to_node: generate_chapter
          condition: "ctx['tone'] == 'light'"
        - to_node: generate_dramatic_chapter
          condition: "ctx['tone'] == 'dark'"
    - from_node: generate_chapter
      to_node: summarize_chapter
    - from_node: generate_dramatic_chapter
      to_node: summarize_chapter
    - from_node: summarize_chapter
      to_node: update_progress
    - from_node: update_progress
      to_node: check_if_complete
    - from_node: check_if_complete
      to_node: generate_chapter
      condition: "ctx['continue_generating']"
  convergence_nodes:
    - finalize_story

observers:
  - story_observer
```

### Mermaid Diagram: Updated Story Generator Flow

```mermaid
graph TD
    A[generate_outline] --> B[analyze_tone]
    B -->|"'light'"| C[generate_chapter]
    B -->|"'dark'"| D[generate_dramatic_chapter]
    C --> E[summarize_chapter]
    D --> E
    E --> F[update_progress]
    F --> G[check_if_complete]
    G -->|"ctx['continue_generating']"| C
    G --> H[finalize_story]
    F --> H
    style A fill:#CE93D8,stroke:#AB47BC,stroke-width:2px  # Purple for LLM
    style B fill:#CE93D8,stroke:#AB47BC,stroke-width:2px  # Purple for LLM
    style C fill:#CE93D8,stroke:#AB47BC,stroke-width:2px  # Purple for LLM
    style D fill:#CE93D8,stroke:#AB47BC,stroke-width:2px  # Purple for LLM
    style E fill:#FCE4EC,stroke:#F06292,stroke-width:2px  # Pink for template
    style F fill:#90CAF9,stroke:#42A5F5,stroke-width:2px  # Blue for function
    style G fill:#90CAF9,stroke:#42A5F5,stroke-width:2px  # Blue for function
    style H fill:#90CAF9,stroke:#42A5F5,stroke-width:2px,stroke-dasharray:5 5  # Blue with dashed for convergence
```

#### Execution
With `initial_context = {"story_genre": "science fiction", "chapter_count": 3, "chapters": [], "completed_chapters": 0, "style": "descriptive", "model_name": "gemini/gemini-2.0-flash"}`:
1. `generate_outline` uses input mapping (`story_genre`, `chapter_count`) and a dynamic `model` to create an outline.
2. `analyze_tone` determines the story’s tone with a dynamic `model`.
3. Branches to `generate_chapter` (light tone) or `generate_dramatic_chapter` (dark tone), mapping `chapter_num` to `completed_chapters`.
4. `summarize_chapter` formats the chapter using a template, mapping `chapter_num`.
5. `update_progress` updates chapters and count with the summary.
6. `check_if_complete` loops back if more chapters are needed.
7. Converges at `finalize_story` to compile the final story.

---

## 4. Functions ⚙️

The `functions` section defines reusable Python code.

### Fields 📋
- `type` (string, required): `"embedded"` or `"external"`.
- `code` (string, optional): Inline code for `embedded`.
- `module` (string, optional): Source for `external` (PyPI, path, URL).
- `function` (string, optional): Function name in `module`.

### Rules ✅
- Embedded: Use `async def` (if async), name matches key.
- External: Requires `module` and `function`, no `code`.

### Examples 🌈
From the story generator:
```yaml
functions:
  finalize_story:
    type: embedded
    code: |
      async def finalize_story(chapters):
          return "\n".join(chapters)
```
External example:
```yaml
functions:
  fetch:
    type: external
    module: requests
    function: get
```

```mermaid
graph TD
    A[Function Definition] --> B{Type?}
    B -->|embedded| C[Code: async def ...]
    B -->|external| D[Module: PyPI, Path, URL]
    D --> E[Function Name]
    style A fill:#e6f3ff,stroke:#0066cc,stroke-width:2px
    style B fill:#fff,stroke:#333
    style C fill:#cce6ff,stroke:#0066cc
    style D fill:#cce6ff,stroke:#0066cc
    style E fill:#cce6ff,stroke:#0066cc
```

---

## 5. Dependencies 🐍

The `dependencies` section lists required Python modules.

### Fields 📋
- `dependencies` (list, optional): PyPI packages (e.g., `requests>=2.28.0`), local paths (e.g., `/path/to/module.py`), or URLs (e.g., `https://example.com/module.py`).

### Example 🌈
```yaml
dependencies:
  - requests>=2.28.0
  - /path/to/my_custom_module.py
  - https://example.com/another_module.py
```

---

## 6. Nodes 🧩

Nodes define tasks, now enhanced with **input mappings** (including lambdas), **template nodes**, and dynamic `model` selection in LLM nodes, alongside functions and sub-workflows.

### Fields 📋
- `function` (string, optional): Links to `functions`.
- `sub_workflow` (object, optional):
  - `start` (string)
  - `transitions` (list)
  - `convergence_nodes` (list, optional)
- `llm_config` (object, optional):
  - `model` (string, default: `"gpt-3.5-turbo"`): Can be a static name or lambda (e.g., `"lambda ctx: ctx['model_name']"`).
  - `system_prompt` (string, optional)
  - `system_prompt_file` (string, optional): Path to a Jinja2 template file (overrides `system_prompt`).
  - `prompt_template` (string, default: `"{{ input }}"`)
  - `prompt_file` (string, optional): Path to a Jinja2 template file (overrides `prompt_template`).
  - `temperature` (float, default: `0.7`)
  - `max_tokens` (int, optional)
  - `top_p` (float, default: `1.0`)
  - `presence_penalty` (float, default: `0.0`)
  - `frequency_penalty` (float, default: `0.0`)
  - `response_model` (string, optional)
- `template_config` (object, optional):
  - `template` (string, default: `""`): Jinja2 template string.
  - `template_file` (string, optional): Path to a Jinja2 template file (overrides `template`).
- `inputs_mapping` (dict, optional): Maps node parameters to context keys or lambda expressions (e.g., `"lambda ctx: ctx['x'] + 1"`).
- `output` (string, optional): Context key for the result.
- `retries` (int, default: `3`)
- `delay` (float, default: `1.0`)
- `timeout` (float/null, default: `null`)
- `parallel` (bool, default: `false`)

### Rules ✅
- Exactly one of `function`, `sub_workflow`, `llm_config`, or `template_config`.
- LLM and template inputs derived from `prompt_template`/`template` or `prompt_file`/`template_file`, overridden by `inputs_mapping`.
- `inputs_mapping` values can be strings (context keys) or serialized lambdas.

### Examples 🌈
Using a template node with an external Jinja2 file:
```yaml
nodes:
  format_report:
    template_config:
      template_file: "templates/report.j2"
    inputs_mapping:
      title: "report_title"
      data: "report_data"
    output: formatted_report
```
(`templates/report.j2`: `Report: {{ title }}\nData: {{ data }}`)

With input mapping, lambda, and dynamic model in an LLM node:
```yaml
nodes:
  generate_outline:
    llm_config:
      model: "lambda ctx: ctx['model_name']"  # Dynamic model selection
      system_prompt: "You are a creative writer skilled at generating stories."
      system_prompt_file: "path/to/system_prompt_template.jinja"
      prompt_template: "Create a story outline for a {genre} story with {num_chapters} chapters."
      temperature: 0.7
      max_tokens: 1000
    inputs_mapping:
      genre: "story_genre"
      num_chapters: "lambda ctx: ctx['chapter_count'] + 1"
    output: outline
```

From the story generator (template node):
```yaml
nodes:
  summarize_chapter:
    template_config:
      template: "Chapter {chapter_num}: {chapter}"
    inputs_mapping:
      chapter_num: "completed_chapters"
    output: chapter_summary
```

```mermaid
graph TD
    A[Node] --> B{Type?}
    B -->|function| C[Function Ref]
    B -->|sub_workflow| D[Start + Transitions + Convergence]
    B -->|llm_config| E[LLM Setup]
    B -->|template_config| F[Template Setup]
    A --> G[Inputs Mapping?]
    G -->|Yes| H[Context Keys or Lambdas]
    E --> I{Structured?}
    I -->|Yes| J[response_model]
    I -->|No| K[Plain Text]
    F --> L[Jinja2 Template]
    E --> M[Dynamic Model?]
    M -->|Yes| N[Lambda Expression]
    style A fill:#e6ffe6,stroke:#009933,stroke-width:2px
    style B fill:#fff,stroke:#333
    style C fill:#ccffcc,stroke:#009933
    style D fill:#ccffcc,stroke:#009933
    style E fill:#ccffcc,stroke:#009933
    style F fill:#ccffcc,stroke:#009933
    style G fill:#fff,stroke:#333
    style H fill:#b3ffb3,stroke:#009933
    style I fill:#fff,stroke:#333
    style J fill:#b3ffb3,stroke:#009933
    style K fill:#b3ffb3,stroke:#009933
    style L fill:#b3ffb3,stroke:#009933
    style M fill:#fff,stroke:#333
    style N fill:#b3ffb3,stroke:#009933
```

---

## 6. Input Mapping with LLM Nodes and Template Nodes 🔗

Input mapping allows flexible parameter passing to nodes, enabling dynamic behavior based on workflow context. This is particularly powerful with LLM nodes (including dynamic models) and template nodes.

### Implementation Details

- **Input Mapping Types**:
  - Direct context references (e.g., `"story_genre"`)
  - Lambda expressions (e.g., `"lambda ctx: ctx['chapter_count'] + 1"`)
  - Static values

- **Supported Node Types**:
  - LLM nodes
  - Template nodes
  - Function nodes
  - Sub-workflow nodes

### LLM Node Input Mapping

LLM nodes support input mapping for prompts and dynamic model selection:

```yaml
nodes:
  generate_outline:
    llm_config:
      model: "lambda ctx: ctx['model_name']"  # Dynamic model selection
      system_prompt: "You are a creative writer skilled in {genre} stories."
      system_prompt_file: "path/to/system_prompt_template.jinja"
      prompt_template: "Create a story outline for a {genre} story with {num_chapters} chapters."
      temperature: 0.7
      max_tokens: 1000
    inputs_mapping:
      genre: "story_genre"  # Map from context
      num_chapters: "lambda ctx: ctx['chapter_count'] + 1"  # Dynamic value
    output: outline
```

### Template Node Input Mapping

Template nodes use mapped inputs in Jinja2 templates:

```yaml
nodes:
  summarize_chapter:
    template_config:
      template: "Chapter {chapter_num}: {chapter}\n\nSummary: {summary}"
    inputs_mapping:
      chapter_num: "current_chapter"
      chapter: "lambda ctx: ctx['chapters'][ctx['current_chapter']]"
      summary: "lambda ctx: ctx['summaries'][ctx['current_chapter']]"
    output: chapter_summary
```

### Combined Example

Here’s an example combining both LLM and template nodes with input mapping:

```yaml
nodes:
  generate_character:
    llm_config:
      model: "lambda ctx: ctx['model_name']"  # Dynamic model selection
      system_prompt: "You are a character designer."
      prompt_template: "Create a character for a {genre} story."
    inputs_mapping:
      genre: "story_genre"
    output: character_description

  format_character:
    template_config:
      template: "Character Profile:\n\n{description}\n\nTraits: {traits}"
    inputs_mapping:
      description: "character_description"
      traits: "lambda ctx: ', '.join(ctx['character_traits'])"
    output: formatted_character
```

### Key Points

- Use `inputs_mapping` to map context values to node parameters.
- Support both direct context references and lambda expressions.
- Works seamlessly with LLM (including dynamic `model`), template, and other node types.
- Enables dynamic, context-aware workflows.
- Input mapping is validated against node parameters.

---

## 7. Workflow 🌐

The `workflow` section orchestrates execution, leveraging branching and convergence.

### Fields 📋
- `start` (string, optional): First node.
- `transitions` (list):
  - `from_node` (string)
  - `to_node` (string or list):
    - String: Sequential or parallel transition.
    - List of objects: Branching with `to_node` and `condition`.
  - `condition` (string, optional): For sequential transitions.
- `convergence_nodes` (list, optional): Nodes where branches merge.

### Example 🌈
From the story generator:
```yaml
workflow:
  start: generate_outline
  transitions:
    - from_node: generate_outline
      to_node: analyze_tone
    - from_node: analyze_tone
      to_node:
        - to_node: generate_chapter
          condition: "ctx['tone'] == 'light'"
        - to_node: generate_dramatic_chapter
          condition: "ctx['tone'] == 'dark'"
    - from_node: generate_chapter
      to_node: summarize_chapter
    - from_node: generate_dramatic_chapter
      to_node: summarize_chapter
    - from_node: summarize_chapter
      to_node: update_progress
    - from_node: update_progress
      to_node: check_if_complete
    - from_node: check_if_complete
      to_node: generate_chapter
      condition: "ctx['continue_generating']"
  convergence_nodes:
    - finalize_story
```

```mermaid
graph TD
    A[Workflow] --> B[Start Node]
    A --> C[Transitions]
    C --> D[From Node]
    D --> E{To Node}
    E -->|Sequential| F[Single Node]
    E -->|Parallel| G[List of Nodes]
    E -->|Branching| H[List with Conditions]
    C --> I[Condition?]
    I -->|Yes| J[ctx-based Logic]
    A --> K[Convergence Nodes]
    K --> L[Merge Points]
    style A fill:#fff0e6,stroke:#cc3300,stroke-width:2px
    style B fill:#ffe6cc,stroke:#cc3300
    style C fill:#ffe6cc,stroke:#cc3300
    style D fill:#ffd9b3,stroke:#cc3300
    style E fill:#fff,stroke:#333
    style F fill:#ffd9b3,stroke:#cc3300
    style G fill:#ffd9b3,stroke:#cc3300
    style H fill:#ffd9b3,stroke:#cc3300
    style I fill:#fff,stroke:#333
    style J fill:#ffd9b3,stroke:#cc3300
    style K fill:#ffe6cc,stroke:#cc3300
    style L fill:#ffd9b3,stroke:#cc3300
```

---

## 8. Workflow Validation 🕵️‍♀️

`validate_workflow_definition()` ensures integrity:
- Checks node connectivity, circular references, undefined nodes, missing start.
- Validates branch conditions, convergence points (at least two incoming transitions), and input mappings (including lambda syntax).
- Returns `NodeError` objects (`node_name`, `description`).

### Example
```python
issues = validate_workflow_definition(workflow)
if issues:
    for issue in issues:
        print(f"Node '{issue.node_name}': {issue.description}")
```

---

## 9. Observers 👀

Monitor events like node starts, completions, or failures.

### Example
From the story generator:
```yaml
observers:
  - story_observer
```

---

## 10. Context 📦

The `ctx` dictionary shares data, enhanced by input mappings:
- `generate_outline` → `ctx["outline"]` (mapped from `story_genre`, `chapter_count`, dynamic `model`)
- `summarize_chapter` → `ctx["chapter_summary"]` (mapped from `completed_chapters`)
- `finalize_story` → `ctx["final_story"]`

---

## 11. Execution Flow 🏃‍♂️

The `WorkflowEngine`:
1. Starts at `workflow.start`.
2. Executes nodes, applying input mappings and updating `ctx`.
3. Follows transitions (sequential, parallel, or branching) based on conditions.
4. Converges at specified nodes.
5. Notifies observers.
6. Ends when transitions are exhausted.

---

## 12. Converting Between Python and YAML 🔄

### Python to YAML (`flow_extractor.py`)
```python
from quantalogic.flow.flow_extractor import extract_workflow_from_file
from quantalogic.flow.flow_manager import WorkflowManager

wf_def, globals = extract_workflow_from_file("story_generator_agent.py")
WorkflowManager(wf_def).save_to_yaml("story_generator_workflow.yaml")
```

### YAML to Python (`flow_generator.py`)
```python
from quantalogic.flow.flow_generator import generate_executable_script

manager = WorkflowManager()
manager.load_from_yaml("story_generator_workflow.yaml")
generate_executable_script(manager.workflow, {}, "standalone_story.py")
```

```mermaid
graph TD
    A[Python Workflow] -->|flow_extractor.py| B[WorkflowDefinition]
    B -->|WorkflowManager| C[YAML File]
    C -->|WorkflowManager| D[WorkflowDefinition]
    D -->|flow_generator.py| E[Standalone Python Script]
    style A fill:#e6f3ff,stroke:#0066cc,stroke-width:2px
    style B fill:#fff,stroke:#333
    style C fill:#e6ffe6,stroke:#009933,stroke-width:2px
    style D fill:#fff,stroke:#333
    style E fill:#fff0e6,stroke:#cc3300,stroke-width:2px
```

---

## 13. WorkflowManager 🧑‍💻

Programmatic workflow creation with new features:
```python
manager = WorkflowManager()
manager.add_node(
    "start",
    llm_config={"model": "lambda ctx: ctx['model_name']", "prompt_template": "Say hi to {name}"},
    inputs_mapping={"name": "user_name"}
)
manager.add_node(
    "format",
    template_config={"template": "Message: {text}"},
    inputs_mapping={"text": "start_result"}
)
manager.set_start_node("start")
manager.add_transition("start", "format")
manager.add_convergence_node("format")
manager.save_to_yaml("hi.yaml")
```

---

## 14. Conclusion 🎉

The Quantalogic Flow YAML DSL (March 8, 2025) is a powerful, flexible tool for workflow automation, exemplified by the updated Story Generator case study. With new **input mapping** (including lambdas), **template nodes**, and **dynamic model selection** in LLM nodes, alongside sub-workflows, branching, convergence, and conversion tools, it seamlessly bridges Python and YAML. Whether crafting dynamic stories with formatted chapters or managing complex processes, this DSL, paired with `WorkflowManager`, unlocks efficient, scalable workflows. 🚀
