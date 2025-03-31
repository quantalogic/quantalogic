## flow book with chapters, images, ...etc
# i need a full book well designed with author, preambule, remerciements, dedicasse, final ...etc
#  like : BD bande dessiné

#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru>=0.7.2",
#     "litellm>=1.0.0",
#     "pydantic>=2.0.0",
#     "asyncio",
#     "jinja2>=3.1.0",
#     "quantalogic",
#     "instructor>=0.5.2",
#     "typer>=0.9.0",
#     "rich>=13.0.0"
# ]
# ///

import os
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

import anyio
import typer
from loguru import logger
from quantalogic.flow.flow import Nodes, Workflow, WorkflowEvent, WorkflowEventType

# Configure logging
logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

# Define structured output models
class NarrationStyle(BaseModel):
    """Narration style configuration."""
    type: str = Field(
        description="Type of narration",
        enum=[
            "first_person", "third_person_limited", "third_person_omniscient",
            "second_person", "multiple_narrators", "unreliable_narrator"
        ]
    )
    perspective: str = Field(description="Narrative perspective and voice characteristics")
    tense: str = Field(description="Past or present tense", enum=["past", "present"])

class LiteraryStyle(BaseModel):
    """Literary style configuration."""
    genre: str = Field(description="Primary genre of the work")
    tone: str = Field(description="Overall tone and mood")
    themes: List[str] = Field(description="Major themes to explore")
    writing_style: str = Field(description="Specific writing style (e.g., 'minimalist', 'flowery', 'stream of consciousness')")
    influences: List[str] = Field(description="Literary influences and similar authors")

class ChapterStructure(BaseModel):
    """Structure for a book chapter."""
    title: str = Field(description="Chapter title")
    pov_character: Optional[str] = Field(description="POV character for this chapter", default=None)
    narrative_hook: str = Field(description="Opening hook or central conflict")
    key_scenes: List[str] = Field(description="Key scenes to include")
    themes: List[str] = Field(description="Themes to explore in this chapter")
    word_count: int = Field(description="Target word count for the chapter")

class ChapterContent(BaseModel):
    """Content structure for a book chapter."""
    title: str = Field(description="Chapter title")
    pov_character: Optional[str] = Field(description="POV character for this chapter")
    summary: str = Field(description="Brief chapter summary")
    content: str = Field(description="Main chapter content")
    word_count: int = Field(description="Actual word count of the chapter")

class BookMetadata(BaseModel):
    """Book metadata and front/back matter."""
    title: str = Field(description="Book title")
    author: str = Field(description="Author name")
    narration_style: NarrationStyle = Field(description="Narration style configuration")
    literary_style: LiteraryStyle = Field(description="Literary style configuration")
    target_audience: str = Field(description="Target audience description")
    preface: str = Field(description="Book preface")
    acknowledgments: str = Field(description="Acknowledgments section")
    dedication: str = Field(description="Book dedication")
    epilogue: Optional[str] = Field(description="Book epilogue")

class BookStructure(BaseModel):
    """Complete book structure."""
    metadata: BookMetadata = Field(description="Book metadata and front/back matter")
    chapters: List[ChapterContent] = Field(description="List of chapters")
    total_word_count: int = Field(description="Total word count of the book")

# Get the templates directory path
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

def get_template_path(template_name):
    """Get the full path for a template file."""
    return os.path.join(TEMPLATES_DIR, template_name)

# Custom Observer for Workflow Events
async def book_progress_observer(event: WorkflowEvent):
    if event.event_type == WorkflowEventType.WORKFLOW_STARTED:
        print(f"\n{'='*50}\n📚 Starting Book Generation 📚\n{'='*50}")
    elif event.event_type == WorkflowEventType.NODE_STARTED:
        print(f"\n🔄 [{event.node_name}] Starting...")
    elif event.event_type == WorkflowEventType.NODE_COMPLETED:
        if event.node_name == "generate_chapter_content":
            print(f"✨ [{event.node_name}] Generated chapter content")
        elif event.node_name == "update_chapters":
            chapter_num = event.result
            print(f"✅ [{event.node_name}] Chapter {chapter_num} completed")
        elif event.node_name == "compile_book":
            print(f"📖 [{event.node_name}] Book compiled successfully")
        else:
            print(f"✅ [{event.node_name}] Completed")
    elif event.event_type == WorkflowEventType.WORKFLOW_COMPLETED:
        print(f"\n{'='*50}\n🎉 Book Generation Finished 🎉\n{'='*50}")

# Workflow Nodes
@Nodes.structured_llm_node(
    system_prompt="""You are a book planner. Create a book structure that follows the given specifications.
    Focus on creating a cohesive narrative arc with well-defined chapters.""",
    output="structure",
    response_model=BookStructure,
    prompt_template="""Create a book structure with the following specifications:

Title: {{title}}
Author: {{author}}
Number of Chapters: {{num_chapters}}
Words per Chapter: {{words_per_chapter}}
Total Word Count: {{total_word_count}}
Target Audience: {{target_audience}}

Story Concept:
{{content}}

Narration Style:
- Type: {{narration_style.type}}
- Perspective: {{narration_style.perspective}}
- Tense: {{narration_style.tense}}

Literary Style:
- Genre: {{literary_style.genre}}
- Tone: {{literary_style.tone}}
- Themes: {{literary_style.themes | join(', ')}}
- Writing Style: {{literary_style.writing_style}}
- Literary Influences: {{literary_style.influences | join(', ')}}

Please create a complete book structure with:
1. Front matter (dedication, preface, acknowledgments)
2. Chapter outlines with clear narrative progression
3. Epilogue (if appropriate)""",
    temperature=0.7,
    max_retries=3
)
async def generate_book_structure(
    model: str,
    content: str,
    num_chapters: int,
    title: str,
    author: str,
    narration_style: Dict,
    literary_style: Dict,
    target_audience: str,
    words_per_chapter: int,
    total_word_count: int
) -> BookStructure:
    """Generate the complete book structure including metadata and chapters."""
    logger.debug("Generating book structure")
    pass

@Nodes.structured_llm_node(
    system_prompt="""You are a creative writer. Generate a single chapter that follows the given style guidelines.
    Focus on creating engaging narrative content while maintaining consistent voice and style.""",
    output="chapter_content",
    response_model=ChapterContent,
    prompt_template="""Write a chapter with the following specifications:

Title: {{chapter_content.title}}
POV Character: {{chapter_content.pov_character if chapter_content.pov_character else 'N/A'}}
Summary: {{chapter_content.summary}}

Narration Style:
- Type: {{narration_style.type}}
- Perspective: {{narration_style.perspective}}
- Tense: {{narration_style.tense}}

Literary Style:
- Genre: {{literary_style.genre}}
- Tone: {{literary_style.tone}}
- Writing Style: {{literary_style.writing_style}}

Target Word Count: {{words_per_chapter}}

Please focus on:
1. Character development
2. Atmospheric description
3. Natural dialogue
4. Plot advancement
5. Theme exploration

Write the chapter content maintaining the specified narrative voice and style.""",
    temperature=0.7,
    max_retries=3
)
async def generate_chapter_content(
    model: str,
    chapter_content: Dict,
    narration_style: Dict,
    literary_style: Dict,
    words_per_chapter: int
) -> ChapterContent:
    """Generate detailed content for a chapter."""
    logger.debug(f"Generating content for chapter: {chapter_content['title']}")
    pass

@Nodes.define(output=None)
async def initialize_chapters() -> Dict:
    """Initialize the chapter tracking state."""
    logger.debug("Initializing chapter tracking")
    try:
        return {
            "completed_chapters": [],
            "completed_chapters_count": 0,
            "retry_count": 0,
            "max_retries": 3
        }
    except Exception as e:
        logger.error(f"Error initializing chapters: {str(e)}")
        raise

@Nodes.define(output="completed_chapters_count")
async def update_chapters(
    structure: BookStructure,
    completed_chapters: List[Dict],
    chapter_content: ChapterContent,
    completed_chapters_count: int,
    retry_count: int = 0,
    max_retries: int = 3
) -> int:
    """Update the list of completed chapters."""
    try:
        # Add the chapter to completed chapters
        completed_chapters.append(chapter_content.model_dump())
        logger.debug(f"Successfully added chapter {completed_chapters_count + 1}")
        return completed_chapters_count + 1
    except Exception as e:
        if retry_count < max_retries:
            logger.warning(f"Error updating chapters (attempt {retry_count + 1}): {str(e)}")
            return completed_chapters_count  # Keep current count and retry
        else:
            logger.error(f"Failed to update chapters after {max_retries} attempts: {str(e)}")
            raise

@Nodes.define(output="final_book")
async def compile_book(
    structure: BookStructure,
    completed_chapters: List[Dict]
) -> str:
    """Compile the final book with all content."""
    book = []
    
    # Add front matter
    book.extend([
        f"# {structure.metadata.title}",
        f"\nBy {structure.metadata.author}",
        "\n## Dedication",
        structure.metadata.dedication,
        "\n## Preface",
        structure.metadata.preface,
        "\n## Acknowledgments",
        structure.metadata.acknowledgments,
        "\n---\n"
    ])
    
    # Add chapters
    for i, chapter in enumerate(completed_chapters, 1):
        book.extend([
            f"\n## Chapter {i}: {chapter['title']}",
            "\n### Summary",
            chapter["summary"],
            "\n### Content",
            chapter["content"],
            "\n---\n"
        ])
    
    # Add epilogue if present
    if structure.metadata.epilogue:
        book.extend([
            "\n## Epilogue",
            structure.metadata.epilogue
        ])
    
    return "\n".join(book)

@Nodes.define(output=None)
async def save_book(final_book: str, output_path: str) -> None:
    """Save the final book to a file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_book)
    logger.info(f"Saved book to {output_path}")

# Create the workflow
workflow = (
    Workflow("generate_book_structure")
    .add_observer(book_progress_observer)
    .node("generate_book_structure", inputs_mapping={
        "model": "model",
        "content": "content",
        "num_chapters": "num_chapters",
        "title": "title",
        "author": "author",
        "narration_style": "narration_style",
        "literary_style": "literary_style",
        "target_audience": "target_audience",
        "words_per_chapter": "words_per_chapter",
        "total_word_count": "total_word_count"
    })
    .then("initialize_chapters")
    .then("generate_chapter_content", lambda ctx: {
        "model": ctx["model"],
        "chapter_content": ctx["structure"].chapters[ctx["completed_chapters_count"]].model_dump(),
        "narration_style": ctx["narration_style"],
        "literary_style": ctx["literary_style"],
        "words_per_chapter": ctx["words_per_chapter"]
    })
    .then("update_chapters", lambda ctx: {
        "structure": ctx["structure"],
        "completed_chapters": ctx["completed_chapters"],
        "chapter_content": ctx["chapter_content"],
        "completed_chapters_count": ctx["completed_chapters_count"],
        "retry_count": ctx["retry_count"]
    })
    .branch([
        ("generate_chapter_content", lambda ctx: ctx["completed_chapters_count"] < len(ctx["structure"].chapters)),
        ("compile_book", lambda ctx: ctx["completed_chapters_count"] >= len(ctx["structure"].chapters))
    ])
    .then("save_book")
)

async def create_book(
    content: str,
    title: str,
    author: str,
    output_path: str,
    model: str = "gemini/gemini-2.0-flash",
    num_chapters: int = 12,
    words_per_chapter: int = 2500,
    narration_style: Dict = {
        "type": "third_person_limited",
        "perspective": "intimate character focus",
        "tense": "past"
    },
    literary_style: Dict = {
        "genre": "literary fiction",
        "tone": "introspective",
        "themes": ["identity", "transformation", "society"],
        "writing_style": "lyrical realism",
        "influences": ["Virginia Woolf", "James Joyce"]
    },
    target_audience: str = "Adult literary fiction readers",
    total_word_count: Optional[int] = None
):
    """Create a literary novel with specified parameters."""
    if total_word_count is None:
        total_word_count = words_per_chapter * num_chapters

    initial_context = {
        "content": content,
        "title": title,
        "author": author,
        "output_path": output_path,
        "model": model,
        "num_chapters": num_chapters,
        "words_per_chapter": words_per_chapter,
        "total_word_count": total_word_count,
        "narration_style": narration_style,
        "literary_style": literary_style,
        "target_audience": target_audience
    }
    
    logger.info(f"Starting novel generation for '{title}' by {author}")
    engine = workflow.build()
    result = await engine.run(initial_context)
    logger.info("Novel generation completed successfully 🎉")
    return result

if __name__ == "__main__":
    # Example usage with literary parameters
    example_content = """
    A psychological exploration of memory and identity through the lens of an unreliable narrator.
    Set in a small coastal town, the story follows a reclusive writer who begins receiving mysterious
    letters that seem to be written by their younger self, forcing them to confront long-buried truths
    about their past.
    """
    
    # Create an async wrapper function
    async def main():
        await create_book(
            content=example_content,
            title="Echoes of Yesterday",
            author="A.I. Wordsworth",
            output_path="novel.md",
            num_chapters=3,
            words_per_chapter=3000,
            narration_style={
                "type": "unreliable_narrator",
                "perspective": "first person with questionable memory",
                "tense": "present"
            },
            literary_style={
                "genre": "psychological literary fiction",
                "tone": "introspective and unsettling",
                "themes": ["memory", "identity", "truth", "self-deception"],
                "writing_style": "stream of consciousness with unreliable elements",
                "influences": ["Virginia Woolf", "Kazuo Ishiguro", "Vladimir Nabokov"]
            },
            target_audience="Readers of literary fiction and psychological narratives"
        )
    
    # Run the async main function
    anyio.run(main)
