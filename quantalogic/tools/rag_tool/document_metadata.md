from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Metadata for indexed documents."""
    source_path: str
    file_type: str
    creation_date: datetime
    last_modified: datetime
    chunk_size: int
    overlap: int
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)
