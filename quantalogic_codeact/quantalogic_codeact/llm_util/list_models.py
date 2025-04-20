

from rich.console import Console

from quantalogic_codeact.llm_util.data import get_model_info, list_litellm_models
from quantalogic_codeact.llm_util.presentation import make_model_info_table, make_model_list_table


def main():
    console = Console()
    console.rule("[bold]Litellm Models List")
    models = list_litellm_models()
    with console.pager():
        console.print(make_model_list_table(models))

    console.rule("[bold]Litellm Model Info")
    infos = get_model_info()
    with console.pager():
        console.print(make_model_info_table(infos))


if __name__ == "__main__":
    main()