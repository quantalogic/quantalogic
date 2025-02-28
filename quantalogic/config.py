from dataclasses import dataclass
from typing import Optional


@dataclass
class QLConfig:
    """Central configuration for QuantaLogic agent parameters."""

    model_name: str
    verbose: bool
    mode: str
    log: str
    vision_model_name: Optional[str]
    max_iterations: int
    compact_every_n_iteration: Optional[int]
    max_tokens_working_memory: Optional[int]
    no_stream: bool
    thinking_model_name: str
