from dataclasses import dataclass
from typing import Any

@dataclass
class Message:
    role: str
    content: str

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access to role and content."""
        if key == "role":
            return self.role
        if key == "content":
            return self.content
        raise KeyError(f"Message has no key {key}")
