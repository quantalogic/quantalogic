from typing import List

import requests

from quantalogic_codeact.llm_util.models import CostInfo, ModelInfo


def list_litellm_models() -> List[str]:
    """Fetches and returns a list of all models supported by litellm."""
    url = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        # Handle JSON structures: top-level dict or list of entries
        if isinstance(data, dict):
            return [mid for mid in data.keys() if mid != 'sample_spec']
        models = []
        for entry in data:
            provider = entry.get("litellm_provider")
            model_name = entry.get("model")
            if provider and model_name and model_name != 'sample_spec':
                models.append(f"{provider}/{model_name}")
        return models
    except requests.RequestException as e:
        print(f"Error fetching the model list: {e}")
        return []


def get_model_info() -> List[ModelInfo]:
    """Fetches and returns detailed information about all models supported by litellm."""
    url = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        models: List[ModelInfo] = []
        for model_id, info in data.items():
            if model_id == 'sample_spec':
                continue
            capabilities = {k: v for k, v in info.items() if k.startswith("supports_") and isinstance(v, bool)}
            cost_info = CostInfo(
                input_cost_per_token=info.get("input_cost_per_token"),
                output_cost_per_token=info.get("output_cost_per_token"),
                input_cost_per_token_batches=info.get("input_cost_per_token_batches"),
                output_cost_per_token_batches=info.get("output_cost_per_token_batches"),
                cache_read_input_token_cost=info.get("cache_read_input_token_cost"),
            )
            model = ModelInfo(
                model_id=model_id,
                litellm_provider=info.get("litellm_provider", ""),
                mode=info.get("mode", ""),
                max_tokens=info.get("max_tokens"),
                max_input_tokens=info.get("max_input_tokens"),
                max_output_tokens=info.get("max_output_tokens"),
                cost_info=cost_info,
                capabilities=capabilities,
                deprecation_date=info.get("deprecation_date"),
            )
            models.append(model)
        return models
    except requests.RequestException as e:
        print(f"Error fetching model information: {e}")
        return []
