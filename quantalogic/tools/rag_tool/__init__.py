"""
RAG Tool and related components.

This module provides tools and utilities for Retrieval-Augmented Generation (RAG).
"""

from loguru import logger

# Explicit imports of all tools in the module
# from .document_metadata import DocumentMetadata
# from .query_response import QueryResponse 
#from .rag_tool_beta import RagToolBeta
# from .Document_rag_hf import RagToolHf
#from .document_rag_sources import RagToolHf
from .document_rag_sources_ import RagToolHf
from .openai_legal_rag import OpenAILegalRAG
# from .hybride_search import RagToolHf

# Define __all__ to control what is imported with `from ... import *`
__all__ = [
    # 'DocumentMetadata',
    # 'QueryResponse', 
    # 'RagToolBeta',
    'RagToolHf',
    'OpenAILegalRAG'
]

# Optional: Add logging for import confirmation
logger.info("RAG tools module initialized successfully.")
