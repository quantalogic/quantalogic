from pydantic import BaseModel


class ModelInfo(BaseModel):
    model_name: str
    max_input_tokens: int
    max_output_tokens: int
    max_cot_tokens: int | None = None


class ModelNotFoundError(Exception):
    """Raised when a model is not found in local registry"""
