from dataclasses import dataclass, field
from typing import Any

from nanoid import generate


@dataclass
class Message:
    role: str
    content: str
    nanoid: str = field(default_factory=lambda: generate())

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access to role, content, and nanoid."""
        if key == "role":
            return self.role
        if key == "content":
            return self.content
        if key == "nanoid":
            return self.nanoid
        raise KeyError(f"Message has no key {key}")