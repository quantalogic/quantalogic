from dataclasses import dataclass, field
from typing import Dict, List

from quantalogic.codeact.agent import Agent


@dataclass
class AgentState:
    """Encapsulates agent-specific state."""
    agent: Agent
    model_name: str
    max_iterations: int
    message_history: List[Dict[str, str]] = field(default_factory=list)
    vision_model_name: str | None = None
    compact_every_n_iteration: int | None = None
    max_tokens_working_memory: int | None = None
