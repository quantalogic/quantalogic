#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "litellm",
#     "pydantic>=2.0",
#     "anyio",
#     "pypandoc",
#     "typer",
#     "rich",
#     "aiofiles",
#     "quantalogic"
# ]
# ///

import typer
import anyio
from rich.console import Console
from rich.prompt import Prompt
from ai_course_generator.course_generator_agent import CourseRequest, generate_course

app = typer.Typer(add_completion=False)
console = Console()

@app.command()
def generate(
    subject: str = typer.Option(None, help="Course subject"),
    number_of_chapters: int = typer.Option(None, help="Number of chapters"),
    level: str = typer.Option(None, help="Difficulty level (beginner/intermediate/advanced)"),
    words_by_chapter: int = typer.Option(None, help="Number of words per chapter"),
    target_directory: str = typer.Option(None, help="Target directory for course output"),
    pdf_generation: bool = typer.Option(True, help="Generate PDF version of the course"),
    docx_generation: bool = typer.Option(True, help="Generate DOCX version of the course"),
    epub_generation: bool = typer.Option(False, help="Generate EPUB version of the course"),
    model_name: str = typer.Option(None, help="AI model to use for course generation"),
    interactive: bool = typer.Option(None, "--interactive", "-i", help="Enable interactive mode")
):
    """Generate a course plan based on parameters"""
    
    # If no parameters are provided, force interactive mode
    if all(param is None for param in [subject, number_of_chapters, level, words_by_chapter, target_directory, model_name, interactive]):
        interactive = True
    
    # If interactive is explicitly set to True or no parameters were provided
    if interactive or interactive is None:
        console.print("[bold magenta]Course Generation Interactive Mode[/bold magenta]\n")
        
        # Course content parameters
        subject = Prompt.ask(
            "[bold]Enter course subject[/bold] (e.g. Python, Java, C++)", 
            default=subject or "Python Programming"
        )
        
        number_of_chapters = int(Prompt.ask(
            "[bold]Number of chapters[/bold] (1-20)", 
            default=str(number_of_chapters or 5)
        ))
        
        level = Prompt.ask(
            "[bold]Difficulty level[/bold]",
            choices=["beginner", "intermediate", "advanced"],
            default=level or "intermediate"
        )
        
        # Output configuration
        target_directory = Prompt.ask(
            "[bold]Target directory[/bold] (path to save course files)", 
            default=target_directory or "./courses"
        )
        
        words_by_chapter = int(Prompt.ask(
            "[bold]Words per chapter[/bold] (500-5000)", 
            default=str(words_by_chapter or 1000)
        ))
        
        # Document formats
        pdf_generation = Prompt.ask(
            "[bold]Generate PDF version[/bold]", 
            choices=["True", "False"], 
            default=str(pdf_generation)
        ) == "True"
        
        docx_generation = Prompt.ask("[bold]Generate DOCX version[/bold]", choices=["True", "False"], default=str(docx_generation)) == "True"
        epub_generation = Prompt.ask("[bold]Generate EPUB version[/bold]", choices=["True", "False"], default=str(epub_generation)) == "True"
        model_name = Prompt.ask("[bold]AI Model Name[/bold]", default=model_name or "gemini/gemini-2.0-flash")
    else:
        # Validate that all required parameters are provided when not in interactive mode
        if any(param is None for param in [subject, number_of_chapters, level, words_by_chapter, target_directory]):
            console.print("[bold red]Error: All parameters are required when not in interactive mode.[/bold red]")
            raise typer.Abort()

    course_request = CourseRequest(
        subject=subject,
        number_of_chapters=number_of_chapters,
        level=level,
        words_by_chapter=words_by_chapter,
        target_directory=target_directory,
        pdf_generation=pdf_generation,
        docx_generation=docx_generation,
        epub_generation=epub_generation,
        model_name=model_name
    )
    
    with console.status("[bold green]Generating course..."):
        result = anyio.run(generate_course, course_request)
    
    console.print(f"[bold green]\nGenerated Course Plan at: {result}[/bold green]")

def main():
    """Entry point for Poetry script"""
    app()

if __name__ == "__main__":
    main()
