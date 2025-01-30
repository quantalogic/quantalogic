from dataclasses import dataclass


@dataclass
class QLConfig:
    """Central configuration for QuantaLogic agent parameters."""
    model_name: str
    verbose: bool
    mode: str
    log: str
    vision_model_name: str | None
    max_iterations: int
    compact_every_n_iteration: int | None
    max_tokens_working_memory: int | None
    no_stream: bool