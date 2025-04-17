class ShellState:
    """Encapsulates shell-wide state."""
    def __init__(self, streaming: bool = True, mode: str = "codeact"):
        self.streaming: bool = streaming
        self.mode: str = mode
        self.model_name: str
        self.vision_model_name: str | None
        self.max_iterations: int
        self.compact_every_n_iteration: int | None
        self.max_tokens_working_memory: int | None
