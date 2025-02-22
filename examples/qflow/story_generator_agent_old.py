#!/usr/bin/env -S uv run

# /// script
# # requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "litellm",
#     "pydantic>=2.0",
#     "anyio"
# ]
# ///
from qflow import Workflow, WorkflowEngine, NodeStatus
from litellm import acompletion
from loguru import logger
import anyio
from typing import List, Dict, Optional
from pydantic import BaseModel

MODEL = "gemini/gemini-2.0-flash"
DEFAULT_PARAMS = {
    "temperature": 0.7,
    "max_tokens": 2000
}

class ChapterRequest(BaseModel):
    genre: str
    num_chapters: int = 5
    style: str = "cinematic, technical prose"
    theme: Optional[str] = None
    target_audience: str = "young adults"

def create_workflow() -> Workflow:
    wf = Workflow(
        entry_node="validate_input",
        version="1.2.0"
    )

    # Nodes
    wf.add_node(
        name="validate_input",
        func=validate_input,
        inputs=["genre", "num_chapters"],
        output="validation_result",
        description="Validate input parameters"
    )

    wf.add_node(
        name="generate_title",
        func=generate_title,
        inputs=["genre", "theme", "target_audience"],
        output="title",
        max_retries=3,
        description="Generate novel title"
    )

    wf.add_node(
        name="generate_outline",
        func=generate_outline,
        inputs=["genre", "title", "num_chapters"],
        output="outline",
        timeout=30.0,
        description="Generate chapter outline"
    )

    wf.add_node(
        name="chapter_loop",
        func=chapter_loop,
        inputs=["total_chapters", "completed_chapters"],
        output="loop_status"
    )

    wf.add_node(
        name="generate_chapter",
        func=generate_chapter,
        inputs=["title", "outline", "current_chapter", "total_chapters", "style"],
        output="chapter_content",
        max_retries=3,
        description="Generate chapter content"
    )

    wf.add_node(
        name="update_chapter_progress",
        func=update_chapter_progress,
        inputs=["completed_chapters", "chapter_content", "chapters"],
        output="completed_chapters",
        description="Track chapter completion"
    )

    wf.add_node(
        name="compile_book",
        func=compile_book,
        inputs=["title", "outline", "chapters"],
        output="manuscript",
        description="Compile final manuscript"
    )

    wf.add_node(
        name="quality_check",
        func=quality_check,
        inputs=["manuscript"],
        output="quality_report",
        description="Quality assurance check"
    )

    wf.add_node("end",func=end,description="End node",inputs=[],output="")

    # Transitions
    wf.add_transition("validate_input", "success", "generate_title")
    wf.add_transition("generate_title", "success", "generate_outline")
    wf.add_transition("generate_outline", "success", "chapter_loop")
    wf.add_transition("chapter_loop", "next", "generate_chapter")
    wf.add_transition("chapter_loop", "complete", "compile_book")
    wf.add_transition("generate_chapter", "success", "update_chapter_progress")
    wf.add_transition("update_chapter_progress", "success", "chapter_loop")
    wf.add_transition("compile_book", "success", "quality_check")
    wf.add_transition("quality_check", "success", "end")

    return wf

async def generate_content(prompt: str, **kwargs) -> str:
    params = {**DEFAULT_PARAMS, **kwargs}
    response = await acompletion(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        **params
    )
    return response.choices[0].message.content.strip()

async def validate_input(genre: str, num_chapters: int) -> str:
    if num_chapters < 1 or num_chapters > 20:
        raise ValueError("Number of chapters must be between 1 and 20")
    
    valid_genres = ["science fiction", "fantasy", "mystery", "romance"]
    if genre.lower() not in valid_genres:
        raise ValueError(f"Invalid genre. Supported genres: {', '.join(valid_genres)}")
    
    return "Input validation passed"

async def generate_title(genre: str, theme: Optional[str], target_audience: str) -> str:
    prompt = f"""Generate a {genre} novel title suitable for {target_audience}.
    Theme: {theme or 'general'}
    Return only the title without any additional text."""
    return await generate_content(prompt, temperature=0.8)

async def generate_outline(genre: str, title: str, num_chapters: int) -> str:
    prompt = f"""Create a {num_chapters}-chapter outline for {title}
    Genre: {genre}
    Include:
    - Chapter titles
    - 3-5 key plot points per chapter
    - Character development milestones
    - Avoid spoilers in chapter titles"""
    return await generate_content(prompt, temperature=0.7)

async def generate_chapter(
    title: str,
    outline: str,
    current_chapter: int,
    total_chapters: int,
    style: str
) -> str:
    prompt = f"""Write Chapter {current_chapter}/{total_chapters} of {title}
    Style: {style}
    Outline: {outline}
    Current Chapter Requirements:
    - Include dialogue and descriptions
    - Maintain consistent character voices
    - Progress overarching plot
    - 800-1200 words"""
    return await generate_content(prompt, temperature=0.8)

async def update_chapter_progress(
    completed_chapters: int,
    chapter_content: str,
    chapters: List[str]
) -> int:
    chapters.append(chapter_content)
    return completed_chapters + 1

async def chapter_loop(total_chapters: int, completed_chapters: int) -> str:
    if completed_chapters < total_chapters:
        return "next"
    return "complete"

async def compile_book(title: str, outline: str, chapters: List[str]) -> str:
    manuscript = [
        f"# {title}\n",
        "## Outline\n",
        outline,
        "\n## Chapters\n"
    ]
    for idx, content in enumerate(chapters, 1):
        manuscript.append(f"\n### Chapter {idx}\n\n{content}")
    return "\n".join(manuscript)

async def quality_check(manuscript: str) -> str:
    prompt = f"""Analyze this manuscript for quality issues:
    {manuscript}
    Check for:
    - Consistency in plot and characters
    - Pacing issues
    - Grammar and style problems
    - Logical inconsistencies
    Provide detailed feedback in bullet points"""
    return await generate_content(prompt, temperature=0.2)

async def end() -> None:
    logger.info("End of course generation.")


async def main():
    wf = create_workflow()
    engine = WorkflowEngine(wf)

    try:
        state = await engine.execute({
            "genre": "science fiction",
            "num_chapters": 5,
            "style": "cinematic, technical prose",
            "theme": "interstellar diplomacy",
            "target_audience": "young adults",
            "current_chapter": 1,
            "total_chapters": 5,
            "completed_chapters": 0,
            "chapters": []
        })

        if manuscript := state.context.get("manuscript"):
            logger.success("Manuscript generated successfully!")
            print("\n" + "=" * 40 + " MANUSCRIPT " + "=" * 40)
            print(manuscript[:2000] + "\n[...truncated...]")
        else:
            logger.error("Workflow failed to generate manuscript")
            logger.debug("Workflow state: {}", state.model_dump())

    except Exception as e:
        logger.critical("Workflow execution failed: {}", e)
        if engine.state:
            logger.error("Failed state: {}", engine.state.model_dump())

if __name__ == "__main__":
    anyio.run(main)