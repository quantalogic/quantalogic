from pathlib import Path

import typer
from jinja2 import Environment, FileSystemLoader
from loguru import logger
from rich.console import Console

app = typer.Typer()

console = Console()

@app.command()
def create_toolbox(
    name: str = typer.Argument(..., help="Name of the new toolbox (e.g., 'my-toolbox')")
) -> None:
    """Create a starter toolbox project with the given name using Jinja2 templates."""
    toolbox_dir = Path(name)
    if toolbox_dir.exists():
        logger.error(f"Directory '{name}' already exists.")
        console.print(f"[red]Error: Directory '{name}' already exists.[/red]")
        raise typer.Exit(code=1)

    # Set up Jinja2 environment
    template_dir = Path(__file__).parent.parent / "templates" / "toolbox"
    env = Environment(loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True)

    # Create directory structure
    toolbox_dir.mkdir()
    package_name = name.replace("-", "_")
    version = "0.1.0"
    package_dir = toolbox_dir / package_name
    package_dir.mkdir()

    # Render and write template files (including __init__.py)
    context = {"name": name, "package_name": package_name, "version": version}
    template_files = [
        "pyproject.toml.j2",
        "tools.py.j2",
        "README.md.j2",
        "__init__.py.j2",
    ]
    for template_name in template_files:
        template = env.get_template(template_name)
        content = template.render(**context)
        if template_name == "tools.py.j2":
            output_file = package_dir / "tools.py"
        elif template_name == "__init__.py.j2":
            output_file = package_dir / "__init__.py"
        else:
            output_file = toolbox_dir / template_name.replace(".j2", "")
        output_file.write_text(content.strip())

    # Inform user of toolbox path and features
    toolbox_path = toolbox_dir.resolve()
    logger.info(f"Created starter toolbox project '{name}' at: {toolbox_path}")
    typer.echo(f"Toolbox created at: {toolbox_path}")
    
    # Inform about the confirmation system examples
    console.print("\n[bold green]Toolbox Features:[/bold green]")
    console.print("- Basic echo tool example")
    console.print("- [bold yellow]Confirmation system examples:[/bold yellow]")
    console.print("  - Static confirmation message example: [italic]delete_item[/italic]")
    console.print("  - Dynamic confirmation message example: [italic]modify_item[/italic]")
    console.print("\n[bold]Usage:[/bold]")
    console.print(f"1. Install your toolbox: [blue]pip install -e {toolbox_path}[/blue]")
    console.print(f"2. Enable it in your config: [blue]quantalogic_codeact toolbox install {package_name}[/blue]")