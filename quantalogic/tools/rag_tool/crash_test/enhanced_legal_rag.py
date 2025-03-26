"""Enhanced Multilingual Legal RAG Tool with Advanced Scoring.

This tool provides sophisticated RAG capabilities with:
- Multiple embedding models for better accuracy
- Advanced scoring and reranking
- Cross-encoder reranking for better relevance
- Enhanced legal context extraction
- Comprehensive result analysis
"""

import os
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
import json
from datetime import datetime
import shutil
import numpy as np
from sklearn.preprocessing import MinMaxScaler

import chromadb
from sentence_transformers import SentenceTransformer, CrossEncoder
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

# Configure logging
logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
)

@dataclass
class LegalContext:
    """Enhanced legal context with more detailed metadata."""
    document_type: Optional[str] = None
    jurisdiction: Optional[str] = None
    court_level: Optional[str] = None
    decision_date: Optional[str] = None
    key_concepts: Optional[List[str]] = None
    legal_references: Optional[List[str]] = None
    temporal_info: Optional[Dict[str, Any]] = None
    relevance_scores: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}

@dataclass
class SearchResult:
    """Comprehensive search result with detailed scoring."""
    content: str
    file_name: str
    page_number: str
    article_number: Optional[str] = None
    section: Optional[str] = None
    reference_number: Optional[str] = None
    embedding_score: float = 0.0
    cross_encoder_score: float = 0.0
    final_score: float = 0.0
    legal_context: Optional[LegalContext] = None
    metadata: Dict[str, Any] = None

class LegalTextSplitter(SentenceSplitter):
    """Advanced text splitter for legal documents."""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 128):
        super().__init__(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            paragraph_separator="\n\n"
        )
        
    def split_text(self, text: str) -> List[str]:
        """Split text while preserving legal document structure."""
        # Legal section markers
        markers = [
            'article', 'section', '§', 'chapitre',
            'titre', 'alinéa', 'paragraphe', 'annexe',
            'مادة', 'فصل', 'قسم', 'باب', 'فرع'
        ]
        
        sections = []
        current_section = []
        
        for line in text.split('\n'):
            line = line.strip()
            # Check for legal section markers
            if any(marker in line.lower() for marker in markers):
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

class EnhancedLegalRAG(Tool):
    """Advanced RAG tool for legal document retrieval with multiple scoring methods."""

    name: str = "enhanced_legal_rag"
    description: str = (
        "Advanced RAG tool for legal document retrieval with multiple scoring methods, "
        "cross-encoder reranking, and comprehensive legal context extraction."
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
            name="min_score",
            arg_type="float",
            description="Minimum final score (0-1) for returned sources",
            required=False,
            default="0.1",
        ),
    ]

    def __init__(
        self,
        name: str = "enhanced_legal_rag",
        persist_dir: str = "./storage/enhanced_legal_rag",
        document_paths: Optional[List[str]] = None,
        chunk_size: int = 512,
        chunk_overlap: int = 128,
        primary_embed_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        cross_encoder_model: str = "sentence-transformers/LaBSE",  # Changed to a valid multilingual model
        force_reindex: bool = False
    ):
        """Initialize the enhanced legal RAG tool."""
        super().__init__()
        self.name = name
        self.persist_dir = os.path.abspath(persist_dir)
        self.force_reindex = force_reindex

        # Initialize embedding models
        try:
            self.embed_model = HuggingFaceEmbedding(
                model_name=primary_embed_model,
                embed_batch_size=8
            )
            # Use the same model for cross-encoding since it's multilingual
            self.cross_encoder = SentenceTransformer(cross_encoder_model)
            logger.info(f"Successfully initialized embedding models")
        except Exception as e:
            logger.error(f"Failed to initialize embedding models: {e}")
            raise

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
        
        # Initialize text splitter
        self.text_splitter = LegalTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        # Initialize index
        self.index = self._initialize_index(document_paths)

    def _extract_legal_metadata(self, text: str) -> Dict[str, Any]:
        """Enhanced legal metadata extraction."""
        metadata = {}
        
        import re
        
        # Extract article numbers (support for multiple formats)
        article_patterns = [
            r'Article[s]?\s+(\d+[-\d]*)',
            r'Art\.\s*(\d+[-\d]*)',
            r'مادة\s+(\d+[-\d]*)',
            r'المادة\s+(\d+[-\d]*)'
        ]
        
        for pattern in article_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata['article_number'] = match.group(1)
                break
            
        # Extract section information
        section_patterns = [
            r'Section\s+(\d+[-\d]*)',
            r'Sect\.\s*(\d+[-\d]*)',
            r'قسم\s+(\d+[-\d]*)',
            r'فرع\s+(\d+[-\d]*)'
        ]
        
        for pattern in section_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata['section'] = match.group(1)
                break
            
        # Extract legal references
        ref_patterns = [
            r'(?:loi|décret|arrêté)\s+n[°o]?\s*(\d+[-./]\d+)',  # French
            r'(?:قانون|مرسوم|قرار)\s+(?:رقم\s+)?(\d+[-./]\d+)',  # Arabic
            r'(?:law|decree)\s+(?:no\.\s+)?(\d+[-./]\d+)'        # English
        ]
        
        references = []
        for pattern in ref_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            references.extend(match.group(1) for match in matches)
        
        if references:
            metadata['references'] = references
            metadata['reference_id'] = references[0]  # Primary reference
                
        return metadata

    def _preprocess_legal_text(self, text: str) -> str:
        """Enhanced legal text preprocessing."""
        # Basic cleaning
        text = ' '.join(text.split())
        
        # Fix common OCR issues
        text = text.replace('|', 'I')
        text = text.replace('0', 'O')
        text = text.replace('l', 'I')
        
        # Normalize punctuation
        text = text.replace('،', ',')
        text = text.replace('؛', ';')
        text = text.replace('«', '"')
        text = text.replace('»', '"')
        
        # Normalize section markers
        text = text.replace('§', 'Section')
        text = text.replace('Art.', 'Article')
        
        return text

    def _load_documents(self, document_paths: List[str]) -> List[Document]:
        """Load and preprocess legal documents with enhanced processing."""
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
                    # Clean and preprocess text
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
                logger.info(f"Processed {len(processed_docs)} documents from {path}")
                
            except Exception as e:
                logger.error(f"Error loading document {path}: {str(e)}")
                continue
                
        return all_documents

    def _initialize_index(self, document_paths: Optional[List[str]]) -> Optional[VectorStoreIndex]:
        """Initialize or load the vector index."""
        logger.info("Initializing index...")
        
        if document_paths:
            documents = self._load_documents(document_paths)
            return self._create_index(documents)
        
        # Try loading existing index
        index_path = os.path.join(self.persist_dir, "docstore.json")
        if os.path.exists(index_path) and not self.force_reindex:
            try:
                return load_index_from_storage(storage_context=self.storage_context)
            except Exception as e:
                logger.error(f"Failed to load existing index: {str(e)}")
        
        return None

    def _create_index(self, documents: List[Document]) -> Optional[VectorStoreIndex]:
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

    def execute(self, query: str, max_sources: int = 10, min_score: float = 0.1) -> str:
        """Execute enhanced search for legal documents."""
        try:
            if not self.index:
                raise ValueError("No index available. Please add documents first.")

            logger.info(f"Searching for legal sources with query: {query}")
            
            # Step 1: Initial embedding search with higher k
            initial_k = max_sources * 3  # Get more results for reranking
            query_engine = self.index.as_query_engine(
                similarity_top_k=initial_k,
                node_postprocessors=[
                    SimilarityPostprocessor(similarity_cutoff=0.01)  # Very low cutoff for initial search
                ],
                response_mode="no_text",
                streaming=False,
                verbose=True
            )
            
            response = query_engine.query(query)
            
            # Step 2: Process and rerank results
            results = []
            if response.source_nodes:
                # Prepare cross-encoder inputs
                texts = [node.node.text.strip() for node in response.source_nodes]
                
                # Get cross-encoder embeddings and calculate similarity scores
                query_embedding = self.cross_encoder.encode(query, convert_to_tensor=True)
                text_embeddings = self.cross_encoder.encode(texts, convert_to_tensor=True)
                cross_encoder_scores = [float(query_embedding @ text_embedding) for text_embedding in text_embeddings]
                
                # Get embedding scores
                embedding_scores = [node.score for node in response.source_nodes]
                
                # Normalize both score types
                norm_embedding_scores = self._normalize_scores(embedding_scores)
                norm_cross_encoder_scores = self._normalize_scores(cross_encoder_scores)
                
                # Combine scores and create results
                for i, node in enumerate(response.source_nodes):
                    # Calculate final score (weighted average)
                    final_score = 0.4 * norm_embedding_scores[i] + 0.6 * norm_cross_encoder_scores[i]
                    
                    if final_score < min_score:
                        continue
                    
                    # Extract metadata
                    metadata = node.node.metadata.copy()
                    metadata.update(self._extract_legal_metadata(node.node.text))
                    
                    # Create result entry
                    result = SearchResult(
                        content=node.node.text.strip(),
                        file_name=metadata.get('file_name', 'Unknown'),
                        page_number=str(metadata.get('page_number', 'N/A')),
                        article_number=metadata.get('article_number'),
                        section=metadata.get('section'),
                        reference_number=metadata.get('reference_id'),
                        embedding_score=norm_embedding_scores[i],
                        cross_encoder_score=norm_cross_encoder_scores[i],
                        final_score=final_score,
                        metadata={
                            'source_type': 'legal_document',
                            'query': query,
                            'timestamp': str(datetime.now().isoformat())
                        }
                    )
                    results.append(result)
            
            # Sort by final score and limit results
            results.sort(key=lambda x: x.final_score, reverse=True)
            results = results[:max_sources]
            
            # Format results for output
            output_results = []
            for result in results:
                output_results.append({
                    'content': result.content,
                    'file_name': result.file_name,
                    'page_number': result.page_number,
                    'article_number': result.article_number,
                    'section': result.section,
                    'reference_number': result.reference_number,
                    'scores': {
                        'embedding_score': round(result.embedding_score, 4),
                        'cross_encoder_score': round(result.cross_encoder_score, 4),
                        'final_score': round(result.final_score, 4)
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

if __name__ == "__main__":
    # Example usage
    try:
        # Clean up existing index if needed
        if os.path.exists("./storage/enhanced_legal_rag"):
            shutil.rmtree("./storage/enhanced_legal_rag")
        
        # Initialize tool
        tool = EnhancedLegalRAG(
            persist_dir="./storage/enhanced_legal_rag",
            document_paths=[
                "./docs/test/code_civile.md",
                "./docs/test/code_procedure.md"
            ],
            chunk_size=512,
            chunk_overlap=128,
            force_reindex=True
        )
        
        # Test queries
        test_queries = [
            "Quels sont les recours légaux en Algérie pour contraindre un voisin à fermer des ouvertures (fenêtres) donnant sur ma propriété ?",
        ]
        
        for query in test_queries:
            print(f"\nQuery: {query}")
            try:
                # Use lower min_score to get more results
                result = tool.execute(query, max_sources=10, min_score=0.1)
                print(result)
            except Exception as e:
                print(f"Error: {str(e)}")

    except Exception as e:
        logger.error(f"Failed to initialize or run tool: {e}")
