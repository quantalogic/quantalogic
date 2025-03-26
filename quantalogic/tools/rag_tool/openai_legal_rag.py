"""OpenAI-powered RAG Tool optimized for legal document retrieval.

This tool provides enhanced RAG capabilities with:
- OpenAI embeddings for superior semantic understanding
- Optimized chunking strategy for legal documents
- Advanced reranking using hybrid search
- Persistent ChromaDB storage
- Enhanced response formatting with legal context
"""

import os
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
import json
from datetime import datetime
import textwrap
import asyncio
import shutil

import chromadb
from openai import OpenAI, AsyncOpenAI
import tiktoken
from llama_index.core import (
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
    Document,
)
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.readers.file.docs import PDFReader
from rank_bm25 import BM25Okapi
from sklearn.preprocessing import MinMaxScaler
import numpy as np
from loguru import logger

from quantalogic.tools.tool import Tool, ToolArgument

# Configure tool-specific logging
logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
)

@dataclass
class LegalSource:
    """Structured representation of a legal source."""
    content: str
    file_name: str
    section: str
    article_number: Optional[str] = None
    reference_id: Optional[str] = None
    score: Optional[float] = None
    metadata: Dict[str, Any] = None

class OpenAILegalRAG(Tool):
    """Enhanced OpenAI-powered RAG tool for legal document retrieval."""

    name: str = "openai_legal_rag"
    description: str = (
        "Advanced RAG tool optimized for legal document retrieval using OpenAI embeddings "
        "with enhanced chunking and hybrid search capabilities."
    )
    arguments: List[ToolArgument] = [
        ToolArgument(
            name="query",
            arg_type="string",
            description="Legal query to search for relevant articles and sections",
            required=True,
            example="What are the requirements for filing a civil lawsuit?",
        ),
        ToolArgument(
            name="max_sources",
            arg_type="int",
            description="Maximum number of legal sources to return",
            required=False,
            default="20",
        ),
        ToolArgument(
            name="min_relevance",
            arg_type="float",
            description="Minimum relevance score (0-1) for returned sources",
            required=False,
            default="0.1",
        ),
    ]

    def __init__(
        self,
        name: str = "openai_legal_rag",
        persist_dir: str = "./storage/openai_legal_rag",
        document_paths: Optional[List[str]] = None,
        openai_api_key: Optional[str] = None,
        embedding_model: str = "text-embedding-3-small",
        chunk_size: int = 512,
        chunk_overlap: int = 128,
        bm25_weight: float = 0.3,
        embedding_weight: float = 0.7,
        force_reindex: bool = False,
        cache_embeddings: bool = True
    ):
        """Initialize the OpenAI-powered legal RAG tool.
        
        Args:
            name: Tool name
            persist_dir: Directory for storing embeddings and index
            document_paths: List of paths to legal documents
            openai_api_key: OpenAI API key (defaults to env var)
            embedding_model: OpenAI embedding model to use
            chunk_size: Size of text chunks for embedding
            chunk_overlap: Overlap between chunks
            bm25_weight: Weight for BM25 scores in hybrid search
            embedding_weight: Weight for embedding scores
            force_reindex: Force rebuild of index
            cache_embeddings: Whether to cache embeddings
        """
        super().__init__()
        self.name = name
        self.persist_dir = os.path.abspath(persist_dir)
        self.embedding_model = embedding_model
        self.force_reindex = force_reindex
        self.bm25_weight = bm25_weight
        self.embedding_weight = embedding_weight
        
        # Initialize OpenAI clients
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.async_openai_client = AsyncOpenAI(api_key=openai_api_key)
        
        # Initialize embedding model
        self.embed_model = OpenAIEmbedding(
            model=embedding_model,
            api_key=openai_api_key,
            cache_path=os.path.join(persist_dir, "embedding_cache") if cache_embeddings else None
        )
        
        # Setup ChromaDB
        chroma_persist_dir = os.path.join(self.persist_dir, "chroma")
        os.makedirs(chroma_persist_dir, exist_ok=True)
        chroma_client = chromadb.PersistentClient(path=chroma_persist_dir)
        collection = chroma_client.create_collection(
            name="legal_collection",
            get_or_create=True
        )
        
        self.vector_store = ChromaVectorStore(chroma_collection=collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        
        # Initialize text splitter with legal-specific settings
        self.text_splitter = self._create_legal_text_splitter(chunk_size, chunk_overlap)
        
        # Initialize or load index
        self.index = self._initialize_index(document_paths)
        
        # Initialize BM25 components
        self.bm25_index = None
        self.document_store = []
        
        if document_paths:
            self._build_hybrid_index(document_paths)

    def _create_legal_text_splitter(self, chunk_size: int, chunk_overlap: int) -> SentenceSplitter:
        """Create a text splitter optimized for legal documents."""
        return SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            paragraph_separator="\n\n",
            tokenizer=self._get_legal_tokenizer()
        )

    def _get_legal_tokenizer(self):
        """Create a tokenizer optimized for legal text."""
        enc = tiktoken.encoding_for_model("gpt-4")
        
        def legal_tokenizer(text: str) -> List[str]:
            # Clean and normalize text
            text = text.replace('\n', ' ').strip()
            
            # Preserve legal references and numbers
            text = text.replace('.', ' . ')
            text = text.replace('§', ' § ')
            
            # Tokenize
            tokens = enc.encode(text)
            return [t for t in enc.decode_tokens_bytes(tokens)]
        
        return legal_tokenizer

    def _extract_legal_metadata(self, text: str) -> Dict[str, Any]:
        """Extract legal metadata from text."""
        metadata = {}
        
        # Extract article numbers
        import re
        article_match = re.search(r'Article[s]?\s+(\d+[-\d]*)', text)
        if article_match:
            metadata['article_number'] = article_match.group(1)
            
        # Extract section information
        section_match = re.search(r'Section\s+(\d+[-\d]*)', text)
        if section_match:
            metadata['section'] = section_match.group(1)
            
        # Extract legal references
        ref_patterns = [
            r'(?:loi|décret|arrêté|Act|Article|Art)\s+n[°o]?\s*(\d+[-./]\d+)',  # French
            r'(?:قانون|مرسوم|قرار)\s+(?:رقم\s+)?(\d+[-./]\d+)',  # Arabic
            r'(?:law|decree)\s+(?:no\.\s+)?(\d+[-./]\d+)'        # English
        ]
        
        for pattern in ref_patterns:
            ref_match = re.search(pattern, text, re.IGNORECASE)
            if ref_match:
                metadata['reference_id'] = ref_match.group(1)
                break
                
        return metadata

    def _build_hybrid_index(self, document_paths: List[str]):
        """Build both embedding and BM25 indices."""
        documents = self._load_documents(document_paths)
        
        # Store documents and their text for BM25
        tokenized_corpus = []
        self.document_store = []  # Reset document store
        
        # Process each document's chunks using the text splitter
        for doc in documents:
            chunks = self.text_splitter.split_text(doc.text)
            
            for chunk in chunks:
                # Process text for BM25
                text = chunk.lower()
                tokens = text.split()
                
                # Store document info with the exact chunk text
                self.document_store.append({
                    'text': chunk,  # Store original chunk text
                    'metadata': doc.metadata,
                    'tokens': tokens
                })
                
                tokenized_corpus.append(tokens)
        
        # Create BM25 index from tokenized chunks
        self.bm25_index = BM25Okapi(tokenized_corpus)
        
        # Create or update embedding index
        if not self.index or self.force_reindex:
            self._create_index(documents)

    def _load_documents(self, document_paths: List[str]) -> List[Document]:
        """Load and preprocess legal documents."""
        all_documents = []
        
        for path in document_paths:
            if not os.path.exists(path):
                logger.warning(f"Document path does not exist: {path}")
                continue
                
            try:
                if path.lower().endswith('.pdf'):
                    docs = PDFReader().load_data(path)
                else:
                    docs = SimpleDirectoryReader(
                        input_files=[path],
                        filename_as_id=True
                    ).load_data()
                
                # Process each document
                processed_docs = []
                for doc in docs:
                    # Clean text
                    text = self._preprocess_legal_text(doc.text)
                    
                    # Extract metadata
                    metadata = self._extract_legal_metadata(text)
                    metadata.update(doc.metadata)
                    metadata['file_name'] = os.path.basename(path)
                    metadata['file_path'] = path
                    
                    processed_doc = Document(
                        text=text,
                        metadata=metadata
                    )
                    processed_docs.append(processed_doc)
                    
                all_documents.extend(processed_docs)
                
            except Exception as e:
                logger.error(f"Error loading document {path}: {str(e)}")
                continue
                
        return all_documents

    def _preprocess_legal_text(self, text: str) -> str:
        """Preprocess legal text for better quality."""
        # Clean whitespace
        text = ' '.join(text.split())
        
        # Fix common OCR issues
        text = text.replace('|', 'I')
        text = text.replace('0', 'O')
        
        # Normalize section markers
        text = text.replace('§', 'Section')
        
        # Wrap text
        text = textwrap.fill(text, width=80)
        
        return text

    def _create_index(self, documents: List[Document]) -> VectorStoreIndex:
        """Create vector store index from documents."""
        try:
            if not documents:
                logger.warning("No valid documents provided")
                return None
                
            logger.info("Creating vector index...")
            index = VectorStoreIndex.from_documents(
                documents,
                storage_context=self.storage_context,
                transformations=[self.text_splitter],
                show_progress=True
            )
            
            self.storage_context.persist(persist_dir=self.persist_dir)
            logger.info(f"Created and persisted index with {len(documents)} documents")
            
            return index
            
        except Exception as e:
            logger.error(f"Error creating index: {str(e)}")
            return None

    def _initialize_index(self, document_paths: Optional[List[str]]) -> Optional[VectorStoreIndex]:
        """Initialize or load the vector index."""
        logger.info("Initializing index...")
        
        if document_paths:
            documents = self._load_documents(document_paths)
            return self._create_index(documents)
        
        # Try loading existing index
        index_path = os.path.join(self.persist_dir, "docstore.json")
        if os.path.exists(index_path):
            try:
                return load_index_from_storage(storage_context=self.storage_context)
            except Exception as e:
                logger.error(f"Failed to load existing index: {str(e)}")
        
        return None

    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """Normalize scores to range [0, 1]."""
        if not scores:
            return scores
        scaler = MinMaxScaler()
        normalized = scaler.fit_transform(np.array(scores).reshape(-1, 1))
        return normalized.flatten().tolist()

    def execute(self, query: str, max_sources: int = 10, min_relevance: float = 0.5) -> str:
        """Execute hybrid search for legal documents.
        
        Args:
            query: Legal query to search for
            max_sources: Maximum number of sources to return
            min_relevance: Minimum relevance score threshold
            
        Returns:
            JSON string containing relevant legal sources with metadata
        """
        try:
            if not self.index or not self.bm25_index:
                raise ValueError("Indices not initialized. Please add documents first.")

            logger.info(f"Executing hybrid legal search for query: {query}")
            
            # Get embedding-based results
            query_engine = self.index.as_query_engine(
                similarity_top_k=max_sources * 2,
                node_postprocessors=[
                    SimilarityPostprocessor(similarity_cutoff=min_relevance)
                ],
                response_mode="no_text",
                streaming=True,
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
                if node.score < min_relevance:
                    continue
                
                text = node.node.text.strip()
                if text in seen_texts:
                    continue
                seen_texts.add(text)
                
                # Find corresponding BM25 score
                doc_idx = next(
                    (i for i, doc in enumerate(self.document_store) 
                     if doc['text'].strip() == text),
                    None
                )
                
                if doc_idx is not None:
                    bm25_score = float(bm25_scores[doc_idx])
                else:
                    logger.warning(f"Could not find BM25 score for text: {text[:100]}...")
                    bm25_score = 0.0
                
                # Extract metadata
                metadata = node.node.metadata.copy()
                metadata.update(self._extract_legal_metadata(text))
                
                legal_source = LegalSource(
                    content=text,
                    file_name=metadata.get('file_name', 'Unknown'),
                    section=metadata.get('section', 'N/A'),
                    article_number=metadata.get('article_number'),
                    reference_id=metadata.get('reference_id'),
                    score=float(node.score) if node.score else 0.0,
                    metadata={
                        'bm25_score': bm25_score,
                        'embedding_score': float(node.score) if node.score else 0.0,
                        'query': query,
                        'timestamp': str(datetime.now().isoformat())
                    }
                )
                combined_results.append(legal_source)
            
            # Normalize and combine scores
            if combined_results:
                bm25_scores = [r.metadata['bm25_score'] for r in combined_results]
                embedding_scores = [r.metadata['embedding_score'] for r in combined_results]
                
                normalized_bm25 = self._normalize_scores(bm25_scores)
                normalized_embedding = self._normalize_scores(embedding_scores)
                
                # Calculate combined scores
                for i, result in enumerate(combined_results):
                    result.metadata['bm25_score'] = normalized_bm25[i]
                    result.metadata['embedding_score'] = normalized_embedding[i]
                    result.metadata['combined_score'] = (
                        self.bm25_weight * normalized_bm25[i] +
                        self.embedding_weight * normalized_embedding[i]
                    )
                    result.score = result.metadata['combined_score']
            
            # Sort by combined score and limit results
            combined_results.sort(key=lambda x: x.score or 0, reverse=True)
            combined_results = combined_results[:max_sources]
            
            # Format results for output
            output_results = []
            for result in combined_results:
                output_results.append({
                    'content': result.content,
                    'file_name': result.file_name,
                    'section': result.section,
                    'article_number': result.article_number,
                    'reference_id': result.reference_id,
                    'scores': {
                        'bm25_score': round(result.metadata['bm25_score'], 4),
                        'embedding_score': round(result.metadata['embedding_score'], 4),
                        'combined_score': round(result.metadata['combined_score'], 4)
                    },
                    'metadata': result.metadata
                })
            
            logger.info(f"Found {len(output_results)} relevant legal sources")
            return json.dumps(output_results, indent=4, ensure_ascii=False)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Legal search failed: {error_msg}")
            error_response = {
                'error': error_msg,
                'query': query,
                'timestamp': str(datetime.now().isoformat()),
                'sources': []
            }
            return json.dumps(error_response, indent=4, ensure_ascii=False)

    def format_legal_sources(self, sources: List[LegalSource]) -> str:
        """Format legal sources into a readable markdown string."""
        if not sources:
            return "No relevant legal sources found."

        output = ["# Relevant Legal Sources\n"]
        
        for source in sources:
            # Source header
            header = []
            if source.article_number:
                header.append(f"Article {source.article_number}")
            if source.section:
                header.append(f"Section {source.section}")
            if source.reference_id:
                header.append(f"Ref: {source.reference_id}")
                
            output.append(f"## {' | '.join(header) if header else 'Legal Source'}")
            output.append(f"**Document**: {source.file_name}\n")
            
            # Scores
            if source.score:
                output.append(f"**Relevance**: {round(source.score * 100, 2)}%\n")
            
            # Content
            output.append(f"{source.content}\n")
            output.append("---\n")
        
        return "\n".join(output)

if __name__ == "__main__":
    # Example usage
    tool = OpenAILegalRAG(
        persist_dir="./storage/openai_legal_rag",
        document_paths=[
            "./docs/test/code_civile.md",
            "./docs/test/code_procedure.md"
        ],
        chunk_size=512,
        chunk_overlap=128,
        bm25_weight=0.3,
        embedding_weight=0.7,
        force_reindex=False
    )
    
    # Test queries
    test_queries = [
        "Quels sont les recours légaux en Algérie pour contraindre un voisin à fermer des ouvertures (fenêtres) donnant sur ma propriété ?",
        #"Articles du Code Civil Algérien concernant les ouvertures sur propriétés voisines et protection de la vie privée",
        #"Mon voisin a créé des ouvertures (fenêtres) donnant directement sur ma propriété, ce qui porte atteinte à ma vie privée. Je souhaite faire valoir mes droits et le contraindre à fermer ces ouvertures.",
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        try:
            result = tool.execute(query, max_sources=3, min_relevance=0.2)
            print(result)
        except Exception as e:
            print(f"Error: {str(e)}")
