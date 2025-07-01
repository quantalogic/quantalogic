from typing import Optional

from pydantic import BaseModel


class QLConfig(BaseModel):
    model_name: str
    verbose: bool
    mode: str
    log: str
    vision_model_name: Optional[str] = None
    max_iterations: int
    compact_every_n_iteration: Optional[int] = None
    max_tokens_working_memory: Optional[int] = None
    no_stream: bool
    thinking_model_name: str
    chat_system_prompt: Optional[str] = None
    tool_mode: Optional[str] = None  # Added field for tool mode
    auto_tool_call: bool = True  # Default to True for automatic tool execution