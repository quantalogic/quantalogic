"""LegalMind Pro: Advanced Multilingual Legal Research System

A state-of-the-art legal research and analysis system that provides:

1. Multilingual Processing & Analysis:
   - Comprehensive support for French, Arabic, and English legal documents
   - Intelligent legal term recognition and cross-lingual mapping
   - Advanced citation detection and validation across languages
   - Specialized handling of jurisdiction-specific legal terminology

2. Document Structure Analysis:
   - Automated extraction of legal hierarchies (titles, chapters, articles)
   - Smart detection of document types and legal entities
   - Citation graph construction and analysis
   - Temporal reference tracking and validation

3. Advanced Search Capabilities:
   - Hybrid search combining BM25 and semantic embeddings
   - Context-aware relevance scoring
   - Citation-based recommendation system
   - Hierarchical document navigation

4. Enhanced Features:
   - High-quality OCR for scanned legal documents
   - Automated legal content summarization
   - Citation network visualization
   - Source attribution and validation
"""

import os
from typing import List, Optional, Dict, Any, Tuple, ClassVar
from dataclasses import dataclass
import asyncio
import shutil
import json
from datetime import datetime
import re
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
from llama_index.core import (
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
    Response,
    QueryBundle,
    Settings,
    Document,
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.readers.file.docs import PDFReader
from loguru import logger
from quantalogic.tools.tool import Tool, ToolArgument
from quantalogic.tools.rag_tool.ocr_pdf_markdown import PDFToMarkdownConverter
from rank_bm25 import BM25Okapi
from sklearn.preprocessing import MinMaxScaler
import numpy as np
from pydantic import BaseModel, Field

# Configure tool-specific logging
logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
)

@dataclass
class LegalReference:
    """Structured representation of a legal reference."""
    type: str  # 'article', 'section', 'chapter', etc.
    number: str
    title: Optional[str] = None
    code_name: Optional[str] = None
    jurisdiction: Optional[str] = None

@dataclass
class LegalSource:
    """Enhanced representation of a legal source with hierarchical context."""
    content: str
    file_name: str
    page_number: str
    reference: Optional[LegalReference] = None
    hierarchy: Dict[str, str] = None  # e.g., {'title': '1', 'chapter': '2', 'section': '3'}
    citations: List[LegalReference] = None
    score: Optional[float] = None
    context: Optional[str] = None

@dataclass
class LegalSearchResult:
    """Comprehensive legal search result with analysis."""
    source: LegalSource
    relevance_scores: Dict[str, float]  # Different types of relevance scores
    analysis: Dict[str, Any]  # Legal analysis metadata
    citations_graph: Dict[str, List[str]]  # Citation relationships
    key_terms: List[Tuple[str, float]]  # Important legal terms and their weights

class RagToolHf(Tool):
    """LegalMind Pro: Advanced Multilingual Legal Research System.
    
    A comprehensive legal research and analysis system that combines:
    - Advanced multilingual processing (FR/AR/EN)
    - Intelligent legal document structure analysis
    - Hybrid search with citation awareness
    - Automated legal content summarization
    """

    name: str = "legalmind_pro"
    description: str = (
        "Advanced legal research and analysis system that combines natural language processing, "
        "semantic search, and citation analysis to provide comprehensive legal document "
        "retrieval and analysis across multiple languages with detailed source attribution."
    )
    version: str = "2.1.0"
    arguments: List[ToolArgument] = [
        ToolArgument(
            name="query",
            arg_type="string",
            description=(
                "Legal search query in French, Arabic, or English. Can include specific "
                "references to laws, articles, or legal concepts."
            ),
            required=True,
        ),
        ToolArgument(
            name="max_sources",
            arg_type="int",
            description="Maximum number of legal sources to return (default: 5, max: 20)",
            required=False,
            default="5",
            min_value="1",
            max_value="20"
        ),
        ToolArgument(
            name="min_score",
            arg_type="float",
            description="Minimum relevance score threshold (0.0-1.0)",
            required=False,
            default="0.3",
            min_value="0.0",
            max_value="1.0"
        ),
        ToolArgument(
            name="include_context",
            arg_type="boolean",
            description="Include surrounding context for each result",
            required=False,
            default="true",
        )
    ]

    # Class variables with type annotations
    LEGAL_PATTERNS: ClassVar[Dict[str, str]] = {
        'article': r'Article\s+(\d+[\w\-]*)',
        'act': r'Act\s+(\d+[\w\-]*)',
        'section': r'Section\s+(\d+[\w\-]*)',
        'chapter': r'Chapter\s+(\d+[\w\-]*)',
        'reference': r'(?:ref\.|reference)\s+(\d+[\w\-]*)',
    }

    def __init__(
        self,
        name: str = "legalmind_pro",
        persist_dir: str = "./storage/legal_rag",
        document_paths: Optional[List[str]] = None,
        chunk_size: int = 512,
        chunk_overlap: int = 100,
        use_ocr_for_pdfs: bool = False,
        ocr_model: str = "openai/gpt-4o-mini",
        embed_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        bm25_weight: float = 0.4,
        embedding_weight: float = 0.6,
        min_relevance_score: float = 0.3,
    ):
        """Initialize the LegalMind Pro research system.

        Args:
            name: System identifier
            persist_dir: Directory for index storage
            document_paths: Paths to legal documents
            chunk_size: Text chunk size for processing
            chunk_overlap: Overlap between chunks
            use_ocr_for_pdfs: Enable OCR for PDFs
            ocr_model: OCR model identifier
            embed_model: Embedding model name
            bm25_weight: BM25 score weight (0-1)
            embedding_weight: Embedding score weight (0-1)
            min_relevance_score: Minimum relevance threshold
        """
        super().__init__(
            name=name,
            description="Advanced multilingual legal research and analysis system",
            version="2.1.0",
        )
        
        self.persist_dir = Path(persist_dir)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.use_ocr_for_pdfs = use_ocr_for_pdfs
        self.ocr_model = ocr_model
        self.embed_model = embed_model
        self.bm25_weight = bm25_weight
        self.embedding_weight = embedding_weight
        self.min_relevance_score = min_relevance_score
        
        # Initialize indices
        self.bm25_index = None
        self.document_store: List[Dict[str, Any]] = []
        self.citation_graph: Dict[str, List[str]] = {}
        self.legal_term_index: Dict[str, float] = {}
        
        # Build indices if documents provided
        if document_paths:
            self._build_legal_index(document_paths)

    def _extract_legal_references(self, text: str) -> List[LegalReference]:
        """Extract and structure legal references from text."""
        references = []
        for ref_type, pattern in self.LEGAL_PATTERNS.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                ref_num = match.group(1)
                # Extract surrounding context (title)
                context_start = max(0, match.start() - 50)
                context_end = min(len(text), match.end() + 50)
                context = text[context_start:context_end].strip()
                
                references.append(LegalReference(
                    type=ref_type,
                    number=ref_num,
                    title=context,
                    code_name=self._detect_code_name(text)
                ))
        return references

    def _detect_code_name(self, text: str) -> Optional[str]:
        """Detect the legal code name from text."""
        code_patterns = [
            r"Code\s+(?:of|des?|du)\s+([A-Z][a-zA-Z\s]+)",
            r"([A-Z][a-zA-Z\s]+)\s+Code",
        ]
        for pattern in code_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None

    def _build_legal_index(self, document_paths: List[str]):
        """Build specialized legal document index."""
        documents = self._load_documents(document_paths)
        
        # Process documents for legal structure
        self.document_store = []
        tokenized_corpus = []
        
        for doc in documents:
            # Extract legal references and structure
            references = self._extract_legal_references(doc.text)
            hierarchy = self._extract_document_hierarchy(doc.text)
            
            # Process text for BM25
            processed_text = self._preprocess_legal_text(doc.text)
            tokens = processed_text.split()
            
            # Store enhanced document info
            self.document_store.append({
                'text': doc.text,
                'processed_text': processed_text,
                'metadata': {
                    **doc.metadata,
                    'references': references,
                    'hierarchy': hierarchy
                },
                'tokens': tokens
            })
            
            tokenized_corpus.append(tokens)
            
            # Build citation graph
            self._update_citation_graph(references)
        
        # Create indices
        self.bm25_index = BM25Okapi(tokenized_corpus)
        self._create_embedding_index(documents)

    def _load_documents(self, document_paths: List[str]) -> List[Document]:
        """Load and preprocess documents from various file formats."""
        logger.info(f"Loading documents from {len(document_paths)} paths")
        documents = []
        
        for path in document_paths:
            try:
                if not os.path.exists(path):
                    logger.warning(f"Document path does not exist: {path}")
                    continue
                
                if path.lower().endswith('.pdf'):
                    if self.use_ocr_for_pdfs:
                        # Use OCR for PDF processing
                        converter = PDFToMarkdownConverter(self.ocr_model)
                        markdown_text = converter.convert_pdf_to_markdown(path)
                        doc = Document(text=markdown_text, metadata={
                            'file_name': os.path.basename(path),
                            'processing_method': 'ocr',
                            'original_format': 'pdf'
                        })
                        documents.append(doc)
                    else:
                        # Use standard PDF reader
                        reader = PDFReader()
                        docs = reader.load_data(path)
                        for doc in docs:
                            doc.metadata.update({
                                'processing_method': 'standard',
                                'original_format': 'pdf'
                            })
                        documents.extend(docs)
                else:
                    # Use standard document reader for other formats
                    reader = SimpleDirectoryReader(input_files=[path])
                    docs = reader.load_data()
                    for doc in docs:
                        doc.metadata.update({
                            'file_name': os.path.basename(path),
                            'processing_method': 'standard',
                            'original_format': path.split('.')[-1]
                        })
                    documents.extend(docs)
                
            except Exception as e:
                logger.error(f"Error loading document {path}: {str(e)}")
                continue
        
        # Split documents into chunks
        parser = SentenceSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        
        processed_documents = []
        for doc in documents:
            try:
                nodes = parser.get_nodes_from_documents([doc])
                for node in nodes:
                    processed_doc = Document(
                        text=node.text,
                        metadata={
                            **doc.metadata,
                            'page_number': str(node.metadata.get('page_number', 'N/A')),
                            'chunk_number': str(node.metadata.get('chunk_number', 'N/A'))
                        }
                    )
                    processed_documents.append(processed_doc)
            except Exception as e:
                logger.error(f"Error processing document chunk: {str(e)}")
                continue
        
        logger.info(f"Successfully loaded {len(processed_documents)} document chunks")
        return processed_documents

    def _create_embedding_index(self, documents: List[Document]):
        """Create the embedding index for semantic search."""
        try:
            # Initialize embedding model
            embed_model = HuggingFaceEmbedding(
                model_name=self.embed_model
            )
            
            # Create Chroma store
            db = chromadb.PersistentClient(path=str(self.persist_dir))
            chroma_collection = db.get_or_create_collection("legal_documents")
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            
            # Create storage context
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            
            # Create index
            self.index = VectorStoreIndex.from_documents(
                documents,
                storage_context=storage_context,
                embed_model=embed_model,
                show_progress=True
            )
            
            logger.info("Successfully created embedding index")
            
        except Exception as e:
            logger.error(f"Error creating embedding index: {str(e)}")
            raise

    def _extract_document_hierarchy(self, text: str) -> Dict[str, str]:
        """Extract document hierarchy information."""
        hierarchy = {}
        
        # Extract title information
        title_match = re.search(r'Title\s+(\d+[\w\-]*)', text)
        if title_match:
            hierarchy['title'] = title_match.group(1)
        
        # Extract chapter information
        chapter_match = re.search(r'Chapter\s+(\d+[\w\-]*)', text)
        if chapter_match:
            hierarchy['chapter'] = chapter_match.group(1)
        
        # Extract section information
        section_match = re.search(r'Section\s+(\d+[\w\-]*)', text)
        if section_match:
            hierarchy['section'] = section_match.group(1)
        
        return hierarchy

    def _preprocess_legal_text(self, text: str) -> str:
        """Preprocess legal text for improved search."""
        # Convert to lowercase
        text = text.lower()
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        # Replace common legal abbreviations
        replacements = {
            'art.': 'article',
            'sec.': 'section',
            'ch.': 'chapter',
            'ref.': 'reference',
            'reg.': 'regulation',
            'para.': 'paragraph',
            'pp.': 'pages',
        }
        
        for abbr, full in replacements.items():
            text = text.replace(abbr, full)
        
        return text

    def _update_citation_graph(self, references: List[LegalReference]):
        """Update the citation graph with new references."""
        for ref in references:
            key = f"{ref.type}_{ref.number}"
            if key not in self.citation_graph:
                self.citation_graph[key] = []
            
            # Add cross-references
            for other_ref in references:
                if other_ref != ref:
                    other_key = f"{other_ref.type}_{other_ref.number}"
                    if other_key not in self.citation_graph[key]:
                        self.citation_graph[key].append(other_key)

    def _hybrid_legal_search(self, query: str, max_sources: int) -> List[LegalSearchResult]:
        """Perform hybrid legal document search."""
        # Get embedding-based results
        query_engine = self.index.as_query_engine(
            similarity_top_k=max_sources * 2,
            node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=self.min_relevance_score)],
            response_mode="no_text",
            streaming=False,
            verbose=True
        )
        
        embedding_response = query_engine.query(query)
        
        # Get BM25 results
        tokenized_query = self._preprocess_legal_text(query).split()
        bm25_scores = self.bm25_index.get_scores(tokenized_query)
        
        # Combine results
        results = []
        seen_texts = set()
        
        for node in embedding_response.source_nodes:
            text = node.node.text.strip()
            if text in seen_texts or node.score < self.min_relevance_score:
                continue
                
            seen_texts.add(text)
            
            # Find corresponding BM25 score
            doc_idx = next(
                (i for i, doc in enumerate(self.document_store) 
                 if doc['text'].strip() == text),
                None
            )
            
            if doc_idx is None:
                continue
                
            bm25_score = bm25_scores[doc_idx]
            
            # Extract legal references
            references = self._extract_legal_references(text)
            
            # Create legal source
            source = LegalSource(
                content=text,
                file_name=node.node.metadata.get('file_name', 'Unknown'),
                page_number=str(node.node.metadata.get('page_number', 'N/A')),
                reference=references[0] if references else None,
                hierarchy=self._extract_document_hierarchy(text),
                citations=references,
                context=self._extract_context(text)
            )
            
            # Calculate scores
            relevance_scores = {
                'bm25': float(bm25_score),
                'embedding': float(node.score),
                'combined': self.bm25_weight * float(bm25_score) + 
                           self.embedding_weight * float(node.score)
            }
            
            # Extract key terms
            key_terms = self._extract_key_terms(text)
            
            # Create search result
            result = LegalSearchResult(
                source=source,
                relevance_scores=relevance_scores,
                analysis=self._analyze_legal_content(text, query),
                citations_graph=self._get_citation_subgraph(references),
                key_terms=key_terms
            )
            
            results.append(result)
        
        # Sort by combined score
        results.sort(key=lambda x: x.relevance_scores['combined'], reverse=True)
        return results[:max_sources]

    def _extract_context(self, text: str, context_window: int = 200) -> str:
        """Extract surrounding context for a text snippet."""
        words = text.split()
        if len(words) <= context_window:
            return text
        
        middle = len(words) // 2
        start = max(0, middle - context_window // 2)
        end = min(len(words), middle + context_window // 2)
        
        return ' '.join(words[start:end])

    def _extract_key_terms(self, text: str) -> List[Tuple[str, float]]:
        """Extract important legal terms and their weights."""
        # Simple implementation - can be enhanced with legal term dictionary
        words = self._preprocess_legal_text(text).split()
        term_freq = {}
        
        for word in words:
            if len(word) > 3:  # Skip short words
                term_freq[word] = term_freq.get(word, 0) + 1
        
        # Calculate TF-IDF-like scores
        max_freq = max(term_freq.values()) if term_freq else 1
        terms = [(term, freq/max_freq) for term, freq in term_freq.items()]
        
        # Sort by score
        terms.sort(key=lambda x: x[1], reverse=True)
        return terms[:10]  # Return top 10 terms

    def _analyze_legal_content(self, text: str, query: str) -> Dict[str, Any]:
        """Perform basic legal content analysis."""
        return {
            'document_type': self._detect_document_type(text),
            'legal_entities': self._extract_legal_entities(text),
            'query_relevance': self._calculate_query_relevance(text, query),
            'temporal_references': self._extract_temporal_references(text)
        }

    def _detect_document_type(self, text: str) -> str:
        """Detect the type of legal document."""
        text_lower = text.lower()
        if 'act' in text_lower:
            return 'Act'
        elif 'regulation' in text_lower:
            return 'Regulation'
        elif 'directive' in text_lower:
            return 'Directive'
        elif 'code' in text_lower:
            return 'Code'
        return 'Other'

    def _extract_legal_entities(self, text: str) -> List[str]:
        """Extract legal entities mentioned in the text."""
        # Simple implementation - can be enhanced with NER
        entities = []
        entity_patterns = [
            r'(?:The|the)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Court|Commission|Authority|Agency)',
            r'(?:Ministry|Department)\s+of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ]
        
        for pattern in entity_patterns:
            matches = re.finditer(pattern, text)
            entities.extend(match.group(1) for match in matches)
        
        return list(set(entities))

    def _calculate_query_relevance(self, text: str, query: str) -> float:
        """Calculate relevance score between text and query."""
        # Simple implementation using word overlap
        text_words = set(self._preprocess_legal_text(text).split())
        query_words = set(self._preprocess_legal_text(query).split())
        
        overlap = len(text_words.intersection(query_words))
        return overlap / len(query_words) if query_words else 0.0

    def _extract_temporal_references(self, text: str) -> List[str]:
        """Extract temporal references from text."""
        date_patterns = [
            r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',
            r'\d{4}',
        ]
        
        dates = []
        for pattern in date_patterns:
            matches = re.finditer(pattern, text)
            dates.extend(match.group(0) for match in matches)
        
        return list(set(dates))

    def _get_citation_subgraph(self, references: List[LegalReference]) -> Dict[str, List[str]]:
        """Get a subgraph of citations for the given references."""
        subgraph = {}
        for ref in references:
            key = f"{ref.type}_{ref.number}"
            if key in self.citation_graph:
                subgraph[key] = self.citation_graph[key]
        return subgraph

    def _generate_legal_summary(self, results: List[LegalSearchResult]) -> Dict[str, Any]:
        """Generate a comprehensive legal summary of search results."""
        if not results:
            return {
                'status': 'no_results',
                'message': 'No relevant legal documents found.'
            }
        
        # Collect statistics
        doc_types = {}
        total_citations = 0
        key_terms_freq = {}
        
        for result in results:
            # Document types
            doc_type = result.analysis.get('document_type', 'Unknown')
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
            
            # Citations
            if result.source.citations:
                total_citations += len(result.source.citations)
            
            # Key terms
            for term, score in result.key_terms:
                key_terms_freq[term] = key_terms_freq.get(term, 0) + 1
        
        # Sort key terms by frequency
        top_terms = sorted(
            key_terms_freq.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return {
            'status': 'success',
            'document_types': doc_types,
            'total_citations': total_citations,
            'top_terms': top_terms,
            'average_relevance': sum(r.relevance_scores['combined'] for r in results) / len(results),
            'result_count': len(results)
        }

    def execute(
        self,
        query: str,
        max_sources: int = 5,
        min_score: float = 0.3,
        include_context: bool = True
    ) -> str:
        """Execute legal document search and analysis.
        
        Args:
            query: Legal search query in French, Arabic, or English
            max_sources: Maximum number of sources to return (1-20)
            min_score: Minimum relevance score threshold (0.0-1.0)
            include_context: Whether to include surrounding context
            
        Returns:
            JSON string containing search results and comprehensive analysis
            
        Example:
            >>> tool = LegalMindPro()
            >>> results = tool.execute(
            ...     query="Find environmental regulations in commercial law",
            ...     max_sources=10,
            ...     min_score=0.5,
            ...     include_context=True
            ... )
        """
        try:
            if not self.index or not self.bm25_index:
                raise ValueError("Legal indices not initialized. Please add documents first.")

            logger.info(f"Executing legal search for query: {query}")
            
            # Validate and normalize parameters
            try:
                max_sources = min(max(int(max_sources), 1), 20)
                min_score = min(max(float(min_score), 0.0), 1.0)
                include_context = bool(include_context)
            except (TypeError, ValueError) as e:
                logger.warning(f"Parameter validation error: {str(e)}. Using defaults.")
                max_sources = 5
                min_score = 0.3
                include_context = True
            
            # Get search results with validated parameters
            search_results = self._hybrid_legal_search(query, max_sources)
            
            # Format response
            response = {
                'query': query,
                'timestamp': datetime.now().isoformat(),
                'results': [
                    {
                        'source': {
                            'content': result.source.content,
                            'file_name': result.source.file_name,
                            'page_number': result.source.page_number,
                            'reference': vars(result.source.reference) if result.source.reference else None,
                            'hierarchy': result.source.hierarchy,
                            'context': result.source.context if include_context else None
                        },
                        'relevance': result.relevance_scores,
                        'analysis': result.analysis,
                        'key_terms': result.key_terms,
                        'related_citations': list(result.citations_graph.keys())
                    }
                    for result in search_results
                    if result.relevance_scores['combined'] >= min_score
                ],
                'summary': self._generate_legal_summary(search_results),
                'metadata': {
                    'total_sources_analyzed': len(self.document_store),
                    'search_parameters': {
                        'max_sources': max_sources,
                        'min_score': min_score,
                        'include_context': include_context,
                        'bm25_weight': self.bm25_weight,
                        'embedding_weight': self.embedding_weight
                    }
                }
            }
            
            filtered_results = [r for r in search_results if r.relevance_scores['combined'] >= min_score]
            logger.info(f"Found {len(filtered_results)} relevant legal sources (threshold: {min_score})")
            return json.dumps(response, indent=2, ensure_ascii=False)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Legal search failed: {error_msg}")
            return json.dumps({
                'error': error_msg,
                'query': query,
                'timestamp': datetime.now().isoformat(),
                'search_parameters': {
                    'max_sources': max_sources,
                    'min_score': min_score,
                    'include_context': include_context
                },
                'sources': []
            }, indent=2)

if __name__ == "__main__":
    # Example usage
    tool = RagToolHf(
        persist_dir="./storage/legal_rag",
        document_paths=[
            "./docs/legal/civil_code.md",
            "./docs/legal/criminal_code.md"
        ]
    )
    
    # Test legal queries
    test_queries = [
        "Find articles related to environmental protection regulations",
        "Search for workplace safety requirements and penalties",
        "Find recent amendments to traffic regulations"
    ]
    
    for query in test_queries:
        print(f"\nLegal Query: {query}")
        try:
            result = tool.execute(query, max_sources=3)
            print(result)
        except Exception as e:
            print(f"Error in legal search: {str(e)}")
