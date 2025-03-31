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
from quantalogic.tools.image_generation.stable_diffusion import StableDiffusionTool, STABLE_DIFFUSION_CONFIG

# Configure logging
logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

# Define structured output models
class ImageRequest(BaseModel):
    """Request for chapter illustration."""
    description: str = Field(description="Description of the image to generate")
    style: str = Field(description="Art style for the image")
    size: str = Field(description="Image dimensions")

class ChapterImageRequests(BaseModel):
    """Container for chapter image requests."""
    requests: List[ImageRequest] = Field(description="List of image requests for the chapter", max_items=3)

class ChapterContent(BaseModel):
    """Content structure for a book chapter."""
    title: str = Field(description="Chapter title")
    summary: str = Field(description="Brief chapter summary")
    content: str = Field(description="Main chapter content")
    image_requests: List[ImageRequest] = Field(description="List of image generation requests", max_items=3)

class BookMetadata(BaseModel):
    """Book metadata and front/back matter."""
    title: str = Field(description="Book title")
    author: str = Field(description="Author name")
    preface: str = Field(description="Book preface")
    acknowledgments: str = Field(description="Acknowledgments section")
    dedication: str = Field(description="Book dedication")
    conclusion: str = Field(description="Book conclusion")

class BookStructure(BaseModel):
    """Complete book structure."""
    metadata: BookMetadata = Field(description="Book metadata and front/back matter")
    chapters: List[ChapterContent] = Field(description="List of chapters")

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
        if event.node_name == "generate_chapter_images":
            print(f"✨ [{event.node_name}] Generated images for chapter")
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
    system_prompt="""You are an expert book planner and editor. Your task is to analyze the input content 
    and create a detailed book structure with metadata and chapter outlines.""",
    output="structure",
    response_model=BookStructure,
    prompt_template="""Create a structured book with {{num_chapters}} chapters based on the following content.

Title: {{title}}
Author: {{author}}
Content: {{content}}

For each chapter:
1. Create an engaging title
2. Write a brief summary that hooks the reader
3. Plan the main content structure
4. Consider potential illustration opportunities (1-3 per chapter)

Also create:
1. A meaningful dedication
2. A comprehensive preface
3. Heartfelt acknowledgments
4. A satisfying conclusion

Remember to maintain a cohesive narrative flow throughout the book.""",
    temperature=0.7
)
async def generate_book_structure(
    model: str,
    content: str,
    num_chapters: int,
    title: str,
    author: str
) -> BookStructure:
    """Generate the complete book structure including metadata and chapters."""
    logger.debug("Generating book structure")
    pass

@Nodes.structured_llm_node(
    system_prompt="""You are a creative writer and illustrator specializing in comic book art. Your task is to generate detailed image 
    descriptions that will work well with the comic book style of illustration.""",
    output="image_requests",
    response_model=ChapterImageRequests,
    prompt_template="""Create comic book panel descriptions for the following chapter:

Title: {{chapter_content.title}}
Summary: {{chapter_content.summary}}
Content: {{chapter_content.content}}

Style: Comic Book ({{style_preset}})
Image Size: {{size}}

Generate between 1 and 3 comic book panel descriptions that:
1. Capture dramatic moments or key scenes from the chapter
2. Use dynamic compositions and angles typical of comic books
3. Include clear foreground and background elements
4. Consider emotional impact and character expressions
5. Work well with the comic book art style

For each panel description:
- Focus on action and movement
- Include character poses and expressions
- Describe the scene composition
- Mention lighting and atmosphere
- Keep it clear and specific for the AI artist""",
    temperature=0.7
)
async def generate_image_requests(
    model: str,
    chapter_content: Dict,
    style_preset: str,
    size: str
) -> ChapterImageRequests:
    """Generate image requests for a chapter."""
    logger.debug(f"Generating image requests for chapter: {chapter_content['title']}")
    pass

@Nodes.define(output="image_paths")
async def generate_chapter_images(image_requests: ChapterImageRequests) -> List[str]:
    """Generate images for a chapter using the image requests."""
    image_paths = []
    sd_tool = StableDiffusionTool()
    
    for request in image_requests.requests:
        try:
            # Override style to ensure it's always comic-book
            result = await sd_tool.async_execute(
                prompt=request.description,
                style="comic-book",  # Force comic-book style
                size=request.size
            )
            image_paths.append(result)
            logger.info(f"Generated image: {result}")
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            continue
    
    return image_paths

@Nodes.define(output="completed_chapters_count")
async def update_chapters(
    structure: BookStructure,
    completed_chapters: List[Dict],
    chapter_content: Dict,
    image_paths: List[str],
    completed_chapters_count: int
) -> int:
    """Update the list of completed chapters with content and images."""
    # Get the current chapter from structure
    current_chapter = structure.chapters[completed_chapters_count].model_dump()
    
    # Add images to the chapter content
    current_chapter["image_paths"] = image_paths
    
    # Append to completed chapters
    completed_chapters.append(current_chapter)
    return completed_chapters_count + 1

@Nodes.define(output="final_book")
async def compile_book(
    structure: BookStructure,
    completed_chapters: List[Dict]
) -> str:
    """Compile the final book with all content and images."""
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
            chapter["content"],
            "\n### Illustrations"
        ])
        
        for image_path in chapter["image_paths"]:
            book.append(f"\n![Chapter {i} Illustration]({image_path})")
        
        book.append("\n---\n")
    
    # Add conclusion
    book.extend([
        "\n## Conclusion",
        structure.metadata.conclusion
    ])
    
    return "\n".join(book)

@Nodes.define(output=None)
async def initialize_chapters() -> Dict:
    """Initialize the chapter tracking state."""
    logger.debug("Initializing chapter tracking")
    return {"completed_chapters": [], "completed_chapters_count": 0}

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
        "author": "author"
    })
    .then("initialize_chapters")
    .then("generate_image_requests", lambda ctx: {
        "model": ctx["model"],
        "chapter_content": ctx["structure"].chapters[ctx["completed_chapters_count"]].model_dump(),
        "style_preset": "comic-book",
        "size": ctx["size"]
    })
    .then("generate_chapter_images")
    .then("update_chapters", lambda ctx: {
        "structure": ctx["structure"],
        "completed_chapters": ctx["completed_chapters"],
        "chapter_content": ctx["structure"].chapters[ctx["completed_chapters_count"]].model_dump(),
        "image_paths": ctx["image_paths"],
        "completed_chapters_count": ctx["completed_chapters_count"]
    })
    .branch([
        ("generate_image_requests", lambda ctx: ctx["completed_chapters_count"] < len(ctx["structure"].chapters)),
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
    num_chapters: int = 2,
    style_preset: str = "comic-book",
    size: str = "1024x1024"
):
    """Create an illustrated book with chapters and images."""
    initial_context = {
        "content": content,
        "title": title,
        "author": author,
        "output_path": output_path,
        "model": model,
        "num_chapters": num_chapters,
        "style_preset": style_preset,
        "size": size
    }
    
    logger.info(f"Starting book generation for '{title}' by {author}")
    engine = workflow.build()
    result = await engine.run(initial_context)
    logger.info("Book generation completed successfully 🎉")
    return result

if __name__ == "__main__":
    # Example usage with direct variables
    example_content = """
    This is a story about a young programmer who discovers the magic of coding.
    Through various adventures and challenges, they learn about algorithms,
    data structures, and the power of creative problem-solving.
    """
    
    # Create an async wrapper function
    async def main():
        await create_book(
            content=example_content,
            title="The Coding Adventure",
            author="AI Writer",
            output_path="coding_adventure.md"
        )
    
    # Run the async main function
    anyio.run(main)
