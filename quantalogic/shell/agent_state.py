from typing import Dict, List

from quantalogic.codeact.agent import Agent


class AgentState:
    """Encapsulates agent-specific state."""
    def __init__(self, agent: Agent):
        self.agent = agent
        self.message_history: List[Dict[str, str]] = []
        self.model_name: str
        self.vision_model_name: str | None
        self.max_iterations: int
        self.compact_every_n_iteration: int | None
        self.max_tokens_working_memory: int | None
        
        
