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
from typing import Any, Dict, List

import anyio
from litellm import acompletion
from loguru import logger

from quantalogic.flow import Nodes, Workflow, WorkflowEngine

# Constants for LLM configuration
MODEL = "gemini/gemini-2.0-flash"
DEFAULT_PARAMS = {
    "temperature": 0.7,
    "max_tokens": 2000
}

# Helper function for LLM content generation
async def generate_content(prompt: str, **kwargs) -> str:
    params = {**DEFAULT_PARAMS, **kwargs}
    response = await acompletion(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        **params
    )
    return response.choices[0].message.content.strip()

# Node definitions using quantalogic.flow.Nodes
@Nodes.define(output="validation_result")
async def validate_input(genre: str, num_chapters: int) -> str:
    """Validate input parameters."""
    if num_chapters < 1 or num_chapters > 20:
        raise ValueError("Number of chapters must be between 1 and 20")
    valid_genres = ["science fiction", "fantasy", "mystery", "romance"]
    if genre.lower() not in valid_genres:
        raise ValueError(f"Invalid genre. Supported genres: {', '.join(valid_genres)}")
    return "Input validation passed"

@Nodes.define(output="title")
async def generate_title(genre: str) -> str:
    """Generate a title based on the genre."""
    prompt = f"Generate a creative title for a {genre} story"
    return await generate_content(prompt)

@Nodes.define(output="outline")
async def generate_outline(genre: str, title: str, num_chapters: int) -> str:
    """Generate a chapter outline for the story."""
    prompt = f"Create a detailed outline for a {genre} story titled '{title}' with {num_chapters} chapters"
    return await generate_content(prompt)

@Nodes.define(output="chapter_content")
async def generate_chapter(title: str, outline: str, completed_chapters: int, num_chapters: int, style: str = "descriptive") -> str:
    """Generate content for a specific chapter."""
    prompt = f"Write chapter {completed_chapters + 1} of {num_chapters} for the story '{title}'. Story outline: {outline}. Writing style: {style}"
    return await generate_content(prompt)

@Nodes.define(output="completed_chapters")
async def update_chapter_progress(chapters: List[str], chapter_content: str, completed_chapters: int) -> int:
    """Update the chapter list and completion count."""
    chapters.append(chapter_content)  # Modify the list in place
    return completed_chapters + 1

@Nodes.define(output="manuscript")
async def compile_book(title: str, outline: str, chapters: List[str]) -> str:
    """Compile the full manuscript from title, outline, and chapters."""
    manuscript = f"Title: {title}\n\nOutline:\n{outline}\n\n"
    for i, chapter in enumerate(chapters, 1):
        manuscript += f"Chapter {i}:\n{chapter}\n\n"
    return manuscript

@Nodes.define(output="quality_check_result")
async def quality_check(manuscript: str) -> str:
    """Perform a quality check on the compiled manuscript."""
    prompt = f"Review this manuscript for coherence, grammar, and storytelling quality:\n\n{manuscript}"
    return await generate_content(prompt)

@Nodes.define()
async def end(quality_check_result: str) -> None:
    """Log the end of the workflow."""
    logger.info(f"Story generation completed. Quality check: {quality_check_result}")

# Define the workflow using quantalogic.flow.Workflow
workflow = (
    Workflow("validate_input")
    .node("validate_input")            # Start: Validate inputs
    .then("generate_title")
    .node("generate_title")            # Generate the story title
    .then("generate_outline")
    .node("generate_outline")          # Generate the outline
    .then("generate_chapter")
    .node("generate_chapter")          # Generate the first chapter
    .then("update_chapter_progress")
    .node("update_chapter_progress")   # Update progress
    .then("generate_chapter", condition=lambda ctx: ctx['completed_chapters'] < ctx['num_chapters'])  # Loop if more chapters needed
    .then("compile_book", condition=lambda ctx: ctx['completed_chapters'] >= ctx['num_chapters'])     # Proceed when all chapters done
    .node("compile_book")              # Compile the book
    .then("quality_check")
    .node("quality_check")             # Perform quality check
    .then("end")
    .node("end")                       # End the workflow
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

    engine = workflow.build()  # Create the WorkflowEngine correctly
    result = await engine.run(initial_context)
    logger.info(f"Workflow result: {result}")

if __name__ == "__main__":
    anyio.run(main)