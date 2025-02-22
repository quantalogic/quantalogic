#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "litellm",
#     "pydantic>=2.0",
#     "anyio",
#     "quantalogic>=0.35"
# ]
# ///
from typing import List

import anyio
from loguru import logger

from quantalogic.flow import Nodes, Workflow

MODEL = "gemini/gemini-2.0-flash"
DEFAULT_LLM_PARAMS = {
    "model": MODEL,
    "temperature": 0.7,
    "max_tokens": 2000,
    "top_p": 1.0,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
}

@Nodes.validate_node(output="validation_result")
async def validate_input(genre: str, num_chapters: int) -> str:
    """Validate input parameters."""
    if not (1 <= num_chapters <= 20 and genre.lower() in ["science fiction", "fantasy", "mystery", "romance"]):
        raise ValueError(f"Invalid input: num_chapters must be 1-20, genre must be one of science fiction, fantasy, mystery, romance")
    return "Input validated"

@Nodes.llm_node(
    **DEFAULT_LLM_PARAMS,
    system_prompt="You are a creative writer specializing in story titles.",
    prompt_template="Generate a creative title for a {genre} story",
    output="title",
)
async def generate_title(genre: str) -> str:
    """Generate a title based on the genre (handled by llm_node)."""
    pass  # Logic handled by llm_node decorator

@Nodes.llm_node(
    **DEFAULT_LLM_PARAMS,
    system_prompt="You are an expert in story structuring and outlining.",
    prompt_template="Create a detailed outline for a {genre} story titled '{title}' with {num_chapters} chapters",
    output="outline",
)
async def generate_outline(genre: str, title: str, num_chapters: int) -> str:
    """Generate a chapter outline for the story (handled by llm_node)."""
    pass  # Logic handled by llm_node decorator

@Nodes.llm_node(
    **DEFAULT_LLM_PARAMS,
    system_prompt="You are a skilled storyteller with a knack for vivid descriptions.",
    prompt_template="Write chapter {chapter_num} of {num_chapters} for the story '{title}'. Outline: {outline}. Style: {style}",
    output="chapter_content",
)
async def generate_chapter(title: str, outline: str, completed_chapters: int, num_chapters: int, style: str = "descriptive") -> str:
    """Generate content for a specific chapter (handled by llm_node)."""
    chapter_num = completed_chapters + 1  # Compute chapter_num from completed_chapters
    kwargs = {
        "chapter_num": chapter_num,
        "num_chapters": num_chapters,
        "title": title,
        "outline": outline,
        "style": style,
    }
    return await generate_chapter._call_llm(**kwargs)  # Direct call to the LLM logic

@Nodes.define(output="completed_chapters")
async def update_chapter_progress(chapters: List[str], chapter_content: str, completed_chapters: int) -> int:
    """Update the chapter list and completion count."""
    chapters.append(chapter_content)
    return completed_chapters + 1

@Nodes.define(output="manuscript")
async def compile_book(title: str, outline: str, chapters: List[str]) -> str:
    """Compile the full manuscript from title, outline, and chapters."""
    return f"Title: {title}\n\nOutline:\n{outline}\n\n" + "\n\n".join(f"Chapter {i}:\n{chap}" for i, chap in enumerate(chapters, 1))

@Nodes.llm_node(
    **DEFAULT_LLM_PARAMS,
    system_prompt="You are a meticulous editor reviewing manuscripts for quality.",
    prompt_template="Review this manuscript for coherence, grammar, and quality:\n\n{manuscript}",
    output="quality_check_result",
)
async def quality_check(manuscript: str) -> str:
    """Perform a quality check on the compiled manuscript (handled by llm_node)."""
    pass  # Logic handled by llm_node decorator

@Nodes.define()
async def end(quality_check_result: str) -> None:
    """Log the end of the workflow."""
    logger.info(f"Story generation completed. Quality check: {quality_check_result}")

# Define the workflow with explicit transitions to ensure correct execution order
workflow = (
    Workflow("validate_input")
    .node("validate_input")
    .then("generate_title")
    .node("generate_title")
    .then("generate_outline")
    .node("generate_outline")
    .then("generate_chapter")
    .node("generate_chapter")
    .then("update_chapter_progress")
    .node("update_chapter_progress")
    .then("generate_chapter", condition=lambda ctx: ctx["completed_chapters"] < ctx["num_chapters"])
    .then("compile_book", condition=lambda ctx: ctx["completed_chapters"] >= ctx["num_chapters"])
    .node("compile_book")
    .then("quality_check")
    .node("quality_check")
    .then("end")
    .node("end")
)

async def main():
    """Main function to run the story generation workflow."""
    initial_context = {
        "genre": "science fiction",
        "num_chapters": 3,
        "chapters": [],
        "completed_chapters": 0,
        "style": "descriptive"
    }
    engine = workflow.build()
    result = await engine.run(initial_context)
    logger.info(f"Workflow result: {result}")

if __name__ == "__main__":
    anyio.run(main)