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
from typing import Dict, List
from pydantic import BaseModel, Field
from pathlib import Path

import anyio
import typer
from loguru import logger
from quantalogic.flow.flow import Nodes, Workflow, WorkflowEvent, WorkflowEventType
from quantalogic.tools.image_generation.stable_diffusion import StableDiffusionTool
from jinja2 import Environment, FileSystemLoader

## flow book with chapters, images, ...etc
# i need a full book well designed with author, preambule, remerciements, dedicasse, final ...etc
#  like : BD bande dessiné

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
    type: str = Field(description="Type of narration")
    perspective: str = Field(description="Narrative perspective and voice characteristics")
    tense: str = Field(description="Past or present tense")

class LiteraryStyle(BaseModel):
    """Literary style configuration."""
    genre: str = Field(description="Primary genre of the work")
    tone: str = Field(description="Overall tone and mood")
    themes: List[str] = Field(description="Major themes to explore")
    writing_style: str = Field(description="Specific writing style")
    influences: List[str] = Field(description="Literary influences and similar authors")

class ChapterStructure(BaseModel):
    """Structure for a book chapter."""
    title: str = Field(description="Chapter title")
    pov_character: str = Field(description="POV character for this chapter")
    narrative_hook: str = Field(description="Opening hook or central conflict")
    key_scenes: List[str] = Field(description="Key scenes to include")
    themes: List[str] = Field(description="Themes to explore in this chapter")
    word_count: int = Field(description="Target word count for the chapter")

class ImageRequest(BaseModel):
    """Request for chapter illustration."""
    description: str = Field(description="Description of the image to generate")
    style: str = Field(description="Art style for the image")
    size: str = Field(description="Image dimensions")

class ImageRequestList(BaseModel):
    """Container for a list of image requests."""
    requests: List[ImageRequest] = Field(description="List of image requests for the chapter")

class ChapterContent(BaseModel):
    """Content structure for a book chapter."""
    title: str = Field(description="Chapter title")
    pov_character: str = Field(description="POV character for this chapter")
    summary: str = Field(description="Brief chapter summary")
    content: str = Field(description="Main chapter content")
    word_count: int = Field(description="Actual word count of the chapter")
    image_requests: List[ImageRequest] = Field(description="List of image generation requests")
    image_paths: List[str] = Field(description="List of generated image paths")

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
    epilogue: str = Field(description="Book epilogue")

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

# Define valid styles for StableDiffusionTool
VALID_STYLES = [
    'photographic', 'digital-art', 'cinematic', 'anime', 'comic-book', 
    'pixel-art', 'enhance', 'fantasy-art', 'line-art', 'analog-film', 
    'neon-punk', 'isometric', 'low-poly', 'origami', 'modeling-compound', 
    '3d-model', 'tile-texture'
]

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
    system_prompt="""You are a creative writer. Generate a single chapter response in JSON format.""",
    output="chapter_content",
    response_model=ChapterContent,
    prompt_template="""Create a chapter following these guidelines:

Title: {{chapter_content.title if chapter_content.title else "TBD"}}
POV Character: {{chapter_content.pov_character if chapter_content.pov_character else "TBD"}}
Word Count: {{words_per_chapter}}
Narration: {{narration_style.type}} in {{narration_style.perspective}}, {{narration_style.tense}} tense
Style: {{literary_style.genre}} with {{literary_style.tone}} tone, {{literary_style.writing_style}}

Return a single JSON object with this exact structure:
{
    "title": "string",
    "pov_character": "string",
    "summary": "string",
    "content": "string",
    "word_count": number,
    "image_requests": [],
    "image_paths": []
}""",
    temperature=0.7,
    max_retries=2,
    model_kwargs={
        "response_format": {"type": "json_object"},
        "tool_choice": "none"
    }
)
async def generate_chapter_content(
    model: str,
    chapter_content: Dict,
    narration_style: Dict,
    literary_style: Dict,
    words_per_chapter: int
) -> ChapterContent:
    """Generate detailed content for a chapter."""
    logger.debug(f"Generating content for chapter: {chapter_content.get('title', 'new chapter')}")
    pass

@Nodes.structured_llm_node(
    system_prompt="""You are an expert book planner and editor. Create a detailed book structure with metadata and chapter outlines.""",
    output="structure",
    response_model=BookStructure,
    prompt_template="""Create a structured book with {{num_chapters}} chapters based on the following content.

Title: {{title}}
Author: {{author}}
Content: {{content}}

Create a book structure with:
1. Metadata including:
   - Title and author
   - Narration style (type, perspective, tense)
   - Literary style (genre, tone, themes, writing style, influences)
   - Target audience
   - Preface, acknowledgments, dedication, epilogue

2. {{num_chapters}} chapters, each with:
   - Title
   - POV character
   - Summary
   - Content
   - Word count ({{words_per_chapter}} words per chapter)
   - Empty lists for image requests and paths (will be filled later)

3. Total word count of {{total_word_count}}

Maintain consistency with:
Narration Style: {{narration_style}}
Literary Style: {{literary_style}}
Target Audience: {{target_audience}}""",
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
    system_prompt="""You are an expert writer and illustrator. Generate detailed image requests for key moments in the chapter.""",
    output="image_requests",
    response_model=ImageRequestList,
    prompt_template="""Generate detailed image descriptions for key moments in this chapter:

Title: {{chapter_content.title}}
Summary: {{chapter_content.summary}}
Content: {{chapter_content.content}}

Create 1-3 image requests that capture pivotal moments. Each image must include:
1. A detailed visual description
2. The art style must be one of: """ + str(VALID_STYLES) + """
3. The image size: "{{size}}"

Focus on:
- Character expressions and poses
- Scene composition and setting
- Lighting and atmosphere
- Dramatic moments
- Visual symbolism

Required format for each image request:
{
  "requests": [
    {
      "description": "Detailed scene description",
      "style": "one of the valid styles listed above",
      "size": "{{size}}"
    }
  ]
}""",
    temperature=0.7,
    model_kwargs={"response_format": {"type": "json_object"}}
)
async def generate_image_requests(
    model: str,
    chapter_content: Dict,
    style: str = "digital-art",
    size: str = "1024x1024"
) -> ImageRequestList:
    """Generate image requests for a chapter."""
    logger.debug(f"Generating image requests for chapter: {chapter_content.get('title', 'unknown')}")
    pass

@Nodes.define(output="image_paths")
async def generate_chapter_images(image_requests: ImageRequestList) -> List[str]:
    """Generate images for a chapter using the image requests."""
    image_paths = []
    sd_tool = StableDiffusionTool()
    
    if not image_requests or not image_requests.requests:
        logger.warning("No valid image requests provided")
        return image_paths
    
    default_size = "1024x1024"
    default_style = "digital-art"
    
    for request in image_requests.requests:
        if not request.description:
            logger.warning("Skipping image request with empty description")
            continue
            
        try:
            # Ensure we have valid size and style
            size = request.size if request.size else default_size
            
            # Validate and set style
            style = request.style if request.style else default_style
            if style not in VALID_STYLES:
                logger.warning(f"Invalid style '{style}', using default style '{default_style}'")
                style = default_style
            
            # Validate size format
            try:
                width, height = map(int, size.split('x'))
                # Reconstruct size string to ensure proper format
                size = f"{width}x{height}"
            except (ValueError, AttributeError):
                logger.warning(f"Invalid size format '{size}', using default")
                size = default_size
            
            result = await sd_tool.async_execute(
                prompt=request.description,
                style=style,
                size=size
            )
            if result:
                image_paths.append(result)
                logger.info(f"Generated image: {result}")
            else:
                logger.warning("Image generation returned no result")
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            continue
    
    return image_paths

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
    image_paths: List[str],
    completed_chapters_count: int,
    retry_count: int = 0,
    max_retries: int = 3
) -> int:
    """Update the list of completed chapters."""
    try:
        # Add the chapter with images to completed chapters
        chapter_dict = chapter_content.model_dump()
        chapter_dict["image_paths"] = image_paths
        completed_chapters.append(chapter_dict)
        logger.debug(f"Successfully added chapter {completed_chapters_count + 1}")
        return completed_chapters_count + 1
    except Exception as e:
        if retry_count < max_retries:
            logger.warning(f"Error updating chapters (attempt {retry_count + 1}): {str(e)}")
            return completed_chapters_count
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
    
    # Add chapters with images
    for i, chapter in enumerate(completed_chapters, 1):
        book.extend([
            f"\n## Chapter {i}: {chapter['title']}",
            "\n### Summary",
            chapter["summary"],
            "\n### Content",
            chapter["content"]
        ])
        
        # Add images if present
        if "image_paths" in chapter and chapter["image_paths"]:
            book.append("\n### Illustrations")
            for j, image_path in enumerate(chapter["image_paths"], 1):
                book.append(f"\n![Chapter {i} Illustration {j}]({image_path})")
        
        book.append("\n---\n")
    
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

@Nodes.define(output="web_book")
async def generate_web_book(
    structure: BookStructure,
    completed_chapters: List[Dict],
    templates_dir: str = TEMPLATES_DIR
) -> str:
    """Generate a web-based version of the book."""
    try:
        env = Environment(loader=FileSystemLoader(templates_dir))
        template = env.get_template("web_book_template.html")
        
        # Create book data structure for the template
        book_data = {
            "metadata": structure.metadata.model_dump(),
            "chapters": completed_chapters
        }
        
        # Render the template
        html_content = template.render(book=book_data)
        return html_content
    except Exception as e:
        logger.error(f"Error generating web book: {str(e)}")
        raise

@Nodes.define(output=None)
async def save_web_book(web_book: str, output_path: str, completed_chapters: List[Dict], structure: BookStructure) -> None:
    """Save the web version of the book."""
    # Create output directory based on the output_path
    output_dir = os.path.dirname(output_path)
    web_dir = os.path.join(output_dir, "web")
    os.makedirs(web_dir, exist_ok=True)

    # Create a sanitized book title for the filename
    book_title = structure.metadata.title.lower().replace(" ", "_").replace("'", "").replace('"', "")
    web_output_path = os.path.join(web_dir, f"{book_title}.html")

    # Create assets directory for images and styles
    assets_dir = os.path.join(web_dir, "assets")
    images_dir = os.path.join(assets_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    # Copy images to assets directory and update paths
    for chapter in completed_chapters:
        if "image_paths" in chapter and chapter["image_paths"]:
            for old_path in chapter["image_paths"]:
                if os.path.exists(old_path):
                    filename = os.path.basename(old_path)
                    new_path = os.path.join(images_dir, filename)
                    import shutil
                    shutil.copy2(old_path, new_path)
                    
                    # Update image path in chapter to be relative to the HTML file
                    chapter["image_paths"][chapter["image_paths"].index(old_path)] = f"assets/images/{filename}"

    # Save the HTML file
    with open(web_output_path, 'w', encoding='utf-8') as f:
        f.write(web_book)
    logger.info(f"Saved web book to {web_output_path}")

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
        "narration_style": ctx["structure"].metadata.narration_style.model_dump(),
        "literary_style": ctx["structure"].metadata.literary_style.model_dump(),
        "words_per_chapter": ctx["words_per_chapter"]
    })
    .then("generate_image_requests", lambda ctx: {
        "model": ctx["model"],
        "chapter_content": ctx["chapter_content"],
        "style": ctx.get("art_style", "digital-art"),
        "size": ctx.get("image_size", "1024x1024")
    })
    .then("generate_chapter_images")
    .then("update_chapters", lambda ctx: {
        "structure": ctx["structure"],
        "completed_chapters": ctx["completed_chapters"],
        "chapter_content": ctx["chapter_content"],
        "image_paths": ctx["image_paths"],
        "completed_chapters_count": ctx["completed_chapters_count"],
        "retry_count": ctx.get("retry_count", 0),
        "max_retries": ctx.get("max_retries", 3)
    })
    .branch([
        ("generate_chapter_content", lambda ctx: ctx["completed_chapters_count"] < len(ctx["structure"].chapters)),
        ("compile_book", lambda ctx: ctx["completed_chapters_count"] >= len(ctx["structure"].chapters))
    ])
    .then("save_book", lambda ctx: {
        "final_book": ctx["final_book"],
        "output_path": ctx["output_path"]
    })
    .then("generate_web_book", lambda ctx: {
        "structure": ctx["structure"],
        "completed_chapters": ctx["completed_chapters"]
    })
    .then("save_web_book", lambda ctx: {
        "web_book": ctx["web_book"],
        "output_path": ctx["output_path"],
        "completed_chapters": ctx["completed_chapters"],
        "structure": ctx["structure"]
    })
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
    total_word_count: int = None,
    art_style: str = "digital-art",
    image_size: str = "1024x1024"
):
    """Create a literary novel with specified parameters and illustrations."""
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
        "target_audience": target_audience,
        "art_style": art_style,
        "image_size": image_size
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
    
    # Create output directory
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "novel.md")
    
    # Create an async wrapper function
    async def main():
        await create_book(
            content=example_content,
            title="Echoes of Yesterday",
            author="A.I. Wordsworth",
            output_path=output_path,
            num_chapters=2,
            words_per_chapter=300,
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
            target_audience="Readers of literary fiction and psychological narratives",
            art_style="surreal",
            image_size="2048x2048"
        )
    
    # Run the async main function
    anyio.run(main)
