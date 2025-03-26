
"""BM25-powered RAG Tool optimized for legal document retrieval.

This tool provides RAG capabilities using:
- BM25Okapi for efficient keyword-based search
- Optimized chunking strategy for legal documents
- Document preprocessing and metadata extraction
- Enhanced response formatting with legal context
"""

import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import json
from datetime import datetime
import textwrap

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
class LegalSource:
    """Structured representation of a legal source."""
    content: str
    file_name: str
    section: str
    article_number: Optional[str] = None
    reference_id: Optional[str] = None
    score: Optional[float] = None
    metadata: Dict[str, Any] = None

class BM25LegalRAG(Tool):
    """BM25-powered RAG tool for legal document retrieval."""

    name: str = "bm25_legal_rag"
    description: str = (
        "RAG tool optimized for legal document retrieval using BM25 search "
        "with enhanced chunking capabilities."
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
        name: str = "bm25_legal_rag",
        document_paths: Optional[List[str]] = None,
        chunk_size: int = 512,
        chunk_overlap: int = 128,
    ):
        """Initialize the BM25-powered legal RAG tool.
        
        Args:
            name: Tool name
            document_paths: List of paths to legal documents
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
        """
        super().__init__()
        self.name = name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Initialize document store and BM25 index
        self.bm25_index = None
        self.document_store = []  # Reset document store
        
        if document_paths:
            self._build_index(document_paths)

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

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks with overlap."""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk = ' '.join(words[i:i + self.chunk_size])
            chunks.append(chunk)
            
        return chunks

    def _build_index(self, document_paths: List[str]):
        """Build BM25 index from documents."""
        documents = self._load_documents(document_paths)
        
        # Store documents and their text for BM25
        tokenized_corpus = []
        self.document_store = []  # Reset document store
        
        # Process each document
        for doc in documents:
            chunks = self._chunk_text(doc.text)
            
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
        logger.info(f"Built BM25 index with {len(tokenized_corpus)} chunks")

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
        """Execute BM25 search for legal documents."""
        try:
            if not self.bm25_index:
                raise ValueError("Index not initialized. Please add documents first.")

            logger.info(f"Executing BM25 legal search for query: {query}")
            
            # Get BM25 results
            tokenized_query = query.lower().split()
            bm25_scores = self.bm25_index.get_scores(tokenized_query)
            
            # Create tuples of (score, index) and sort by score
            scored_indices = [(score, idx) for idx, score in enumerate(bm25_scores)]
            scored_indices.sort(reverse=True)  # Sort by score in descending order
            
            # Get top results and normalize their scores
            top_k = min(max_sources * 2, len(scored_indices))  # Get more results than needed for filtering
            top_scores = [score for score, _ in scored_indices[:top_k]]
            normalized_scores = self._normalize_scores(top_scores)
            
            # Combine results with scores
            results = []
            for norm_score, (orig_score, doc_idx) in zip(normalized_scores, scored_indices[:top_k]):
                if norm_score < min_relevance:
                    continue
                    
                doc = self.document_store[doc_idx]
                text = doc['text'].strip()
                metadata = doc['metadata'].copy()
                metadata.update(self._extract_legal_metadata(text))
                
                legal_source = LegalSource(
                    content=text,
                    file_name=metadata.get('file_name', 'Unknown'),
                    section=metadata.get('section', 'N/A'),
                    article_number=metadata.get('article_number'),
                    reference_id=metadata.get('reference_id'),
                    score=float(norm_score),
                    metadata={
                        'bm25_score': float(orig_score),
                        'normalized_score': float(norm_score),
                        'query': query,
                        'timestamp': str(datetime.now().isoformat())
                    }
                )
                results.append(legal_source)
            
            # Sort by score and limit results
            results.sort(key=lambda x: x.score or 0, reverse=True)
            results = results[:max_sources]
            
            # Format results for output
            output_results = []
            for result in results:
                output_results.append({
                    'content': result.content,
                    'file_name': result.file_name,
                    'section': result.section,
                    'article_number': result.article_number,
                    'reference_id': result.reference_id,
                    'score': round(result.score, 4),
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
            
            # Score
            if source.score:
                output.append(f"**Relevance**: {round(source.score * 100, 2)}%\n")
            
            # Content
            output.append(f"{source.content}\n")
            output.append("---\n")
        
        return "\n".join(output)

if __name__ == "__main__":
    # Example usage
    tool = BM25LegalRAG(
        document_paths=[
            "./docs/test/code_civile.md",
            "./docs/test/code_procedure.md"
        ],
        chunk_size=512,
        chunk_overlap=128
    )
    
    # Test queries
    test_queries = [
        #"Quels sont les recours légaux en Algérie pour contraindre un voisin à fermer des ouvertures (fenêtres) donnant sur ma propriété ?",
        "Mon voisin a créé des ouvertures (fenêtres) donnant directement sur ma propriété, ce qui porte atteinte à ma vie privée. Je souhaite faire valoir mes droits et le contraindre à fermer ces ouvertures.",

    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        try:
            # Use a very low relevance threshold to see all potential matches
            result = tool.execute(query, max_sources=5, min_relevance=0.1)
            print(result)
        except Exception as e:
            print(f"Error: {str(e)}")
