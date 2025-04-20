from typing import Optional

import typer
from rich.console import Console

from quantalogic_codeact.llm_util.data import get_model_info, list_litellm_models
from quantalogic_codeact.llm_util.presentation import make_model_info_table, make_model_list_table

app = typer.Typer()
console = Console()

@app.command("list-models")
def list_models(query: Optional[str] = typer.Argument(None, help="Filter models by substring")) -> None:
    """List all available LLM models and their details."""
    console.rule("[bold cyan]Available LLM Models")
    models = list_litellm_models()
    if query:
        q = query.lower()
        models = [m for m in models if q in m.lower()]
    console.print(make_model_list_table(models))

    console.rule("[bold cyan]LLM Model Details")
    infos = get_model_info()
    if query:
        q = query.lower()
        infos = [info for info in infos if q in info.model_id.lower() or q in info.litellm_provider.lower()]
    console.print(make_model_info_table(infos))
