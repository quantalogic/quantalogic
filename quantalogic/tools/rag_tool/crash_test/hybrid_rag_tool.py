"""
Hybrid RAG Tool optimized for legal document search with BM25 and embeddings support.

Features:
- Hybrid search combining BM25 and dense embeddings
- Optimized for legal documents in multiple languages
- Enhanced text preprocessing and chunking
- Batched operations for better performance
- Persistent storage with ChromaDB
"""

import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import json
from datetime import datetime
import shutil
import asyncio

import chromadb
from sentence_transformers import SentenceTransformer
from llama_index.core import (
    Document, VectorStoreIndex, StorageContext,
    load_index_from_storage, Settings
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.node_parser import SentenceSplitter
from llama_index.readers.file.docs import PDFReader
from rank_bm25 import BM25Okapi
from sklearn.preprocessing import MinMaxScaler
import numpy as np
from loguru import logger
from quantalogic.tools.tool import Tool, ToolArgument

# Configure logging
logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
)

@dataclass
class SearchResult:
    """Represents a search result with detailed scoring."""
    content: str
    file_name: str
    page_number: str
    reference_number: Optional[str] = None
    bm25_score: float = 0.0
    embedding_score: float = 0.0
    combined_score: float = 0.0
    metadata: Dict[str, Any] = None
    text_chunks: List[str] = None
    source_text: str = None

class HybridRagTool(Tool):
    """Advanced Hybrid RAG Tool for legal document search."""
    
    name: str = "hybrid_rag_tool"
    description: str = (
        "Advanced RAG tool combining BM25 and embeddings for precise "
        "legal document search with detailed source attribution."
    )
    arguments: List[ToolArgument] = [
        ToolArgument(
            name="query",
            arg_type="string",
            description="Search query for finding relevant legal sources",
            required=True,
            example="Find articles related to environmental protection",
        ),
        ToolArgument(
            name="max_sources",
            arg_type="int",
            description="Maximum number of sources to return",
            required=False,
            example="5",
        ),
        ToolArgument(
            name="min_relevance",
            arg_type="float",
            description="Minimum relevance score (0-1)",
            required=False,
            example="0.5",
        ),
    ]

    def __init__(
        self,
        persist_dir: str = "./storage/hybrid_rag",
        document_paths: Optional[List[str]] = None,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        embed_batch_size: int = 32,
        embed_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        bm25_weight: float = 0.3,
        embedding_weight: float = 0.7,
        min_chunk_length: int = 50,
    ):
        """Initialize the hybrid RAG tool."""
        super().__init__()
        
        self.persist_dir = os.path.abspath(persist_dir)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embed_batch_size = embed_batch_size
        self.bm25_weight = bm25_weight
        self.embedding_weight = embedding_weight
        self.min_chunk_length = min_chunk_length
        
        # Initialize embedding model
        self.embed_model = HuggingFaceEmbedding(
            model_name=embed_model,
            embed_batch_size=embed_batch_size
        )
        
        # Configure ChromaDB
        self._setup_storage()
        
        # Configure llama-index settings
        Settings.embed_model = self.embed_model
        Settings.chunk_size = chunk_size
        Settings.chunk_overlap = chunk_overlap
        
        # Initialize indices
        self.vector_index = None
        self.bm25_index = None
        self.document_store = []
        
        # Build indices if documents provided
        if document_paths:
            self._build_indices(document_paths)

    def _setup_storage(self):
        """Setup ChromaDB storage."""
        chroma_dir = os.path.join(self.persist_dir, "chroma")
        os.makedirs(chroma_dir, exist_ok=True)
        
        chroma_client = chromadb.PersistentClient(path=chroma_dir)
        collection = chroma_client.create_collection(
            name="legal_collection",
            get_or_create=True
        )
        
        self.vector_store = ChromaVectorStore(chroma_collection=collection)
        self.storage_context = StorageContext.from_defaults(
            vector_store=self.vector_store
        )

    def _preprocess_text(self, text: str) -> str:
        """Enhanced text preprocessing."""
        # Remove excessive whitespace
        text = " ".join(text.split())
        
        # Normalize quotes and dashes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace('–', '-').replace('—', '-')
        
        # Handle line breaks
        text = text.replace('\n\n', '[BREAK]')
        text = text.replace('\n', ' ')
        text = text.replace('[BREAK]', '\n\n')
        
        return text.strip()

    def _extract_law_reference(self, text: str) -> Optional[str]:
        """Extract law reference numbers using enhanced patterns."""
        import re
        
        patterns = [
            # French patterns
            r'(?:loi|décret|arrêté)\s+n[°o]?\s*(\d+[-./]\d+)',
            r'article[s]?\s+[LC]?\.*\s*(\d+(?:[-–]\d+)?(?:\s*et\s*\d+)*)',
            
            # Arabic patterns
            r'(?:قانون|مرسوم|قرار)\s+(?:رقم\s+)?(\d+[-./]\d+)',
            r'(?:المادة|الفصل)\s+(\d+(?:[-–]\d+)?)',
            
            # English patterns
            r'(?:law|decree|act)\s+(?:no\.\s+)?(\d+[-./]\d+)',
            r'article[s]?\s+(\d+(?:[-–]\d+)?(?:\s*and\s*\d+)*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None

    def _chunk_document(self, doc: Document) -> List[str]:
        """Chunk document with enhanced splitting."""
        splitter = SentenceSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            tokenizer=lambda x: x.replace("\n", " ").split(" ")
        )
        
        chunks = []
        for chunk in splitter.split_text(doc.text):
            if len(chunk.strip()) >= self.min_chunk_length:
                chunks.append(self._preprocess_text(chunk))
        
        return chunks

    def _build_indices(self, document_paths: List[str]):
        """Build both BM25 and embedding indices."""
        try:
            # Load and process documents
            documents = []
            tokenized_corpus = []
            
            pdf_reader = PDFReader()
            for path in document_paths:
                if not os.path.exists(path):
                    logger.warning(f"Document path does not exist: {path}")
                    continue
                
                try:
                    # Load document
                    if path.lower().endswith('.pdf'):
                        docs = pdf_reader.load_data(path)
                    else:
                        with open(path, 'r', encoding='utf-8') as f:
                            text = f.read()
                            docs = [Document(text=text, metadata={
                                'file_name': os.path.basename(path),
                                'file_path': path
                            })]
                    
                    # Process each document
                    for doc in docs:
                        processed_text = self._preprocess_text(doc.text)
                        chunks = self._chunk_document(Document(text=processed_text))
                        
                        # Store document info
                        doc_info = {
                            'text': processed_text,
                            'chunks': chunks,
                            'metadata': {
                                **doc.metadata,
                                'file_name': os.path.basename(path),
                                'file_path': path
                            }
                        }
                        self.document_store.append(doc_info)
                        
                        # Prepare for BM25
                        for chunk in chunks:
                            tokenized_corpus.append(chunk.lower().split())
                            documents.append(Document(
                                text=chunk,
                                metadata=doc_info['metadata']
                            ))
                
                except Exception as e:
                    logger.error(f"Error processing document {path}: {str(e)}")
                    continue
            
            # Build BM25 index
            self.bm25_index = BM25Okapi(tokenized_corpus)
            
            # Build vector index
            self.vector_index = VectorStoreIndex.from_documents(
                documents,
                storage_context=self.storage_context,
                show_progress=True
            )
            
            # Persist storage
            self.storage_context.persist(persist_dir=self.persist_dir)
            
            logger.info(f"Built indices with {len(documents)} chunks from {len(document_paths)} documents")
            
        except Exception as e:
            logger.error(f"Error building indices: {str(e)}")
            raise

    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """Normalize scores using min-max scaling."""
        if not scores:
            return scores
        scaler = MinMaxScaler()
        normalized = scaler.fit_transform(np.array(scores).reshape(-1, 1))
        return normalized.flatten().tolist()

    def execute(
        self,
        query: str,
        max_sources: int = 5,
        min_relevance: float = 0.3
    ) -> str:
        """Execute hybrid search with enhanced scoring."""
        try:
            if not self.vector_index or not self.bm25_index:
                raise ValueError("Indices not initialized. Please add documents first.")

            logger.info(f"Executing hybrid search for query: {query}")
            
            # Get embedding-based results
            query_engine = self.vector_index.as_query_engine(
                similarity_top_k=max_sources * 2,
                streaming=False,
                verbose=True
            )
            
            embedding_response = query_engine.query(query)
            
            # Get BM25 results
            tokenized_query = query.lower().split()
            bm25_scores = self.bm25_index.get_scores(tokenized_query)
            
            # Combine and rank results
            combined_results = []
            seen_texts = set()
            
            for node in embedding_response.source_nodes:
                text = node.node.text.strip()
                if text in seen_texts:
                    continue
                seen_texts.add(text)
                
                # Find document context
                doc_idx = next(
                    (i for i, doc in enumerate(self.document_store)
                     if any(chunk.strip() == text for chunk in doc['chunks'])),
                    None
                )
                
                if doc_idx is not None:
                    doc_info = self.document_store[doc_idx]
                    chunk_idx = doc_info['chunks'].index(text)
                    bm25_score = bm25_scores[sum(len(d['chunks']) for d in self.document_store[:doc_idx]) + chunk_idx]
                    
                    # Extract surrounding context
                    context_start = max(0, chunk_idx - 1)
                    context_end = min(len(doc_info['chunks']), chunk_idx + 2)
                    context_chunks = doc_info['chunks'][context_start:context_end]
                    
                    result = SearchResult(
                        content=text,
                        file_name=doc_info['metadata']['file_name'],
                        page_number=str(doc_info['metadata'].get('page_number', 'N/A')),
                        reference_number=self._extract_law_reference(text),
                        bm25_score=bm25_score,
                        embedding_score=float(node.score) if node.score else 0.0,
                        text_chunks=context_chunks,
                        source_text=doc_info['text'],
                        metadata={
                            'source_type': 'legal_document',
                            'file_path': doc_info['metadata']['file_path'],
                            'query': query,
                            'timestamp': datetime.now().isoformat()
                        }
                    )
                    combined_results.append(result)
            
            # Normalize and combine scores
            if combined_results:
                bm25_scores = [r.bm25_score for r in combined_results]
                embedding_scores = [r.embedding_score for r in combined_results]
                
                normalized_bm25 = self._normalize_scores(bm25_scores)
                normalized_embedding = self._normalize_scores(embedding_scores)
                
                for i, result in enumerate(combined_results):
                    result.bm25_score = normalized_bm25[i]
                    result.embedding_score = normalized_embedding[i]
                    result.combined_score = (
                        self.bm25_weight * result.bm25_score +
                        self.embedding_weight * result.embedding_score
                    )
            
            # Filter and sort results
            combined_results = [
                r for r in combined_results
                if r.combined_score >= min_relevance
            ]
            combined_results.sort(key=lambda x: x.combined_score, reverse=True)
            combined_results = combined_results[:max_sources]
            
            # Format results for output
            output_results = []
            for result in combined_results:
                output_results.append({
                    'content': result.content,
                    'context': result.text_chunks,
                    'file_name': result.file_name,
                    'page_number': result.page_number,
                    'reference_number': result.reference_number,
                    'scores': {
                        'bm25_score': round(result.bm25_score, 4),
                        'embedding_score': round(result.embedding_score, 4),
                        'combined_score': round(result.combined_score, 4)
                    },
                    'metadata': result.metadata
                })
            
            logger.info(f"Found {len(output_results)} relevant sources")
            return json.dumps(output_results, indent=2, ensure_ascii=False)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Search failed: {error_msg}")
            return json.dumps({
                'error': error_msg,
                'query': query,
                'timestamp': datetime.now().isoformat(),
                'sources': []
            }, indent=2)

if __name__ == "__main__":
    # Example usage
    tool = HybridRagTool(
        persist_dir="./storage/hybrid_rag",
        document_paths=[
            "./docs/test/law1.pdf",
            "./docs/test/law2.pdf"
        ],
        chunk_size=512,
        chunk_overlap=50,
        embed_batch_size=32
    )
    
    # Test queries
    test_queries = [
        "Find articles related to environmental protection",
        "Search for traffic regulations",
        "Look for workplace safety laws"
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        result = tool.execute(query, max_sources=3, min_relevance=0.3)
        print(result)
