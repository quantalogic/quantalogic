"""RAG (Retrieval Augmented Generation) Tool using LlamaIndex.

This tool provides a flexible RAG implementation supporting multiple vector stores
and embedding models, with configurable document processing options.
"""

import os
from enum import Enum
from typing import Any, List, Optional

import chromadb
from llama_index.core import (
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.core.settings import Settings
from llama_index.embeddings.bedrock import BedrockEmbedding
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.embeddings.instructor import InstructorEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.vector_stores.faiss import FaissVectorStore
from loguru import logger

from quantalogic.tools.tool import Tool, ToolArgument


class VectorStoreType(str, Enum):
    """Supported vector store types."""
    CHROMA = "chroma"
    FAISS = "faiss"

class EmbeddingType(str, Enum):
    """Supported embedding model types."""
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"
    INSTRUCTOR = "instructor"
    BEDROCK = "bedrock"

class RagTool(Tool):
    """Tool for performing RAG operations using LlamaIndex."""

    name: str = "rag_tool"
    description: str = (
        "Retrieval Augmented Generation (RAG) tool for querying indexed documents "
        "using vector stores and embedding models."
    )
    arguments: List[ToolArgument] = [
        ToolArgument(
            name="query",
            arg_type="string",
            description="Query string for searching the index",
            required=True,
            example="What is the main topic?",
        ),
    ]

    def __init__(
        self,
        vector_store: str = "chroma",
        embedding_model: str = "openai",
        persist_dir: str = "./storage/rag",
        document_paths: Optional[List[str]] = None,
    ):
        """Initialize the RAG tool with vector store, embedding model, and optional documents.

        Args:
            vector_store: Vector store type (chroma, faiss)
            embedding_model: Embedding model type (openai, huggingface, instructor, bedrock)
            persist_dir: Directory for persistence
            document_paths: Optional list of paths to documents or directories to index
        """
        super().__init__()
        self.persist_dir = os.path.abspath(persist_dir)
        self.embed_model = self._setup_embedding_model(embedding_model)
        self.vector_store = self._setup_vector_store(vector_store, self.persist_dir)
        
        # Configure llama-index settings with the embedding model
        Settings.embed_model = self.embed_model
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        
        # Initialize index
        self.index = None
        
        # Check if we have documents to initialize with
        if document_paths:
            self._initialize_with_documents(document_paths)
        else:
            # Only try to load existing index if no documents were provided
            index_exists = os.path.exists(os.path.join(self.persist_dir, "docstore.json"))
            if index_exists:
                try:
                    self.index = load_index_from_storage(
                        storage_context=self.storage_context,
                    )
                    logger.info(f"Loaded existing index from {self.persist_dir}")
                except Exception as e:
                    logger.error(f"Failed to load existing index: {str(e)}")
                    self.index = None
            else:
                logger.warning("No existing index found and no documents provided")

    def _initialize_with_documents(self, document_paths: List[str]) -> None:
        """Initialize the index with the given documents.

        Args:
            document_paths: List of paths to documents or directories
        """
        try:
            all_documents = []
            for path in document_paths:
                if not os.path.exists(path):
                    logger.warning(f"Document path does not exist: {path}")
                    continue
                    
                documents = SimpleDirectoryReader(
                    input_files=[path] if os.path.isfile(path) else None,
                    input_dir=path if os.path.isdir(path) else None,
                ).load_data()
                all_documents.extend(documents)
            
            if all_documents:
                self.index = VectorStoreIndex.from_documents(
                    all_documents,
                    storage_context=self.storage_context,
                )
                # Persist the index after creation
                self.storage_context.persist(persist_dir=self.persist_dir)
                logger.info(f"Created and persisted new index with {len(all_documents)} documents")
            else:
                logger.warning("No valid documents found in provided paths")
                
        except Exception as e:
            logger.error(f"Error initializing with documents: {str(e)}")
            raise RuntimeError(f"Failed to initialize with documents: {str(e)}")

    def _setup_embedding_model(self, model_type: str) -> Any:
        """Set up the embedding model based on type.

        Args:
            model_type: Type of embedding model to use

        Returns:
            Configured embedding model instance
        """
        model_type = EmbeddingType(model_type.lower())
        if model_type == EmbeddingType.OPENAI:
            return OpenAIEmbedding()
        elif model_type == EmbeddingType.HUGGINGFACE:
            return HuggingFaceEmbedding()
        elif model_type == EmbeddingType.INSTRUCTOR:
            return InstructorEmbedding()
        elif model_type == EmbeddingType.BEDROCK:
            return BedrockEmbedding()
        else:
            raise ValueError(f"Unsupported embedding model type: {model_type}")

    def _setup_vector_store(self, store_type: str, persist_dir: str) -> Any:
        """Set up the vector store based on type.

        Args:
            store_type: Type of vector store to use
            persist_dir: Directory for persistence

        Returns:
            Configured vector store instance
        """
        store_type = VectorStoreType(store_type.lower())
        
        # Ensure the persist directory exists
        os.makedirs(persist_dir, exist_ok=True)
        
        if store_type == VectorStoreType.CHROMA:
            # Use PersistentClient with explicit settings
            chroma_persist_dir = os.path.join(persist_dir, "chroma")
            os.makedirs(chroma_persist_dir, exist_ok=True)
            
            chroma_client = chromadb.PersistentClient(
                path=chroma_persist_dir,
            )
            collection = chroma_client.create_collection(
                name="default_collection",
                get_or_create=True
            )
            return ChromaVectorStore(
                chroma_collection=collection,
            )
        elif store_type == VectorStoreType.FAISS:
            return FaissVectorStore()
        else:
            raise ValueError(f"Unsupported vector store type: {store_type}")

    def add_documents(self, document_path: str) -> bool:
        """Add documents to the RAG system.

        Args:
            document_path: Path to document or directory of documents

        Returns:
            bool: True if documents were added successfully
        """
        try:
            if not os.path.exists(document_path):
                logger.error(f"Document path does not exist: {document_path}")
                return False

            documents = SimpleDirectoryReader(
                input_files=[document_path] if os.path.isfile(document_path) else None,
                input_dir=document_path if os.path.isdir(document_path) else None,
            ).load_data()

            # Create index with configured settings and storage context
            self.index = VectorStoreIndex.from_documents(
                documents,
                storage_context=self.storage_context,
            )
            
            return True
        except Exception as e:
            logger.error(f"Error adding documents: {str(e)}")
            return False

    def execute(self, query: str) -> str:
        """Execute a query against the indexed documents.

        Args:
            query: Query string for searching

        Returns:
            Query response

        Raises:
            ValueError: If no index is available
        """
        try:
            if not self.index:
                raise ValueError("No index available. Please add documents first using add_documents()")

            # Query the index
            query_engine = self.index.as_query_engine()
            response = query_engine.query(query)
            return str(response)

        except Exception as e:
            logger.error(f"Error in RAG query: {str(e)}")
            raise RuntimeError(f"Query failed: {str(e)}")


if __name__ == "__main__":
    # Example usage
    tool = RagTool(
        vector_store="chroma",
        embedding_model="openai",
        persist_dir="./storage/rag",
        document_paths=[
            "./docs/file1.pdf",
            "./docs/directory1"
        ]
    )
    
    # Query
    print(tool.execute("What is the main topic?"))
