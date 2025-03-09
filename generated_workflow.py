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
DEFAULT_LLM_PARAMS = {'model': 'gemini/gemini-2.0-flash', 'temperature': 0.7, 'max_tokens': 1000}
updated_context = {}
initial_context = {'genre': 'science fiction', 'num_chapters': 3, 'completed_chapters': 0, 'style': 'descriptive'}

@Nodes.define(output='updated_context')
async def update_progress(**context):
    """Update the progress of chapter generation.
    
    Takes the entire context dictionary and handles missing keys gracefully.
    """
    chapters = context.get('chapters', [])
    completed_chapters = context.get('completed_chapters', 0)
    chapter = context.get('chapter', {})
    updated_chapters = chapters.copy()
    updated_chapters.append(chapter)
    updated_context = {**context, 'chapters': updated_chapters, 'completed_chapters': completed_chapters + 1}
    return updated_context

@Nodes.define(output='continue_generating')
async def check_if_complete(completed_chapters=0, num_chapters=0, **kwargs):
    """Check if all chapters have been generated.
    
    Args:
        completed_chapters: Number of chapters completed so far
        num_chapters: Total number of chapters to generate
        kwargs: Additional context parameters
        
    Returns:
        bool: True if we should continue generating chapters, False otherwise
    """
    return completed_chapters < num_chapters

# Define the workflow with branch and converge support
workflow = (
    Workflow("generate_outline")
    .node("generate_outline")
    .node("generate_chapter")
    .node("update_progress")
    .node("check_if_complete")
    .then("generate_chapter", condition=None)
    .then("update_progress", condition=None)
    .then("check_if_complete", condition=None)
    .then("generate_chapter", condition=lambda ctx: lambda ctx: ctx.get('continue_generating', False))
    .then("update_progress", condition=None)
    .then("check_if_complete", condition=None)
)

async def main():
    """Main function to run the workflow."""
    # Customize initial_context as needed
    # Inferred required inputs:
    # None detected
    initial_context = {
    }
    engine = workflow.build()
    result = await engine.run(initial_context)
    logger.info(f"Workflow result: {result}")

if __name__ == "__main__":
    anyio.run(main)
