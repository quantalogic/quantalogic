"""Enhanced Multilingual Legal RAG Tool using hybrid search and LLM-powered retrieval.

This tool provides advanced RAG capabilities with:
- Query expansion and reformulation using LLM
- Hybrid search (dense + sparse retrieval)
- Cross-encoder reranking
- Semantic chunking for legal documents
- Enhanced prompt engineering
"""

import os
from typing import List, Optional, Dict, Any, Literal, Tuple
from dataclasses import dataclass
from enum import Enum
import json
from datetime import datetime
import shutil
import re
from functools import lru_cache

import chromadb
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi
import nltk
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
from llama_index.core import (
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
    Document,
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.readers.file.docs import PDFReader
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
class LegalContext:
    """Structured information about a legal document."""
    document_type: Optional[str] = None
    jurisdiction: Optional[str] = None
    court_level: Optional[str] = None
    decision_date: Optional[str] = None
    key_concepts: Optional[List[str]] = None
    temporal_info: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {k: v for k, v in self.__dict__.items() if v is not None}

@dataclass
class LegalSource:
    """Structured representation of a legal source."""
    content: str
    file_name: str
    page_number: str
    reference_number: Optional[str] = None
    score: Optional[float] = None
    legal_context: Optional[LegalContext] = None
    metadata: Dict[str, Any] = None

class ResponseMode(str, Enum):
    """Response modes for the legal RAG tool."""
    SOURCES_ONLY = "sources_only"
    CONTEXTUAL_ANSWER = "contextual_answer"
    ANSWER_WITH_SOURCES = "answer_with_sources"

class LegalTextSplitter(SentenceSplitter):
    """Custom text splitter optimized for legal documents."""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 128):
        super().__init__(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            paragraph_separator="\n\n"
        )
        
    def split_text(self, text: str) -> List[str]:
        """Split text while preserving legal document structure."""
        sections = []
        current_section = []
        
        for line in text.split('\n'):
            line = line.strip()
            # Check for legal section markers
            if any(marker in line.lower() for marker in [
    "article",
    "section",
    "§",
    "chapitre"
]):
                if current_section:
                    sections.append('\n'.join(current_section))
                current_section = [line]
            else:
                current_section.append(line)
        
        if current_section:
            sections.append('\n'.join(current_section))
        
        # Apply sentence splitting to each section
        chunks = []
        for section in sections:
            section_chunks = super().split_text(section)
            chunks.extend(section_chunks)
        
        return chunks

class QueryProcessor:
    """Process and expand queries using LLM."""
    
    def __init__(self, model_name: str = "google/flan-t5-base"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        if torch.cuda.is_available():
            self.model = self.model.cuda()
            
    def expand_query(self, query: str) -> List[str]:
        """Expand query using T5 model for better retrieval."""
        prompt = f"Reformulate this legal query in different ways to find relevant legal articles: {query}"
        
        inputs = self.tokenizer(prompt, return_tensors="pt", max_length=512, truncation=True)
        if torch.cuda.is_available():
            inputs = inputs.to("cuda")
            
        outputs = self.model.generate(
            **inputs,
            max_length=150,
            num_return_sequences=3,
            num_beams=5,
            temperature=0.7
        )
        
        expanded_queries = [
            self.tokenizer.decode(output, skip_special_tokens=True)
            for output in outputs
        ]
        
        # Add original query
        expanded_queries.append(query)
        return list(set(expanded_queries))

class HybridRetriever:
    """Hybrid retrieval combining dense and sparse search."""
    
    def __init__(
        self,
        embed_model: HuggingFaceEmbedding,
        cross_encoder_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    ):
        self.embed_model = embed_model
        self.cross_encoder = CrossEncoder(cross_encoder_name)
        self.bm25 = None
        self.documents = []
        
    def index_documents(self, documents: List[Document]):
        """Index documents for hybrid search."""
        self.documents = documents
        # Prepare corpus for BM25
        corpus = [doc.text for doc in documents]
        tokenized_corpus = [doc.split() for doc in corpus]
        self.bm25 = BM25Okapi(tokenized_corpus)
        
    def hybrid_search(
        self,
        query: str,
        vector_results: List[Dict],
        top_k: int = 10
    ) -> List[Dict]:
        """Combine dense and sparse search results."""
        # Get BM25 scores
        tokenized_query = query.split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        # Normalize BM25 scores
        max_bm25 = max(bm25_scores)
        if max_bm25 > 0:
            bm25_scores = [score/max_bm25 for score in bm25_scores]
            
        # Combine scores
        combined_results = []
        for vec_result, bm25_score in zip(vector_results, bm25_scores):
            vec_score = vec_result["score"]
            combined_score = 0.7 * vec_score + 0.3 * bm25_score
            vec_result["score"] = combined_score
            combined_results.append(vec_result)
            
        # Sort by combined score
        combined_results.sort(key=lambda x: x["score"], reverse=True)
        return combined_results[:top_k]
        
    def rerank_results(
        self,
        query: str,
        results: List[Dict],
        top_k: int = 5
    ) -> List[Dict]:
        """Rerank results using cross-encoder."""
        if not results:
            return results
            
        pairs = [(query, result["content"]) for result in results]
        scores = self.cross_encoder.predict(pairs)
        
        for result, score in zip(results, scores):
            result["rerank_score"] = float(score)
            
        results.sort(key=lambda x: x["rerank_score"], reverse=True)
        return results[:top_k]

class LegalEmbeddingRAG(Tool):
    """Enhanced RAG tool specialized for legal document retrieval using embeddings."""

    name: str = "legal_embedding_rag"
    description: str = (
        "Advanced legal RAG tool with query expansion, hybrid search, and reranking. "
        "Provides sources, contextual answers, or both with enhanced relevance."
    )
    arguments: List[ToolArgument] = [
        ToolArgument(
            name="query",
            arg_type="string",
            description="Legal query to search for relevant articles and sections",
            required=True,
            example="Find articles related to property rights",
        ),
        ToolArgument(
            name="max_sources",
            arg_type="int",
            description="Maximum number of sources to return",
            required=False,
            default="10",
        ),
        ToolArgument(
            name="min_relevance",
            arg_type="float",
            description="Minimum relevance score (0-1) for returned sources",
            required=False,
            default="0.1",
        ),
        ToolArgument(
            name="response_mode",
            arg_type="string",
            description="Response mode: 'sources_only', 'contextual_answer', or 'answer_with_sources'",
            required=False,
            default="sources_only",
        ),
    ]

    def __init__(
        self,
        name: str = "legal_embedding_rag",
        persist_dir: str = "./storage/legal_embedding_rag",
        document_paths: Optional[List[str]] = None,
        chunk_size: int = 512,
        chunk_overlap: int = 128,
        embed_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        force_reindex: bool = False
    ):
        """Initialize the enhanced legal RAG tool."""
        super().__init__()
        self.name = name
        self.persist_dir = os.path.abspath(persist_dir)
        self.force_reindex = force_reindex

        # Initialize embedding model
        try:
            self.embed_model = HuggingFaceEmbedding(
                model_name=embed_model,
                embed_batch_size=8
            )
            logger.info(f"Successfully initialized embedding model: {embed_model}")
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {e}")
            raise

        # Initialize query processor and hybrid retriever
        self.query_processor = QueryProcessor()
        self.hybrid_retriever = HybridRetriever(self.embed_model)

        # Setup ChromaDB
        chroma_persist_dir = os.path.join(self.persist_dir, "chroma")
        if force_reindex and os.path.exists(chroma_persist_dir):
            shutil.rmtree(chroma_persist_dir)
        
        os.makedirs(chroma_persist_dir, exist_ok=True)
        chroma_client = chromadb.PersistentClient(path=chroma_persist_dir)
        collection = chroma_client.create_collection(
            name="legal_collection",
            get_or_create=True
        )
        
        self.vector_store = ChromaVectorStore(chroma_collection=collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        
        # Initialize text splitter with semantic chunking
        self.text_splitter = LegalTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        # Initialize or load index
        self.index = self._initialize_index(document_paths)
        if self.index and document_paths:
            # Index documents for hybrid search
            self.hybrid_retriever.index_documents(self._load_documents(document_paths))

    def _extract_legal_metadata(self, text: str) -> Dict[str, Any]:
        """Extract legal metadata from text with enhanced article detection."""
        metadata = {}
        
        # Extract article numbers with improved regex
        import re
        
        # Match Art. XXX format (including Arabic numbers)
        article_pattern = r'Art\.?\s*(\d+(?:\-\d+)?(?:\s*bis\d*)?(?:\s*\w+)?)'
        article_match = re.search(article_pattern, text, re.IGNORECASE)
        if article_match:
            metadata[
    "article_number"
] = article_match.group(1).strip()
            metadata[
    "article_type"
] = 'article'
            
        # Extract section information with improved patterns    
        section_patterns = [
            r'Section\s+(\d+(?:[-\s]*\d+)?)',
            r'Chapitre\s+(\d+(?:[-\s]*\d+)?)',
            r'Titre\s+(\d+(?:[-\s]*\d+)?)'
        ]
        
        for pattern in section_patterns:
            section_match = re.search(pattern, text, re.IGNORECASE)
            if section_match:
                metadata[
    "section"
] = section_match.group(1)
                break
                
        # Extract legal references with improved patterns
        ref_patterns = [
            r'(?:loi|décret|arrêté)\s+n[°o]?\s*(\d+[-./]\d+)',  # French
            r'(?:قانون|مرسوم|قرار)\s+(?:رقم\s+)?(\d+[-./]\d+)',  # Arabic
            r'(?:law|decree)\s+(?:no\.\s+)?(\d+[-./]\d+)'        # English
        ]
        
        for pattern in ref_patterns:
            ref_match = re.search(pattern, text, re.IGNORECASE)
            if ref_match:
                metadata[
    "reference_id"
] = ref_match.group(1)
                break
        
        # Extract modification dates
        date_pattern = r'(?:Modifié par|du)\s+(?:la\s+)?(?:loi\s+)?n[°o]?\s*\d+[-./]\d+\s+du\s+(\d{1,2}\s+\w+\s+\d{4})'
        date_match = re.search(date_pattern, text, re.IGNORECASE)
        if date_match:
            metadata[
    "modification_date"
] = date_match.group(1)
            
        return metadata

    def _preprocess_legal_text(self, text: str) -> str:
        """Preprocess legal text with enhanced article handling."""
        # Clean whitespace
        text = ' '.join(text.split())
        
        # Normalize article markers
        text = re.sub(r'Art\.\s*', 'Art. ', text)
        text = re.sub(r'Article\s+', 'Art. ', text)
        
        # Fix common OCR issues
        text = text.replace('|', 'I')
        text = text.replace('0', 'O')
        
        # Normalize section markers
        text = text.replace('§', 'Section')
        
        return text

    def _load_documents(self, document_paths: List[str]) -> List[Document]:
        """Load and preprocess legal documents."""
        all_documents = []
        pdf_reader = PDFReader()
        
        for path in document_paths:
            if not os.path.exists(path):
                logger.warning(f"Document path does not exist: {path}")
                continue
                
            try:
                if path.lower().endswith('.pdf'):
                    docs = pdf_reader.load_data(path)
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
                    metadata["file_name"] = os.path.basename(path)
                    metadata["file_path"] = path
                    
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

    def _create_index(self, documents: List[Document]) -> Optional[VectorStoreIndex]:
        """Create vector store index from documents with article-based chunking."""
        try:
            if not documents:
                logger.warning("No valid documents provided")
                return None
                
            logger.info("Creating vector index...")
            
            # Process documents to split by articles
            processed_docs = []
            for doc in documents:
                # Split text into articles
                article_splits = re.split(r'(?=Art\.\s*\d+)', doc.text)
                
                for article_text in article_splits:
                    if not article_text.strip():
                        continue
                        
                    # Extract metadata for this article
                    metadata = self._extract_legal_metadata(article_text)
                    metadata.update(doc.metadata)
                    
                    # Create a new document for each article
                    article_doc = Document(
                        text=article_text.strip(),
                        metadata=metadata
                    )
                    processed_docs.append(article_doc)
            
            # Create index with processed documents
            index = VectorStoreIndex.from_documents(
                processed_docs,
                storage_context=self.storage_context,
                transformations=[self.text_splitter],
                show_progress=True
            )
            
            self.storage_context.persist(persist_dir=self.persist_dir)
            logger.info(f"Created and persisted index with {len(processed_docs)} articles")
            
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

    def _generate_contextual_answer(self, query: str, sources: List[Dict]) -> str:
        """Generate an enhanced contextual answer using better prompt engineering."""
        if not sources:
            return "No relevant legal sources found for your query."

        # Sort sources by rerank score if available, else by original score
        sorted_sources = sorted(
            sources,
            key=lambda x: x.get("rerank_score", x["score"]),
            reverse=True
        )
        
        # Build enhanced context
        context_parts = []
        
        # Add most relevant legal provisions
        context_parts.append("Most Relevant Legal Provisions:")
        for source in sorted_sources[:3]:
            context_parts.append(
                f"• {source['article_type']} {source['article_number']}: {source['content']}"
                f" (Relevance: {source.get('rerank_score', source['score']):.3f})"
            )

        # Add temporal context
        dates = [s.get("modification_date") for s in sources if s.get("modification_date") != "N/A"]
        if dates:
            context_parts.append(f"\nTemporal Context:")
            context_parts.append(f"• Most recent modification: {max(dates)}")

        # Group by legal domains/sections
        sections = {}
        for source in sources:
            section = source.get("section", "General")
            if section not in sections:
                sections[section] = []
            sections[section].append(source)

        # Build comprehensive analysis
        context_parts.append("\nLegal Analysis:")
        context_parts.append(f"Based on {len(sources)} relevant legal sources:")

        # Add section-specific analysis
        for section, section_sources in sections.items():
            if section != "N/A":
                context_parts.append(f"\n{section}:")
                for source in sorted(
                    section_sources,
                    key=lambda x: x.get("rerank_score", x["score"]),
                    reverse=True
                )[:2]:
                    context_parts.append(f"• {source['content']}")

        # Add practical implications
        context_parts.append("\nPractical Implications:")
        main_source = sorted_sources[0]
        context_parts.append(
            f"According to {main_source['article_type']} {main_source['article_number']}, "
            f"{main_source['content']}"
        )

        # Add references
        context_parts.append("\nKey References:")
        for source in sorted_sources[:3]:
            context_parts.append(
                f"• {source['article_type']} {source['article_number']} "
                f"({source.get('reference_id', 'N/A')})"
            )

        return "\n".join(context_parts)

    def execute(
        self, 
        query: str, 
        max_sources: int = 10, 
        min_relevance: float = 0.1,
        response_mode: str = ResponseMode.SOURCES_ONLY
    ) -> str:
        """Execute enhanced search with query expansion and hybrid retrieval."""
        try:
            if not self.index:
                raise ValueError("No index available. Please add documents first.")

            logger.info(f"Processing query: {query}")
            
            # Expand query
            expanded_queries = self.query_processor.expand_query(query)
            logger.info(f"Generated {len(expanded_queries)} query variations")
            
            # Get results for each query variation
            all_results = []
            for expanded_query in expanded_queries:
                query_engine = self.index.as_query_engine(
                    similarity_top_k=max_sources,
                    node_postprocessors=[
                        SimilarityPostprocessor(similarity_cutoff=min_relevance)
                    ],
                    response_mode="no_text",
                    streaming=False,
                    verbose=True
                )
                
                response = query_engine.query(expanded_query)
                
                # Process results
                for node in response.source_nodes:
                    if node.score < min_relevance:
                        continue
                    
                    metadata = node.node.metadata.copy()
                    result = {
                        'article_number': metadata.get('article_number', 'N/A'),
                        'article_type': metadata.get('article_type', 'article'),
                        'content': node.node.text.strip(),
                        'section': metadata.get('section', 'N/A'),
                        'reference_id': metadata.get('reference_id', 'N/A'),
                        'modification_date': metadata.get('modification_date', 'N/A'),
                        'score': round(float(node.score), 4),
                        'query': expanded_query,
                        'metadata': {
                            'source_type': 'legal_document',
                            'file_name': metadata.get('file_name', 'Unknown'),
                            'timestamp': str(datetime.now().isoformat())
                        }
                    }
                    all_results.append(result)
            
            # Apply hybrid search
            results = self.hybrid_retriever.hybrid_search(
                query,
                all_results,
                top_k=max_sources
            )
            
            # Rerank results
            results = self.hybrid_retriever.rerank_results(
                query,
                results,
                top_k=max(5, max_sources)
            )
            
            logger.info(f"Found {len(results)} relevant articles after reranking")
            logger.info("================================ all_results =============================")
            logger.info(all_results)
            logger.info("================================ results =============================")
            logger.info(results)

            # Prepare response based on mode
            response_mode = ResponseMode(response_mode)
            if response_mode == ResponseMode.SOURCES_ONLY:
                return json.dumps(results, indent=4, ensure_ascii=False)
            elif response_mode == ResponseMode.CONTEXTUAL_ANSWER:
                answer = self._generate_contextual_answer(query, results)
                return json.dumps({"answer": answer}, indent=4, ensure_ascii=False)
            else:  # ANSWER_WITH_SOURCES
                answer = self._generate_contextual_answer(query, results)
                return json.dumps({
                    "answer": answer,
                    "sources": results
                }, indent=4, ensure_ascii=False)

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

if __name__ == "__main__":
    # Example usage
    try:
        # Clean up existing index if needed
        if os.path.exists("./storage/legal_embedding_rag"):
            shutil.rmtree("./storage/legal_embedding_rag")
        
        # Initialize tool with enhanced settings
        tool = LegalEmbeddingRAG(
            persist_dir="./storage/legal_embedding_rag",
            document_paths=[
                "./docs/test/code_civile.md",
                "./docs/test/code_procedure.md"
            ],
            chunk_size=512,
            chunk_overlap=128,
            force_reindex=False
        )
        
        # Test query
        test_query = "Mon voisin à des ouverture (fenêtres) donnant sur ma propriété. j'aimerai invoquer la lois pour qu'il les ferme, quelles sont les lois qui me defends ?"
        
        print("\nTesting enhanced RAG with different response modes:")
        for mode in ResponseMode:
            print(f"\nResponse Mode: {mode.value}")
            try:
                result = tool.execute(
                    query=test_query,
                    max_sources=5,
                    min_relevance=0.5,
                    response_mode=mode.value
                )
                print(result)
            except Exception as e:
                print(f"Error: {str(e)}")

    except Exception as e:
        logger.error(f"Failed to initialize or run tool: {e}")
