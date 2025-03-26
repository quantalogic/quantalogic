"""Enhanced BM25-powered RAG Tool optimized for legal document retrieval with article-based output.

This tool provides RAG capabilities using:
- BM25Okapi for efficient keyword-based search
- Article-based chunking strategy for legal documents
- Enhanced metadata extraction for articles
- Structured article-based output format
"""

import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import json
from datetime import datetime
import re

import tiktoken
from rank_bm25 import BM25Okapi
from llama_index.core import SimpleDirectoryReader, Document
from llama_index.readers.file.docs import PDFReader
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
class LegalArticle:
    """Structured representation of a legal article."""
    article_number: str
    content: str
    section: Optional[str] = None
    reference_id: Optional[str] = None
    modification_date: Optional[str] = None
    score: Optional[float] = None
    metadata: Dict[str, Any] = None

class EnhancedBM25LegalRAG(Tool):
    """Enhanced BM25-powered RAG tool for legal document retrieval."""

    name: str = "enhanced_bm25_legal_rag"
    description: str = (
        "Enhanced RAG tool optimized for legal document retrieval using BM25 search "
        "with article-based chunking and output."
    )
    arguments: List[ToolArgument] = [
        ToolArgument(
            name="query",
            arg_type="string",
            description="Legal query to search for relevant articles",
            required=True,
            example="What are the requirements for filing a civil lawsuit?",
        ),
        ToolArgument(
            name="max_sources",
            arg_type="int",
            description="Maximum number of legal articles to return",
            required=False,
            default="20",
        ),
        ToolArgument(
            name="min_relevance",
            arg_type="float",
            description="Minimum relevance score (0-1) for returned articles",
            required=False,
            default="0.1",
        ),
    ]

    def __init__(
        self,
        name: str = "enhanced_bm25_legal_rag",
        document_paths: Optional[List[str]] = None,
    ):
        """Initialize the enhanced BM25-powered legal RAG tool."""
        super().__init__()
        self.name = name
        
        # Initialize document store and BM25 index
        self.bm25_index = None
        self.document_store = []
        
        if document_paths:
            self._build_index(document_paths)

    def _extract_article_metadata(self, text: str) -> Dict[str, Any]:
        """Extract metadata from article text."""
        metadata = {}
        
        # Extract article number with improved pattern
        article_pattern = r'Art\.?\s*(\d+(?:\-\d+)?(?:\s*bis\d*)?(?:\s*\w+)?)'
        article_match = re.search(article_pattern, text, re.IGNORECASE)
        if article_match:
            metadata['article_number'] = article_match.group(1).strip()
            
        # Extract section information
        section_patterns = [
            r'Section\s+(\d+(?:[-\s]*\d+)?)',
            r'Chapitre\s+(\d+(?:[-\s]*\d+)?)',
            r'Titre\s+(\d+(?:[-\s]*\d+)?)'
        ]
        
        for pattern in section_patterns:
            section_match = re.search(pattern, text, re.IGNORECASE)
            if section_match:
                metadata['section'] = section_match.group(1)
                break
                
        # Extract modification date
        date_pattern = r'(?:Modifié par|du)\s+(?:la\s+)?(?:loi\s+)?n[°o]?\s*\d+[-./]\d+\s+du\s+(\d{1,2}\s+\w+\s+\d{4})'
        date_match = re.search(date_pattern, text, re.IGNORECASE)
        if date_match:
            metadata['modification_date'] = date_match.group(1)
            
        # Extract legal references
        ref_patterns = [
            r'(?:loi|décret|arrêté)\s+n[°o]?\s*(\d+[-./]\d+)',  # French
            r'(?:قانون|مرسوم|قرار)\s+(?:رقم\s+)?(\d+[-./]\d+)',  # Arabic
            r'(?:law|decree)\s+(?:no\.\s+)?(\d+[-./]\d+)'        # English
        ]
        
        for pattern in ref_patterns:
            ref_match = re.search(pattern, text, re.IGNORECASE)
            if ref_match:
                metadata['reference_id'] = ref_match.group(1)
                break
                
        return metadata

    def _split_into_articles(self, text: str) -> List[Dict[str, Any]]:
        """Split text into articles and extract metadata."""
        # Split text into articles
        articles = re.split(r'(?=Art\.\s*\d+)', text)
        processed_articles = []
        
        for article_text in articles:
            if not article_text.strip():
                continue
                
            # Extract metadata
            metadata = self._extract_article_metadata(article_text)
            
            if 'article_number' in metadata:
                processed_articles.append({
                    'text': article_text.strip(),
                    'metadata': metadata
                })
                
        return processed_articles

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
                for doc in docs:
                    # Split into articles
                    articles = self._split_into_articles(doc.text)
                    
                    for article in articles:
                        article['metadata']['file_name'] = os.path.basename(path)
                        article['metadata']['file_path'] = path
                        
                        processed_doc = Document(
                            text=article['text'],
                            metadata=article['metadata']
                        )
                        all_documents.append(processed_doc)
                
            except Exception as e:
                logger.error(f"Error loading document {path}: {str(e)}")
                continue
                
        return all_documents

    def _build_index(self, document_paths: List[str]):
        """Build BM25 index from documents."""
        documents = self._load_documents(document_paths)
        
        # Store documents and their text for BM25
        tokenized_corpus = []
        self.document_store = []
        
        # Process each document (article)
        for doc in documents:
            # Process text for BM25
            text = doc.text.lower()
            tokens = text.split()
            
            # Store document info
            self.document_store.append({
                'text': doc.text,
                'metadata': doc.metadata,
                'tokens': tokens
            })
            
            tokenized_corpus.append(tokens)
        
        # Create BM25 index
        self.bm25_index = BM25Okapi(tokenized_corpus)
        logger.info(f"Built BM25 index with {len(tokenized_corpus)} articles")

    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """Normalize scores to range [0, 1]."""
        if not scores:
            return scores
        scores_array = np.array(scores)
        min_score = np.min(scores_array)
        max_score = np.max(scores_array)
        if max_score == min_score:
            return [1.0] * len(scores)
        return ((scores_array - min_score) / (max_score - min_score)).tolist()

    def execute(self, query: str, max_sources: int = 10, min_relevance: float = 0.1) -> str:
        """Execute BM25 search for legal articles."""
        try:
            if not self.bm25_index:
                raise ValueError("Index not initialized. Please add documents first.")

            logger.info(f"Searching for legal articles with query: {query}")
            
            # Get BM25 results
            tokenized_query = query.lower().split()
            bm25_scores = self.bm25_index.get_scores(tokenized_query)
            
            # Create tuples of (score, index) and sort by score
            scored_indices = [(score, idx) for idx, score in enumerate(bm25_scores)]
            scored_indices.sort(reverse=True)
            
            # Get top results and normalize their scores
            top_k = min(max_sources * 2, len(scored_indices))
            top_scores = [score for score, _ in scored_indices[:top_k]]
            normalized_scores = self._normalize_scores(top_scores)
            
            # Process results
            results = []
            for norm_score, (orig_score, doc_idx) in zip(normalized_scores, scored_indices[:top_k]):
                if norm_score < min_relevance:
                    continue
                    
                doc = self.document_store[doc_idx]
                metadata = doc['metadata'].copy()
                
                # Create article entry
                article = {
                    'article_number': metadata.get('article_number', 'N/A'),
                    'content': doc['text'].strip(),
                    'section': metadata.get('section', 'N/A'),
                    'reference_id': metadata.get('reference_id', 'N/A'),
                    'modification_date': metadata.get('modification_date', 'N/A'),
                    'score': round(float(norm_score), 4),
                    'metadata': {
                        'source_type': 'legal_document',
                        'file_name': metadata.get('file_name', 'Unknown'),
                        'query': query,
                        'bm25_score': float(orig_score),
                        'timestamp': str(datetime.now().isoformat())
                    }
                }
                results.append(article)
            
            # Sort by article number if possible, then by score
            def sort_key(x):
                try:
                    return (int(re.sub(r'\D', '', x['article_number'])), -x['score'])
                except:
                    return (float('inf'), -x['score'])
                    
            results.sort(key=sort_key)
            results = results[:max_sources]
            
            logger.info(f"Found {len(results)} relevant articles")
            return json.dumps(results, indent=4, ensure_ascii=False)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Legal search failed: {error_msg}")
            error_response = {
                'error': error_msg,
                'query': query,
                'timestamp': str(datetime.now().isoformat()),
                'articles': []
            }
            return json.dumps(error_response, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    # Example usage
    tool = EnhancedBM25LegalRAG(
        document_paths=[
            "./docs/test/code_civile.md",
            "./docs/test/code_procedure.md"
        ]
    )
    
    # Test queries
    test_queries = [
            "Quels sont les recours légaux en Algérie pour contraindre un voisin à fermer des ouvertures (fenêtres) donnant sur ma propriété ?",
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        try:
            result = tool.execute(query, max_sources=10, min_relevance=0.1)
            print(result)
        except Exception as e:
            print(f"Error: {str(e)}")
