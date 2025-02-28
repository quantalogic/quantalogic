import litellm

from quantalogic.get_model_info import model_info


def get_all_models() -> list[str]:
    """
    Retrieves a unified list of all model names supported by LiteLLM and Quantalogic.

    Returns:
        list: A list of strings representing the model names.
    """
    litellm_models = set(litellm.model_list)
    quantalogic_models = set(model_info.keys())
    return list(litellm_models.union(quantalogic_models))


# Example usage
if __name__ == "__main__":
    models = get_all_models()
    print("Supported models:", models)
