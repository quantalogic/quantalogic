from dataclasses import dataclass


@dataclass
class ShellState:
    """Encapsulates shell-wide state."""
    model_name: str
    max_iterations: int
    streaming: bool = True
    mode: str = "codeact"
    vision_model_name: str | None = None
    compact_every_n_iteration: int | None = None
    max_tokens_working_memory: int | None = None
