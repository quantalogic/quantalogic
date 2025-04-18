from pathlib import Path

import typer
import yaml
from loguru import logger

app = typer.Typer()

@app.command()
def config_load(filename: str = typer.Argument(..., help="Path to the configuration file to load")):
    """Load a configuration from a file into the default config location."""
    try:
        with open(filename) as f:
            new_config = yaml.safe_load(f) or {}
        config_file_path = Path(".quantalogic/config.yaml").resolve()
        config_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file_path, "w") as f:
            yaml.safe_dump(new_config, f, default_flow_style=False)
        logger.info(f"Configuration loaded from {filename} and saved to {config_file_path}")
        typer.echo(f"Configuration loaded from {filename} and saved to {config_file_path}")
    except Exception as e:
        logger.error(f"Error loading configuration from {filename}: {e}")
        typer.echo(f"Error loading configuration: {e}")
        raise typer.Exit(code=1)