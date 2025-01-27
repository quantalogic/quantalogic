import litellm


def get_litellm_models():
    """
    Retrieves a list of all model names supported by LiteLLM across all providers.
    
    Returns:
        list: A list of strings representing the model names.
    """
    return list(litellm.model_list)

# Example usage
if __name__ == "__main__":
    models = get_litellm_models()
    print("Supported models:", models)