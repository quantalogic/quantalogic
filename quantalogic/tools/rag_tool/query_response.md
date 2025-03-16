from typing import Any, Dict, List

from pydantic import BaseModel


class QueryResponse(BaseModel):
    """Structured query response with source attribution."""
    answer: str
    sources: List[Dict[str, Any]]
    relevance_scores: List[float]
    total_chunks_searched: int
    query_time_ms: float

    def __len__(self) -> int:
        """Support len() operation by returning length of the answer."""
        return len(self.answer)

    def __str__(self) -> str:
        """String representation of the response."""
        return self.answer
