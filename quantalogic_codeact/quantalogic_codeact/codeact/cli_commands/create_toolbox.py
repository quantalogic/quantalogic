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
    # Create __init__.py with version info
    init_file = package_dir / "__init__.py"
    init_file.write_text(f'""" {name} toolbox package """\n__version__ = "{version}"\n')

    # Render and write template files
    context = {"name": name, "package_name": package_name, "version": version}
    for template_name in ["pyproject.toml.j2", "tools.py.j2", "README.md.j2"]:
        template = env.get_template(template_name)
        content = template.render(**context)
        output_file = toolbox_dir / template_name.replace(".j2", "")
        if template_name == "tools.py.j2":
            output_file = package_dir / "tools.py"
        output_file.write_text(content.strip())

    logger.info(f"Created starter toolbox project: {name}")
    console.print(f"[green]Created starter toolbox project: {name}[/green]")