"""RAG (Retrieval Augmented Generation) Tool using LlamaIndex.

This tool provides a flexible RAG implementation supporting multiple vector stores
and embedding models, with configurable document processing options.
"""

import datetime
import json
import os
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from pydantic import BaseModel, Field

from quantalogic.tools.tool import Tool, ToolArgument

from .document_metadata import DocumentMetadata
from .query_response import QueryResponse


class EmbeddingType(str, Enum):
    """Supported embedding model types."""
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"
    INSTRUCTOR = "instructor"
    BEDROCK = "bedrock"

class VectorStoreType(str, Enum):
    """Supported vector store types."""
    CHROMA = "chroma"
    FAISS = "faiss"

class RagToolConfig(BaseModel):
    """Configuration for RagTool."""
    persist_dir: Optional[str] = None
    chunk_size: int = Field(default=512)
    chunk_overlap: int = Field(default=50)
    similarity_top_k: int = Field(default=4)
    similarity_threshold: float = Field(default=0.6)
    api_key: Optional[str] = None
    vector_store: str = Field(default="chroma")
    embedding_model: str = Field(default="openai")
    document_paths: Optional[List[str]] = None

class RagTool(Tool):
    """Enhanced RAG tool with advanced features and performance optimizations."""

    name: str = "rag_tool"
    description: str = (
        "Advanced RAG tool with metadata tracking, source attribution, "
        "and configurable processing options."
    )
    arguments: List[ToolArgument] = [
        ToolArgument(
            name="query",
            arg_type="string",
            description="Query string for searching the index",
            required=True,
            example="What is the main topic?",
        ),
        ToolArgument(
            name="top_k",
            arg_type="int",
            description="Number of top results to consider",
            required=False,
            example="5",
        ),
        ToolArgument(
            name="similarity_threshold",
            arg_type="float",
            description="Minimum similarity score (0-1)",
            required=False,
            example="0.7",
        ),
    ]

    def __init__(
        self,
        vector_store: str = "chroma",
        embedding_model: str = "openai",
        persist_dir: str = None,
        document_paths: List[str] = None,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        similarity_top_k: int = 4,
        similarity_threshold: float = 0.6,
        api_key: str = None,
    ):
        """Initialize the RAG tool with custom settings.

        Args:
            vector_store: Type of vector store to use
            embedding_model: Type of embedding model to use
            persist_dir: Directory to persist the index
            document_paths: List of paths to documents to index
            chunk_size: Size of text chunks for processing
            chunk_overlap: Overlap between chunks
            similarity_top_k: Number of similar chunks to retrieve
            similarity_threshold: Minimum similarity score threshold
            api_key: OpenAI API key for embeddings
        """
        super().__init__()
        
        # Initialize config
        self._config = RagToolConfig(
            persist_dir=persist_dir,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            similarity_top_k=similarity_top_k,
            similarity_threshold=similarity_threshold,
            api_key=api_key,
            vector_store=vector_store,
            embedding_model=embedding_model,
            document_paths=document_paths
        )
        
        # Store instance attributes without loading dependencies yet
        self._index = None
        self._vector_store = None
        self._storage_context = None
        self._document_metadata = {}
        self._dependencies_loaded = False

    def _load_dependencies(self):
        """Lazily load heavy dependencies."""
        if not self._dependencies_loaded:
            global VectorStoreIndex, Document, StorageContext, SentenceSplitter, VectorIndexRetriever
            global SimilarityPostprocessor, KeywordNodePostprocessor, Settings, SimpleNodeParser
            global OpenAIEmbedding, HuggingFaceEmbedding, InstructorEmbedding, BedrockEmbedding
            global ChromaVectorStore, FaissVectorStore, PersistentClient
            
            from chromadb import PersistentClient
            from llama_index.core import (
                Document,
                KeywordNodePostprocessor,
                SentenceSplitter,
                Settings,
                SimilarityPostprocessor,
                SimpleNodeParser,
                StorageContext,
                VectorIndexRetriever,
                VectorStoreIndex,
            )
            from llama_index.embeddings.bedrock import BedrockEmbedding
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding
            from llama_index.embeddings.instructor import InstructorEmbedding
            from llama_index.embeddings.openai import OpenAIEmbedding
            from llama_index.vector_stores.chroma import ChromaVectorStore
            from llama_index.vector_stores.faiss import FaissVectorStore
            
            self._dependencies_loaded = True
            self._setup_components()

    def _setup_components(self):
        """Configure embeddings and settings."""
        self._load_dependencies()  # Ensure dependencies are loaded
        
        # Create storage context
        self._storage_context = StorageContext.from_defaults(
            vector_store=self._vector_store
        )

        # Configure embeddings
        embed_model = self._setup_embedding_model(self._config.embedding_model)
        
        # Initialize settings with our configuration
        settings = Settings(
            embed_model=embed_model,
            node_parser=SimpleNodeParser.from_defaults(
                chunk_size=self._config.chunk_size,
                chunk_overlap=self._config.chunk_overlap
            ),
            chunk_size=self._config.chunk_size,
            chunk_overlap=self._config.chunk_overlap,
        )
        Settings.instance = settings

        # Load existing index if available
        if self._config.persist_dir and os.path.exists(self._config.persist_dir):
            try:
                storage_context = StorageContext.from_defaults(
                    persist_dir=self._config.persist_dir
                )
                self._index = VectorStoreIndex.load_from_storage(
                    storage_context,
                )
                logger.info(f"Loaded existing index from {self._config.persist_dir}")
            except Exception as e:
                logger.error(f"Error loading index: {str(e)}")
                self._index = None

        # Initialize vector store
        self._vector_store = self._setup_vector_store(
            self._config.vector_store, 
            self._config.persist_dir
        )

        # Initialize with documents if provided
        if self._config.document_paths:
            self.initialize_with_documents(self._config.document_paths)

    def _setup_embedding_model(self, model_type: str) -> Any:
        """Set up the embedding model based on type.

        Args:
            model_type: Type of embedding model to use

        Returns:
            Configured embedding model instance
        """
        self._load_dependencies()  # Ensure dependencies are loaded
        model_type = EmbeddingType(model_type.lower())
        if model_type == EmbeddingType.OPENAI:
            return OpenAIEmbedding(api_key=self._config.api_key)
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
        self._load_dependencies()  # Ensure dependencies are loaded
        store_type = VectorStoreType(store_type.lower())
        
        # Ensure the persist directory exists
        os.makedirs(persist_dir, exist_ok=True)
        
        if store_type == VectorStoreType.CHROMA:
            # Use PersistentClient with explicit settings
            chroma_persist_dir = os.path.join(persist_dir, "chroma")
            os.makedirs(chroma_persist_dir, exist_ok=True)
            
            chroma_client = PersistentClient(
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

    def _load_existing_index(self):
        """Load existing index and metadata if available."""
        self._load_dependencies()  # Ensure dependencies are loaded
        try:
            metadata_path = os.path.join(self._config.persist_dir, "metadata.json")
            if os.path.exists(metadata_path):
                with open(metadata_path) as f:
                    self._document_metadata = json.load(f)
            
            if os.path.exists(os.path.join(self._config.persist_dir, "docstore.json")):
                self._index = VectorStoreIndex.load_from_storage(
                    storage_context=StorageContext.from_defaults(vector_store=self._vector_store),
                )
                logger.info(f"Loaded existing index from {self._config.persist_dir}")
        except Exception as e:
            logger.error(f"Failed to load existing index: {str(e)}")
            self._index = None

    def _save_metadata(self):
        """Save document metadata to disk."""
        try:
            metadata_path = os.path.join(self._config.persist_dir, "metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump(self._document_metadata, f)
        except Exception as e:
            logger.error(f"Failed to save metadata: {str(e)}")

    def _process_document(self, doc_path: str) -> List[Dict[str, Any]]:
        """Process a document with advanced chunking and metadata extraction.

        Args:
            doc_path: Path to the document

        Returns:
            List of processed document chunks
        """
        self._load_dependencies()  # Ensure dependencies are loaded
        file_stats = os.stat(doc_path)
        metadata = DocumentMetadata(
            source_path=doc_path,
            file_type=os.path.splitext(doc_path)[1],
            creation_date=datetime.fromtimestamp(file_stats.st_ctime),
            last_modified=datetime.fromtimestamp(file_stats.st_mtime),
            chunk_size=self._config.chunk_size,
            overlap=self._config.chunk_overlap,
        )
        
        # Load and chunk document
        from llama_index.core import SimpleDirectoryReader  # Lazy import
        reader = SimpleDirectoryReader(
            input_files=[doc_path],
            file_metadata=lambda x: metadata.dict(),
        )
        documents = reader.load_data()
        
        # Store metadata
        self._document_metadata[doc_path] = metadata.dict()
        return documents

    def add_documents(self, document_path: str, custom_metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Add documents with metadata tracking.

        Args:
            document_path: Path to document or directory
            custom_metadata: Optional custom metadata to associate

        Returns:
            bool: Success status
        """
        self._load_dependencies()  # Ensure dependencies are loaded
        try:
            if not os.path.exists(document_path):
                logger.error(f"Document path does not exist: {document_path}")
                return False

            # Process documents with metadata
            documents = []
            if os.path.isfile(document_path):
                documents.extend(self._process_document(document_path))
            else:
                for root, _, files in os.walk(document_path):
                    for file in files:
                        doc_path = os.path.join(root, file)
                        documents.extend(self._process_document(doc_path))

            # Update metadata with custom fields
            if custom_metadata:
                for doc_path in self._document_metadata:
                    self._document_metadata[doc_path]["custom_metadata"] = custom_metadata

            # Create or update index
            if self._index is None:
                self._index = VectorStoreIndex.from_documents(
                    documents,
                    storage_context=StorageContext.from_defaults(vector_store=self._vector_store),
                )
            else:
                self._index.insert_nodes(documents)

            # Save metadata
            self._save_metadata()
            return True

        except Exception as e:
            logger.error(f"Error adding documents: {str(e)}")
            return False

    def _create_retriever(self, top_k: int) -> 'VectorIndexRetriever':
        """Create an optimized retriever for document search.

        Args:
            top_k: Number of results to retrieve

        Returns:
            Configured retriever instance
        """
        self._load_dependencies()  # Ensure dependencies are loaded
        return VectorIndexRetriever(
            index=self._index,
            similarity_top_k=top_k * 2,  # Get more candidates for better filtering
            filters=None
        )

    def _create_query_engine(self, retriever: 'VectorIndexRetriever', threshold: float):
        """Create a query engine with advanced processing.

        Args:
            retriever: Configured retriever instance
            threshold: Similarity threshold for filtering

        Returns:
            Configured query engine
        """
        self._load_dependencies()  # Ensure dependencies are loaded
        return self._index.as_query_engine(
            retriever=retriever,
            node_postprocessors=[
                SimilarityPostprocessor(similarity_cutoff=threshold),
                KeywordNodePostprocessor(required_keywords=[])
            ],
            response_mode="compact",
            service_context=Settings.instance.service_context
        )

    def _process_source_nodes(
        self,
        source_nodes: List[Any],
        top_k: int
    ) -> Tuple[List[Dict[str, Any]], List[float]]:
        """Process and extract information from source nodes.

        Args:
            source_nodes: List of source nodes
            top_k: Number of top results to return

        Returns:
            Tuple of (sources, scores)
        """
        self._load_dependencies()  # Ensure dependencies are loaded
        # Sort by score and take top_k
        nodes = sorted(
            source_nodes,
            key=lambda x: x.score if hasattr(x, 'score') else 0,
            reverse=True
        )[:top_k]

        sources = []
        scores = []
        
        for node in nodes:
            metadata = node.node.metadata
            source_info = {
                "content": node.node.text,
                "source_path": metadata.get("source_path", "Unknown"),
                "chunk_index": metadata.get("chunk_index", 0),
                "file_type": metadata.get("file_type", "Unknown"),
                "page_number": metadata.get("page_number", None),
                "section": metadata.get("section", None)
            }
            sources.append(source_info)
            scores.append(node.score if hasattr(node, 'score') else 0.0)

        return sources, scores

    def execute(
        self,
        query: str,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
    ) -> QueryResponse:
        """Execute a query against the indexed documents.
        
        Args:
            query: Query string
            top_k: Optional number of results to return
            similarity_threshold: Optional similarity threshold
            
        Returns:
            QueryResponse with answer and sources
        """
        self._load_dependencies()  # Ensure dependencies are loaded
        start_time = time.time()
        try:
            if not self._index:
                logger.error("No index available. Please add documents first.")
                return QueryResponse(
                    answer="No documents have been indexed yet. Please add documents first.",
                    sources=[],
                    relevance_scores=[],
                    total_chunks_searched=0,
                    query_time_ms=round((time.time() - start_time) * 1000, 2)
                )

            # Configure parameters
            top_k = top_k or self._config.similarity_top_k
            threshold = similarity_threshold or self._config.similarity_threshold

            # Set up retrieval pipeline
            retriever = self._create_retriever(top_k)
            query_engine = self._create_query_engine(retriever, threshold)

            # Execute query
            response = query_engine.query(query)
            
            if not hasattr(response, 'source_nodes') or not response.source_nodes:
                logger.warning(
                    f"Query '{query}' returned no results "
                    f"(top_k={top_k}, threshold={threshold})"
                )
                return QueryResponse(
                    answer="No relevant information found. Try adjusting the similarity threshold or increasing top_k.",
                    sources=[],
                    relevance_scores=[],
                    total_chunks_searched=0,
                    query_time_ms=round((time.time() - start_time) * 1000, 2)
                )
            
            # Process results
            sources, scores = self._process_source_nodes(
                response.source_nodes,
                top_k
            )

            return QueryResponse(
                answer=str(response),
                sources=sources,
                relevance_scores=scores,
                total_chunks_searched=len(response.source_nodes),
                query_time_ms=round((time.time() - start_time) * 1000, 2)
            )

        except Exception as e:
            logger.error(f"Error in RAG query: {str(e)}")
            return QueryResponse(
                answer=f"An error occurred while processing your query: {str(e)}",
                sources=[],
                relevance_scores=[],
                total_chunks_searched=0,
                query_time_ms=round((time.time() - start_time) * 1000, 2)
            )

    def initialize_with_documents(self, document_paths: List[str]) -> None:
        """Initialize the index with the given documents.
        
        Args:
            document_paths: List of paths to documents to index
        """
        self._load_dependencies()  # Ensure dependencies are loaded
        try:
            all_documents = []
            for doc_path in document_paths:
                documents = self._process_document(doc_path)
                all_documents.extend(documents)
            
            if all_documents:
                self._index = VectorStoreIndex.from_documents(
                    all_documents,
                    storage_context=self._storage_context,
                )
                
                if self._config.persist_dir:
                    self._storage_context.persist(persist_dir=self._config.persist_dir)
                    logger.info(f"Created and persisted new index with {len(all_documents)} documents")
            else:
                logger.warning("No valid documents found in provided paths")
                
        except Exception as e:
            logger.error(f"Error initializing with documents: {str(e)}")
            raise RuntimeError(f"Failed to initialize with documents: {str(e)}")


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