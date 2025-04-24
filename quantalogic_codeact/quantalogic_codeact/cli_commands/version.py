import typer

from quantalogic_codeact.version import get_version

app = typer.Typer()

@app.command("version")
def version_command() -> None:
    """Show quantalogic package version."""
    version = get_version()
    typer.echo(version)
