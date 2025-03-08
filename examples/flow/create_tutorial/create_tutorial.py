#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "litellm",
#     "pydantic>=2.0",
#     "anyio",
#     "quantalogic>=0.35",
#     "jinja2",
#     "typer",
#     "pyperclip",
#     "instructor"
# ]
# ///

import os
from typing import Dict, List

import anyio
import pyperclip
import typer
from loguru import logger
from pydantic import BaseModel

from quantalogic.flow.flow import Nodes, Workflow, WorkflowEvent, WorkflowEventType

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
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    logger.info(f"Read markdown file: {path}")
    return {"markdown_content": content, "original_path": path}

@Nodes.structured_llm_node(
    system_prompt="You are an expert in creating educational tutorials. Based on the markdown content provided, design a detailed tutorial structure with EXACTLY {{num_chapters}} chapters. Each chapter must include a title, summary, and lists of 'Why', 'What', 'How' ideas, examples, and Mermaid diagram ideas. Ensure the structure reflects the content of the markdown file.",
    output="structure",
    response_model=TutorialStructure,
    prompt_template="Markdown Content:\n{{markdown_content}}\n\nGenerate a tutorial structure with {{num_chapters}} chapters in JSON format.",
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
    system_prompt="You are a skilled writer crafting educational tutorials. Using the provided chapter structure and full markdown content, write a detailed chapter (about {{words_per_chapter}} words) with 'Why', 'What', and 'How' sections, plus examples and Mermaid diagrams. Base the content on the markdown file and the chapter structure.",
    output="draft_chapter",
    prompt_template="Chapter Structure:\n{{chapter_structure}}\n\nFull Markdown Content:\n{{markdown_content}}\n\nWrite a detailed chapter based on the structure and content.",
    temperature=0.7,
)
async def generate_draft(model: str, chapter_structure: Dict, markdown_content: str, words_per_chapter: int) -> str:
    logger.debug(f"Generating draft for chapter: {chapter_structure['title']} with words_per_chapter: {words_per_chapter}")
    pass

@Nodes.llm_node(
    system_prompt="You are an editor reviewing educational content. Critique the draft chapter for clarity, coherence, engagement, and adherence to the 'Why', 'What', 'How' structure. Provide specific, actionable feedback in under 300 words.",
    output="critique",
    prompt_template="Draft Chapter:\n{{draft_chapter}}\n\nCritique the draft and suggest improvements.",
    max_tokens=300,
)
async def critique_draft(model: str, draft_chapter: str) -> str:
    logger.debug("Critiquing draft chapter")
    pass

@Nodes.llm_node(
    system_prompt="You are a writer refining educational content. Revise the draft chapter based on the critique, improving clarity, coherence, and engagement while keeping the 'Why', 'What', 'How' structure intact.",
    output="improved_draft",
    prompt_template="Draft Chapter:\n{{draft_chapter}}\n\nCritique:\n{{critique}}\n\nRevise the draft based on the critique. Don't add any additional content, comments.",
    temperature=0.7,
)
async def improve_draft(model: str, draft_chapter: str, critique: str, words_per_chapter: int) -> str:
    logger.debug("Improving draft based on critique")
    pass

@Nodes.llm_node(
    system_prompt="You are an editor enhancing tutorial content. Revise the chapter by adding emojis, storytelling, and improved markdown formatting (e.g., headers, lists). Include clear Mermaid diagrams where specified in the structure. Make it engaging and reader-friendly.",
    output="revised_chapter",
    prompt_template="Improved Draft:\n{{improved_draft}}\n\nEnhance the chapter with emojis, storytelling, and formatting. Don't add any additional content, comments.",
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

@Nodes.define(output="final_book")
async def compile_book(structure: TutorialStructure, completed_chapters: List[str]) -> str:
    book = f"# {structure.title} 🎓\n\nWelcome to this tutorial! Let’s explore with clear explanations and visuals. 🚀\n\n"
    for i, (chapter_structure, content) in enumerate(zip(structure.chapters, completed_chapters), 1):
        book += f"## Chapter {i}: {chapter_structure.title} ✨\n\n{content}\n\n---\n\n"
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
    logger.info(f"Saved tutorial to {output_path} 💾")
    print("\n" + "="*50)
    print("📘 Final Tutorial Content 📘")
    print("="*50)
    print(final_book)
    print("="*50)

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
    .then("critique_draft")
    .then("improve_draft")
    .node("improve_draft", inputs_mapping={
        "model": "model",
        "draft_chapter": "draft_chapter",
        "critique": "critique",
        "words_per_chapter": "words_per_chapter",
        "max_tokens": lambda ctx: int(ctx["words_per_chapter"] * 1.5 * 1.2)
    })
    .then("revise_formatting")
    .node("revise_formatting", inputs_mapping={
        "model": "model",
        "improved_draft": "improved_draft",
        "words_per_chapter": "words_per_chapter",
        "max_tokens": lambda ctx: int(ctx["words_per_chapter"] * 1.5 * 1.2)
    })
    .then("update_chapters")
    .branch([
        ("generate_draft", lambda ctx: ctx.get("completed_chapters_count", 0) < len(ctx["structure"].chapters)),
        ("compile_book", lambda ctx: ctx.get("completed_chapters_count", 0) >= len(ctx["structure"].chapters))
    ])
    .node("compile_book")  # Explicitly set current node to compile_book to ensure proper transition
    .then("optional_copy_to_clipboard")  # Transition from compile_book to optional_copy_to_clipboard
    .then("save_and_display")  # Transition from optional_copy_to_clipboard to save_and_display
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
):
    initial_context = {
        "path": path,
        "model": model,
        "num_chapters": num_chapters,
        "words_per_chapter": words_per_chapter,
        "copy_to_clipboard": copy_to_clipboard,
    }
    logger.info(f"Starting tutorial generation for {path}")
    engine = workflow.build()
    result = anyio.run(engine.run, initial_context)
    logger.info("Tutorial generation completed successfully 🎉")

if __name__ == "__main__":
    app()