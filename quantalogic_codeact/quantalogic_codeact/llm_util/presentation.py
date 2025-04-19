from typing import List

from rich.table import Table

from .models import ModelInfo


def make_model_list_table(models: List[str]) -> Table:
    """Generate a Rich Table for a list of model names."""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Model", overflow="fold")
    for m in models:
        table.add_row(m)
    return table


def make_model_info_table(infos: List[ModelInfo]) -> Table:
    """Generate a Rich Table for a list of ModelInfo."""
    table = Table(show_header=True, header_style="bold green")
    table.add_column("Model ID")
    table.add_column("Provider")
    table.add_column("Mode")
    table.add_column("Max Tokens", justify="right")
    table.add_column("Deprecation Date")
    for info in infos:
        table.add_row(
            info.model_id,
            info.litellm_provider,
            info.mode,
            str(info.max_tokens or ""),
            info.deprecation_date or ""
        )
    return table
