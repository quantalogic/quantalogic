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
#     "instructor[litellm]",
# ]
# ///

import anyio
from typing import List
from loguru import logger
from quantalogic.flow import Nodes, Workflow

MODEL = 'gemini/gemini-2.0-flash'
DEFAULT_LLM_PARAMS = {'model': 'gemini/gemini-2.0-flash', 'temperature': 0.7, 'max_tokens': 2000, 'top_p': 1.0, 'presence_penalty': 0.0, 'frequency_penalty': 0.0}
initial_context = {'genre': 'science fiction', 'num_chapters': 3, 'completed_chapters': 0, 'style': 'descriptive'}

@Nodes.define(output='validation_result')
async def validate_input(genre: str, num_chapters: int):
    """Validate input parameters."""
    if not (1 <= num_chapters <= 20 and genre.lower() in ['science fiction', 'fantasy', 'mystery', 'romance']):
        raise ValueError('Invalid input: num_chapters must be 1-20, genre must be one of science fiction, fantasy, mystery, romance')
    return 'Input validated'

@Nodes.define(output='update_progress_result')
async def update_progress(chapters: List[str], chapter: str, completed_chapters: int):
    """Update the chapter list and completion count."""
    updated_chapters = chapters + [chapter]
    return {'chapters': updated_chapters, 'completed_chapters': completed_chapters + 1}

@Nodes.define(output='manuscript')
async def compile_book(title: str, outline: str, chapters: List[str]):
    """Compile the full manuscript from title, outline, and chapters."""
    return f'Title: {title}\n\nOutline:\n{outline}\n\n' + '\n\n'.join((f'Chapter {i}:\n{chap}' for i, chap in enumerate(chapters, 1)))

# Define the workflow with branch, converge, and loop support
workflow = (
    Workflow("validate_input")
    .node("validate_input")
    .node("generate_title")
    .node("generate_outline")
    .node("generate_chapter")
    .start_loop()
    .node("update_progress")
    .node("compile_book")
    .node("quality_check")
    .then("generate_title", condition=None)
    .then("generate_outline", condition=None)
    .then("generate_chapter", condition=None)
    .then("compile_book", condition=lambda ctx: lambda ctx: ctx['completed_chapters'] >= ctx['num_chapters'])
    .then("quality_check", condition=None)
)

async def main():
    """Main function to run the workflow."""
    # Customize initial_context as needed
    # Inferred required inputs:
    # genre, num_chapters
    initial_context = {
        'genre': '',
        'num_chapters': '',
    }
    engine = workflow.build()
    result = await engine.run(initial_context)
    logger.info(f"Workflow result: {result}")

if __name__ == "__main__":
    anyio.run(main)
