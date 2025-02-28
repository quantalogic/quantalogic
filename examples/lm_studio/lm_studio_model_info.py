#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests",
#     "pydantic>=2.0"
# ]
# ///

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ModelType(str, Enum):
    """Enum representing different types of AI models supported by LM Studio"""

    LLM = "llm"
    EMBEDDINGS = "embeddings"
    VLM = "vlm"


class CompatibilityType(str, Enum):
    """Enum representing different model compatibility formats"""

    MLX = "mlx"
    GGUF = "gguf"


class ModelState(str, Enum):
    """Enum representing the loading state of models in LM Studio"""

    LOADED = "loaded"
    NOT_LOADED = "not-loaded"


class ModelInfo(BaseModel):
    """Pydantic model representing metadata for an AI model in LM Studio"""

    id: str = Field(..., description="Unique model identifier in LM Studio's namespace")
    object: Literal["model"] = Field("model", description="Always 'model' for model objects")
    type: ModelType = Field(..., description="Type of AI model")
    publisher: str = Field(..., description="Organization or user who published the model")
    arch: str = Field(..., description="Base architecture family")
    compatibility_type: CompatibilityType = Field(..., alias="compatibility_type")
    quantization: Optional[str] = Field(None, description="Quantization method if applicable")
    state: ModelState = Field(..., description="Current loading state in LM Studio")
    max_context_length: int = Field(..., alias="max_context_length", ge=0)
    loaded_context_length: Optional[int] = Field(
        None, alias="loaded_context_length", description="Currently allocated context length (only when loaded)", ge=0
    )


class ModelListResponse(BaseModel):
    """Pydantic model representing the response from LM Studio's model list API"""

    data: List[ModelInfo] = Field(..., description="List of available models")
    object: Literal["list"] = Field("list", description="Always 'list' for list responses")


def get_model_list() -> ModelListResponse:
    """Fetch and validate model information from LM Studio's API"""
    import requests

    response = requests.get("http://localhost:1234/api/v0/models")
    response.raise_for_status()

    return ModelListResponse(**response.json())


# Example usage
if __name__ == "__main__":
    model_list = get_model_list()

    # Print formatted model info
    for model in model_list.data:
        status = "✅ Loaded" if model.state == ModelState.LOADED else "❌ Not loaded"
        print(f"{status} | {model.id}")
        print(f"  Architecture: {model.arch}")
        print(f"  Max Context: {model.max_context_length:,} tokens")
        if model.loaded_context_length:
            print(f"  Loaded Context: {model.loaded_context_length:,} tokens")
        print(f"  Format: {model.compatibility_type.value} ({model.quantization or 'N/A'})")
        print()
