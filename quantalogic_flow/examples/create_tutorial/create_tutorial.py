#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "anyio",
#     "quantalogic-flow>=0.6.5",
#     "typer",
#     "pyperclip",
# ]
# ///

import os
from typing import Dict, List

import anyio
import pyperclip
import typer
from loguru import logger
from pydantic import BaseModel

from quantalogic_flow.flow import Nodes, Workflow, WorkflowEvent, WorkflowEventType

# Configure logging (set to DEBUG for troubleshooting)
logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    level="DEBUG",  # Changed to DEBUG to see LLM inputs/outputs
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

# Define structured output models
class ChapterStructure(BaseModel):
    title: str
    summary: str
    why_ideas: List[str]
    what_ideas: List[str]
    how_ideas: List[str]
    example_ideas: List[str]
    diagram_ideas: List[str]

class TutorialStructure(BaseModel):
    title: str
    chapters: List[ChapterStructure]

# Get the templates directory path
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# Helper function to get template paths
def get_template_path(template_name):
    return os.path.join(TEMPLATES_DIR, template_name)

# Custom Observer for Workflow Events
async def tutorial_progress_observer(event: WorkflowEvent):
    if event.event_type == WorkflowEventType.WORKFLOW_STARTED:
        print(f"\n{'='*50}\n🚀 Starting Tutorial Generation 🚀\n{'='*50}")
    elif event.event_type == WorkflowEventType.NODE_STARTED:
        print(f"\n🔄 [{event.node_name}] Starting...")
    elif event.event_type == WorkflowEventType.NODE_COMPLETED:
        if event.node_name == "update_chapters" and event.result is not None:
            chapter_num = event.result
            preview_lines = event.context["completed_chapters"][-1].split('\n')[:3]
            preview = '\n    '.join(preview_lines)
            print(f"✅ [{event.node_name}] Chapter {chapter_num} completed\n    Preview:\n    {preview}\n    ...")
        elif event.node_name == "compile_book":
            print(f"✅ [{event.node_name}] Tutorial compiled successfully")
        else:
            print(f"✅ [{event.node_name}] Completed")
    elif event.event_type == WorkflowEventType.WORKFLOW_COMPLETED:
        print(f"\n{'='*50}\n🎉 Tutorial Generation Finished 🎉\n{'='*50}")
    elif event.event_type == WorkflowEventType.TRANSITION_EVALUATED:
        logger.debug(f"Transition evaluated: {event.transition_from} -> {event.transition_to}")

# Workflow Nodes
@Nodes.define(output=None)
async def read_markdown(path: str) -> dict:
    path = os.path.expanduser(path)
    with open(path, encoding='utf-8') as f:
        content = f.read()
    logger.info(f"Read markdown file: {path}")
    return {"markdown_content": content, "original_path": path}

@Nodes.structured_llm_node(
    system_prompt_file=get_template_path("system_generate_structure.j2"),
    output="structure",
    response_model=TutorialStructure,
    prompt_file=get_template_path("prompt_generate_structure.j2"),
    temperature=0.5,
)
async def generate_structure(model: str, markdown_content: str, num_chapters: int) -> TutorialStructure:
    logger.debug("Generating tutorial structure")
    pass

@Nodes.define(output=None)
async def validate_structure(structure: TutorialStructure, num_chapters: int) -> dict:
    actual_chapters = len(structure.chapters)
    if actual_chapters != num_chapters:
        logger.warning(f"Structure has {actual_chapters} chapters, expected {num_chapters}. Proceeding with actual count.")
    else:
        logger.info(f"Validated structure with {actual_chapters} chapters")
    return {"structure": structure}

@Nodes.define(output=None)
async def initialize_chapters() -> dict:
    logger.debug("Initializing chapter tracking")
    return {"completed_chapters": [], "completed_chapters_count": 0}

@Nodes.llm_node(
    system_prompt_file=get_template_path("system_generate_draft.j2"),
    output="draft_chapter",
    prompt_file=get_template_path("prompt_generate_draft.j2"),
    temperature=0.7,
)
async def generate_draft(model: str, chapter_structure: Dict, markdown_content: str, words_per_chapter: int) -> str:
    logger.debug(f"Generating draft for chapter: {chapter_structure['title']} with words_per_chapter: {words_per_chapter}")
    pass

@Nodes.llm_node(
    system_prompt_file=get_template_path("system_critique_draft.j2"),
    output="critique",
    prompt_file=get_template_path("prompt_critique_draft.j2"),
    max_tokens=300,
)
async def critique_draft(model: str, draft_chapter: str) -> str:
    logger.debug("Critiquing draft chapter")
    pass

@Nodes.llm_node(
    system_prompt_file=get_template_path("system_improve_draft.j2"),
    output="improved_draft",
    prompt_file=get_template_path("prompt_improve_draft.j2"),
    temperature=0.7,
)
async def improve_draft(model: str, draft_chapter: str, critique: str, words_per_chapter: int) -> str:
    logger.debug("Improving draft based on critique")
    pass

@Nodes.llm_node(
    system_prompt_file=get_template_path("system_revise_formatting.j2"),
    output="revised_chapter",
    prompt_file=get_template_path("prompt_revise_formatting.j2"),
    temperature=0.8,
)
async def revise_formatting(model: str, improved_draft: str, words_per_chapter: int) -> str:
    logger.debug("Revising chapter formatting")
    pass

@Nodes.define(output="completed_chapters_count")
async def update_chapters(completed_chapters: List[str], revised_chapter: str, completed_chapters_count: int) -> int:
    completed_chapters.append(revised_chapter)
    new_count = completed_chapters_count + 1
    return new_count

def clean_chapter_content(content: str) -> str:
    """Remove code block delimiters and first heading from chapter content."""
    # Handle empty input explicitly
    if not content:
        return ""
    
    lines = content.split('\n')
    
    # Remove opening code block if present
    if lines and (lines[0].strip().startswith('```markdown') or lines[0].strip() == '```'):
        lines = lines[1:]
    
    # Remove closing code block if present
    if lines and lines[-1].strip() == '```':
        lines = lines[:-1]
    
    # Check if lines are empty after delimiter removal
    if not lines:
        return ""

    # Find and remove first # heading if present
    for i, line in enumerate(lines):
        if line.strip() and line.strip().startswith("# "):
            # Found a heading line, remove it
            lines.pop(i)
            break
    
    # Find and remove first ## heading if present
    for i, line in enumerate(lines):
        if line.strip() and line.strip().startswith("## "):
            # Found a heading line, remove it
            lines.pop(i)
            break
    
    # Check if lines are empty after heading removal
    if not lines:
        return ""
    
    # Clean leading empty lines
    while lines and not lines[0].strip():
        lines.pop(0)
    
    # Check if lines are empty after leading cleanup
    if not lines:
        return ""
    
    # Clean trailing empty lines
    while lines and not lines[-1].strip():
        lines.pop(-1)
    
    return '\n'.join(lines)

@Nodes.define(output="final_book")
async def compile_book(structure: TutorialStructure, completed_chapters: List[str]) -> str:
    book = f"# {structure.title}\n\n"
    
    for i, (chapter_structure, content) in enumerate(zip(structure.chapters, completed_chapters), 1):
        # Clean the chapter content using the dedicated function
        cleaned_content = clean_chapter_content(content)
        book += f"## Chapter {i}: {chapter_structure.title}\n\n{cleaned_content}\n\n---\n\n"
    
    return book

@Nodes.define(output=None)
async def optional_copy_to_clipboard(final_book: str, copy_to_clipboard: bool) -> None:
    if copy_to_clipboard:
        pyperclip.copy(final_book)
        logger.info("Copied tutorial to clipboard 📋")

@Nodes.define(output=None)
async def save_and_display(final_book: str, original_path: str) -> None:
    dir_path = os.path.dirname(original_path)
    base_name = os.path.basename(original_path)
    name, ext = os.path.splitext(base_name)
    output_path = os.path.join(dir_path, f"{name}_tutorial{ext}")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_book)
    print("\n" + "="*50)
    print("📘 Final Tutorial Content 📘")
    print("="*50)
    print(final_book)
    print("="*50)
    logger.info(f"Saved tutorial to {output_path} 💾")
    print("Saved to:", output_path)


# Define the Workflow with explicit transitions
workflow = (
    Workflow("read_markdown")
    .add_observer(tutorial_progress_observer)
    .then("generate_structure")
    .then("validate_structure")
    .then("initialize_chapters")
    .then("generate_draft")
    .node("generate_draft", inputs_mapping={
        "chapter_structure": lambda ctx: ctx["structure"].chapters[ctx["completed_chapters_count"]].model_dump(),
        "markdown_content": "markdown_content",
        "words_per_chapter": "words_per_chapter",
        "model": "model",
        "max_tokens": lambda ctx: int(ctx["words_per_chapter"] * 1.5 * 1.2)
    })
    .branch([
        # Skip refinement path - go directly to update_chapters with draft_chapter
        ("update_chapters", lambda ctx: ctx.get("skip_refinement", False)),
        # Full refinement path - go through critique, improve, revise
        ("critique_draft", lambda ctx: not ctx.get("skip_refinement", False))
    ])
    
    # Define the critique path separately
    .node("critique_draft")
    .then("improve_draft")
    .then("revise_formatting")
    .then("update_chapters")
    
    # Define update_chapters node with different input mappings depending on path
    .node("update_chapters", inputs_mapping={
        "completed_chapters": "completed_chapters",
        "revised_chapter": lambda ctx: (
            ctx.get("revised_chapter") if "revised_chapter" in ctx 
            else ctx.get("draft_chapter")
        ),
        "completed_chapters_count": "completed_chapters_count"
    })
    .branch([
        ("generate_draft", lambda ctx: ctx.get("completed_chapters_count", 0) < len(ctx["structure"].chapters)),
        ("compile_book", lambda ctx: ctx.get("completed_chapters_count", 0) >= len(ctx["structure"].chapters))
    ])
    
    # Define the path for continuing with another chapter
    .node("generate_draft")
    
    # Define the path for finishing the tutorial
    .node("compile_book")
    .then("optional_copy_to_clipboard")
    .then("save_and_display")
)

# CLI with Typer
app = typer.Typer()

@app.command()
def generate_tutorial(
    path: str = typer.Argument(..., help="Path to the markdown file"),
    model: str = typer.Option("gemini/gemini-2.0-flash", help="LLM model to use"),
    num_chapters: int = typer.Option(5, help="Number of chapters"),
    words_per_chapter: int = typer.Option(2000, help="Words per chapter"),
    copy_to_clipboard: bool = typer.Option(True, help="Copy result to clipboard"),
    skip_refinement: bool = typer.Option(True, help="Skip critique and improvement steps"),
):
    initial_context = {
        "path": path,
        "model": model,
        "num_chapters": num_chapters,
        "words_per_chapter": words_per_chapter,
        "copy_to_clipboard": copy_to_clipboard,
        "skip_refinement": skip_refinement,
    }
    logger.info(f"Starting tutorial generation for {path}")
    engine = workflow.build()
    result = anyio.run(engine.run, initial_context)
    logger.info("Tutorial generation completed successfully 🎉")

if __name__ == "__main__":
    app()