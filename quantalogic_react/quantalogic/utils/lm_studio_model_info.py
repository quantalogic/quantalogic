from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ModelType(str, Enum):
    LLM = "llm"
    EMBEDDINGS = "embeddings"
    VLM = "vlm"


class CompatibilityType(str, Enum):
    MLX = "mlx"
    GGUF = "gguf"


class ModelState(str, Enum):
    LOADED = "loaded"
    NOT_LOADED = "not-loaded"


class ModelInfo(BaseModel):
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
    data: List[ModelInfo] = Field(..., description="List of available models")
    object: Literal["list"] = Field("list", description="Always 'list' for list responses")


def get_model_list() -> ModelListResponse:
    """Fetch and validate model information from LM Studio's API"""
    import requests

    response = requests.get("http://localhost:1234/api/v0/models")
    response.raise_for_status()

    return ModelListResponse(**response.json())
