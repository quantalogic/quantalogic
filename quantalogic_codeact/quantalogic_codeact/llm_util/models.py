from typing import Dict, Optional

from pydantic import BaseModel, Field


class CostInfo(BaseModel):
    """Holds cost-related information for a model."""
    input_cost_per_token: Optional[float] = None
    output_cost_per_token: Optional[float] = None
    input_cost_per_token_batches: Optional[float] = None
    output_cost_per_token_batches: Optional[float] = None
    cache_read_input_token_cost: Optional[float] = None


class ModelInfo(BaseModel):
    """Represents the structure of a model's information."""
    model_id: str
    litellm_provider: str
    mode: str
    max_tokens: Optional[int] = None
    max_input_tokens: Optional[int] = None
    max_output_tokens: Optional[int] = None
    cost_info: CostInfo = Field(default_factory=CostInfo)
    capabilities: Dict[str, bool] = Field(default_factory=dict)
    deprecation_date: Optional[str] = None
