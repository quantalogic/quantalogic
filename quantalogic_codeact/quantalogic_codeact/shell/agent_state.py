from dataclasses import dataclass

from ..codeact.agent import Agent


@dataclass
class AgentState:
    """Encapsulates agent-specific state."""
    agent: Agent