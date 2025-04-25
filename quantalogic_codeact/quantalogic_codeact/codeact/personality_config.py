"""Defines the PersonalityConfig for agent personality modeling."""
from typing import Dict, List, Tuple

from pydantic import BaseModel, Field, validator


class DialogueTurn(BaseModel):
    """One turn in a dialogue: user or agent."""
    user: str = Field(..., description="Speaker of this turn")
    content: Dict[str, str] = Field(..., description="Content payload, e.g. {'text': ...}")


class MessageExample(BaseModel):
    """A pair of dialogue turns: user then agent."""
    turns: Tuple[DialogueTurn, DialogueTurn] = Field(
        ..., description="Exactly two turns: user then agent"
    )

    @validator("turns")
    def must_be_pair(cls, v):
        if len(v) != 2:
            raise ValueError("messageExamples must have exactly two turns: [user, agent]")
        return v


class StyleConfig(BaseModel):
    all: List[str] = Field(default_factory=list, description="Global style rules")
    chat: List[str] = Field(default_factory=list, description="Style for chat responses")
    post: List[str] = Field(default_factory=list, description="Style for posts")


class PersonalityConfig(BaseModel):
    """Configuration for the agent's personality."""
    system: str = Field("", description="System prompt for personality behavior")
    bio: List[str] = Field(default_factory=list, description="Short bio lines")
    lore: List[str] = Field(default_factory=list, description="Extended backstory entries")
    sop: str = Field("", description="Standard Operating Procedure that must be strictly followed")
    message_examples: List[MessageExample] = Field(
        default_factory=list,
        description="Example dialogues illustrating tone and style",
        alias="messageExamples"
    )
    post_examples: List[str] = Field(
        default_factory=list,
        description="Example standalone posts",
        alias="postExamples"
    )
    topics: List[str] = Field(default_factory=list, description="Preferred discussion topics")
    style: StyleConfig = Field(default_factory=StyleConfig, description="Detailed style settings")
    adjectives: List[str] = Field(default_factory=list, description="Descriptive adjectives")
    extends: List[str] = Field(default_factory=list, description="Parent personality configs to extend")

    @validator("system")
    def no_emojis(cls, v: str) -> str:
        """Ensure system prompt contains no emojis."""
        if any(ord(ch) > 10000 for ch in v):
            raise ValueError("system prompt must not contain emojis")
        return v

    class Config:
        """Pydantic model configuration."""
        validate_default = True
