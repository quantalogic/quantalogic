from rich.console import Console

from quantalogic_codeact.llm_util.data import get_model_info
from quantalogic_codeact.llm_util.presentation import make_model_info_table


async def listmodels_command(shell, args) -> None:
    """List available models, optionally filtered by substring."""
    console = Console()
    # Fetch and optionally filter model info
    substring = args[0] if args else None
    console.rule("[bold]Litellm Model Info")
    infos = get_model_info()
    if substring:
        substring = substring.lower()
        infos = [info for info in infos
                 if substring in info.model_id.lower() or substring in info.litellm_provider.lower()]
    console.print(make_model_info_table(infos))
