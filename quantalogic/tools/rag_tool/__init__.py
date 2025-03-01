"""
RAG Tool and related components.

This module provides tools and utilities for Retrieval-Augmented Generation (RAG).
"""

from loguru import logger

# Explicit imports of all tools in the module
from .document_metadata import DocumentMetadata
from .query_response import QueryResponse
from .rag_tool import RagTool
from .rag_tool_beta import RagToolBeta

# Define __all__ to control what is imported with `from ... import *`
__all__ = [
    'DocumentMetadata',
    'QueryResponse',
    'RagTool',
    'RagToolBeta',
]

# Optional: Add logging for import confirmation
logger.info("RAG tools module initialized successfully.")
