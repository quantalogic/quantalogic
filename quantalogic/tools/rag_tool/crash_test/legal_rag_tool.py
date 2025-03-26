"""Tool for performing Contextual Legal RAG operations."""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

from loguru import logger
from pydantic import BaseModel, Field
from quantalogic.tools.tool import Tool, ToolArgument

# Import necessary libraries for embeddings and search
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
import numpy as np
from sklearn.preprocessing import normalize
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize

# Download required NLTK data for French
try:
    nltk.data.find('tokenizers/punkt/french.pickle')
except LookupError:
    nltk.download('punkt')

class LegalDocument(BaseModel):
    """Model for legal document metadata and content."""
    
    content: str = Field(..., description="The document content")
    doc_type: str = Field(..., description="Type of legal document")
    jurisdiction: str = Field(..., description="Jurisdiction of the document")
    court_level: Optional[str] = Field(None, description="Court level if applicable")
    date: Optional[str] = Field(None, description="Document date")
    citation: Optional[str] = Field(None, description="Legal citation")
    title: str = Field(..., description="Document title")

class LegalSegment(BaseModel):
    """Model for segmented legal document with context."""
    
    content: str = Field(..., description="The segment content")
    context: str = Field(..., description="Generated legal context")
    doc_id: str = Field(..., description="Source document ID")
    segment_id: int = Field(..., description="Segment index in document")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

class LegalRAGTool:
    """Enhanced Legal RAG Tool with configurable parameters."""

    def __init__(
        self,
        persist_dir: str = "./storage/legal_rag",
        document_paths: List[str] = None,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        use_ocr_for_pdfs: bool = False,
        bm25_weight: float = 0.3,
        embedding_weight: float = 0.7,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    ):
        """Initialize the Legal RAG tool with configurable parameters.
        
        Args:
            persist_dir: Directory to persist vectors and indexes
            document_paths: List of paths to legal documents
            chunk_size: Size of text chunks for processing
            chunk_overlap: Overlap between chunks
            use_ocr_for_pdfs: Whether to use OCR for PDF documents
            bm25_weight: Weight for BM25 scores in hybrid search
            embedding_weight: Weight for embedding scores in hybrid search
            embedding_model: Name of the sentence transformer model to use
        """
        self.persist_dir = Path(persist_dir)
        self.document_paths = document_paths or []
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.use_ocr_for_pdfs = use_ocr_for_pdfs
        self.bm25_weight = bm25_weight
        self.embedding_weight = embedding_weight
        
        # Create persistence directory
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize models
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # Initialize storage
        self.segments: List[LegalSegment] = []
        self.embeddings = None
        self.bm25 = None
        
        # Process documents if provided
        if self.document_paths:
            self._process_documents()
            
        logger.info("Legal RAG Tool initialized successfully")

    def _segment_document(self, doc: LegalDocument) -> List[str]:
        """Segment a legal document into logical chunks with overlap."""
        segments = []
        # Use French tokenizer
        sentences = sent_tokenize(doc.content, language='french')
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            # If adding this sentence exceeds chunk size, save current chunk
            if current_size + sentence_size > self.chunk_size and current_chunk:
                segments.append(' '.join(current_chunk))
                
                # Keep overlap sentences for next chunk
                overlap_tokens = current_chunk[-self.chunk_overlap:]
                current_chunk = overlap_tokens + [sentence]
                current_size = sum(len(s) for s in current_chunk)
            else:
                current_chunk.append(sentence)
                current_size += sentence_size
        
        # Add final chunk if it exists
        if current_chunk:
            segments.append(' '.join(current_chunk))
            
        return segments

    def _generate_legal_context(self, segment: str, doc: LegalDocument) -> str:
        """Generate legal context for a document segment."""
        context_parts = []
        
        # Add document metadata
        context_parts.append(f"Type de Document: {doc.doc_type}")
        context_parts.append(f"Juridiction: {doc.jurisdiction}")
        
        if doc.court_level:
            context_parts.append(f"Niveau de Cour: {doc.court_level}")
        if doc.date:
            context_parts.append(f"Date: {doc.date}")
        if doc.citation:
            context_parts.append(f"Citation: {doc.citation}")
            
        # Extract key legal concepts (in French)
        words = word_tokenize(segment.lower(), language='french')
        legal_indicators = ['tribunal', 'loi', 'code', 'règlement', 'jugement', 
                          'jurisprudence', 'arrêt', 'demandeur', 'défendeur', 'justice',
                          'procédure', 'civil', 'pénal', 'droit', 'article']
        legal_concepts = [word for word in words if word in legal_indicators]
        if legal_concepts:
            context_parts.append(f"Concepts Juridiques Clés: {', '.join(set(legal_concepts))}")
            
        return ' | '.join(context_parts)

    def _create_contextual_embedding(self, segment: LegalSegment) -> np.ndarray:
        """Create embedding for a segment with its legal context."""
        combined_text = f"{segment.context} | {segment.content}"
        return self.embedding_model.encode(combined_text)

    def _normalize_scores(self, vector_scores: np.ndarray, bm25_scores: np.ndarray) -> np.ndarray:
        """Normalize and combine vector similarity and BM25 scores."""
        if len(vector_scores) > 0:
            vector_scores = (vector_scores - vector_scores.min()) / (vector_scores.max() - vector_scores.min() + 1e-6)
            bm25_scores = (bm25_scores - bm25_scores.min()) / (bm25_scores.max() - bm25_scores.min() + 1e-6)
            
            # Use configured weights
            combined_scores = (self.embedding_weight * vector_scores + 
                             self.bm25_weight * bm25_scores)
            return combined_scores
        return np.array([])

    def _legal_rerank(self, segments: List[LegalSegment], query: str) -> List[LegalSegment]:
        """Rerank results based on legal relevance factors."""
        current_year = datetime.now().year
        
        for segment in segments:
            score = 1.0  # Base score
            
            # Adjust score based on court hierarchy
            if 'court_level' in segment.metadata:
                court_levels = {
                    'supreme': 1.0,
                    'appellate': 0.8,
                    'district': 0.6,
                    'trial': 0.4
                }
                score *= court_levels.get(segment.metadata['court_level'].lower(), 0.5)
            
            # Adjust for recency if date is available
            if 'date' in segment.metadata:
                try:
                    doc_year = int(segment.metadata['date'].split('-')[0])
                    years_old = current_year - doc_year
                    recency_score = max(0.5, 1 - (years_old / 50))  # Gradual decay over 50 years
                    score *= recency_score
                except (ValueError, IndexError):
                    pass
            
            segment.metadata['relevance_score'] = score
            
        # Sort by combined score
        return sorted(segments, key=lambda x: x.metadata.get('relevance_score', 0), reverse=True)

    def _process_documents(self) -> None:
        """Process and index legal documents."""
        try:
            # Clear existing index
            self.segments = []
            documents = []
            
            # Load and process documents
            for doc_path in self.document_paths:
                if doc_path.endswith('.json'):
                    with open(doc_path, 'r') as f:
                        doc_data = json.load(f)
                        doc = LegalDocument(**doc_data)
                        documents.append(doc)
                else:
                    # Handle other file types (markdown, text, etc.)
                    with open(doc_path, 'r') as f:
                        content = f.read()
                        doc = LegalDocument(
                            content=content,
                            doc_type="unknown",
                            jurisdiction="unknown",
                            title=Path(doc_path).stem
                        )
                        documents.append(doc)
            
            # Process each document
            for doc_idx, doc in enumerate(documents):
                segments = self._segment_document(doc)
                
                for seg_idx, segment_text in enumerate(segments):
                    context = self._generate_legal_context(segment_text, doc)
                    
                    segment = LegalSegment(
                        content=segment_text,
                        context=context,
                        doc_id=f"doc_{doc_idx}",
                        segment_id=seg_idx,
                        metadata={
                            "doc_type": doc.doc_type,
                            "jurisdiction": doc.jurisdiction,
                            "court_level": doc.court_level,
                            "date": doc.date,
                            "citation": doc.citation,
                            "source_path": str(doc_path)
                        }
                    )
                    self.segments.append(segment)
            
            # Create embeddings
            self.embeddings = np.vstack([
                self._create_contextual_embedding(segment)
                for segment in self.segments
            ])
            
            # Save embeddings
            np.save(self.persist_dir / "embeddings.npy", self.embeddings)
            
            # Create BM25 index
            tokenized_segments = [
                word_tokenize(f"{segment.context} {segment.content}".lower(), language='french')
                for segment in self.segments
            ]
            self.bm25 = BM25Okapi(tokenized_segments)
            
            logger.info(f"Processed {len(documents)} documents into {len(self.segments)} segments")
            
        except Exception as e:
            logger.error(f"Error processing documents: {str(e)}")
            raise ValueError(f"Failed to process documents: {str(e)}")

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant legal segments using hybrid search.
        
        Args:
            query: The legal query to process
            top_k: Number of top results to return

        Returns:
            List of dictionaries containing search results with legal context
        """
        try:
            # Load embeddings if not in memory
            if self.embeddings is None and (self.persist_dir / "embeddings.npy").exists():
                self.embeddings = np.load(self.persist_dir / "embeddings.npy")
            
            if self.embeddings is None:
                raise ValueError("No documents have been processed yet")
            
            # Encode query
            query_embedding = self.embedding_model.encode(query)
            
            # Get vector similarity scores
            vector_scores = np.dot(self.embeddings, query_embedding)
            
            # Get BM25 scores
            tokenized_query = word_tokenize(query.lower(), language='french')
            bm25_scores = np.array(self.bm25.get_scores(tokenized_query))
            
            # Combine and normalize scores
            combined_scores = self._normalize_scores(vector_scores, bm25_scores)
            
            # Get top k results
            top_indices = np.argsort(combined_scores)[-top_k:][::-1]
            top_segments = [self.segments[i] for i in top_indices]
            
            # Rerank based on legal factors
            reranked_segments = self._legal_rerank(top_segments, query)
            
            # Format results
            results = []
            for segment in reranked_segments:
                result = {
                    "content": segment.content,
                    "legal_context": segment.context,
                    "metadata": segment.metadata,
                    "relevance_score": segment.metadata.get('relevance_score', 0),
                    "source_path": segment.metadata.get('source_path', '')
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error executing legal RAG search: {str(e)}")
            raise ValueError(f"Failed to execute search: {str(e)}")

if __name__ == "__main__":
    # Example usage
    tool = LegalRAGTool(
        persist_dir="./storage/legal_rag",
        document_paths=[
            "./docs/test/code_civile.md",
            "./docs/test/code_procedure.md"
        ],
        chunk_size=512,
        chunk_overlap=50,
        bm25_weight=0.3,
        embedding_weight=0.7
    )
    
    results = tool.search("Mon voisin a créé des ouvertures (fenêtres) donnant directement sur ma propriété, ce qui porte atteinte à ma vie privée. Je souhaite faire valoir mes droits et le contraindre à fermer ces ouvertures.", top_k=5)
    print(json.dumps(results, indent=2))
