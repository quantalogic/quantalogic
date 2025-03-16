"""Multilingual RAG Tool optimized for French and Arabic using HuggingFace models.

This tool provides enhanced RAG capabilities with:
- Multilingual support (French/Arabic) using specialized embedding models
- Improved query processing with source attribution
- Persistent ChromaDB storage
- Enhanced response formatting
"""

import os
from typing import List, Optional, Dict
from dataclasses import dataclass

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

# Configure detailed logging
logger.remove()
logger.add(
    lambda msg: print(msg),
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG"
)

@dataclass
class SearchResult:
    """Structured search result with source attribution."""
    answer: str
    sources: List[Dict[str, str]]
    confidence: float

class MultilingualRagTool(Tool):
    """Enhanced RAG tool with multilingual support and improved response formatting."""

    name: str = "multilingual_rag"
    description: str = (
        "Advanced multilingual RAG tool optimized for French and Arabic content "
        "with detailed responses and source attribution."
    )
    arguments: List[ToolArgument] = [
        ToolArgument(
            name="query",
            arg_type="string",
            description="Query in French, Arabic, or English",
            required=True,
            example="ما هو الموضوع الرئيسي؟ / Quel est le sujet principal?",
        ),
        ToolArgument(
            name="max_sources",
            arg_type="int",
            description="Maximum number of sources to return",
            required=False,
            example="3",
        ),
    ]

    def __init__(
        self,
        persist_dir: str = "./storage/multilingual_rag",
        document_paths: Optional[List[str]] = None,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ):
        """Initialize the multilingual RAG tool."""
        super().__init__()
        self.persist_dir = os.path.abspath(persist_dir)
        logger.info(f"Initializing MultilingualRagTool with persist_dir: {self.persist_dir}")
        
        # Use paraphrase-multilingual-mpnet-base-v2 for better multilingual understanding
        logger.info("Initializing embedding model...")
        self.embed_model = HuggingFaceEmbedding(
            model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            embed_batch_size=8  # Smaller batch size for better memory usage
        )
        logger.info("Embedding model initialized successfully")
        
        # Configure ChromaDB
        chroma_persist_dir = os.path.join(self.persist_dir, "chroma")
        os.makedirs(chroma_persist_dir, exist_ok=True)
        logger.info(f"Setting up ChromaDB at: {chroma_persist_dir}")
        
        chroma_client = chromadb.PersistentClient(path=chroma_persist_dir)
        collection = chroma_client.create_collection(
            name="multilingual_collection",
            get_or_create=True
        )
        logger.info("ChromaDB collection created/loaded successfully")
        
        self.vector_store = ChromaVectorStore(chroma_collection=collection)
        
        # Configure llama-index settings
        Settings.embed_model = self.embed_model
        Settings.chunk_size = chunk_size
        Settings.chunk_overlap = chunk_overlap
        Settings.num_output = 1024  # Increased output length
        logger.info(f"Configured settings - chunk_size: {chunk_size}, chunk_overlap: {chunk_overlap}")
        
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        
        # Initialize text splitter with better PDF handling
        self.text_splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            paragraph_separator="\n\n",
            tokenizer=lambda x: x.replace("\n", " ").split(" ")  # Better handling of PDF line breaks
        )
        
        # Initialize or load index
        self.index = self._initialize_index(document_paths)

    def _load_documents(self, document_paths: List[str]) -> List[Document]:
        """Load documents with special handling for PDFs."""
        all_documents = []
        pdf_reader = PDFReader()
        
        for path in document_paths:
            if not os.path.exists(path):
                logger.warning(f"Document path does not exist: {path}")
                continue
            
            logger.info(f"Loading document: {path}")
            try:
                if path.lower().endswith('.pdf'):
                    # Special handling for PDFs
                    docs = pdf_reader.load_data(
                        path,
                        extra_info={
                            "file_name": os.path.basename(path),
                            "file_path": path
                        }
                    )
                    logger.info(f"Loaded PDF with {len(docs)} pages")
                    
                    # Process each page to improve text quality
                    processed_docs = []
                    for doc in docs:
                        # Clean up text
                        text = doc.text
                        text = text.replace('\n\n', '[PAGE_BREAK]')  # Preserve important breaks
                        text = text.replace('\n', ' ')  # Replace single breaks with space
                        text = text.replace('[PAGE_BREAK]', '\n\n')  # Restore important breaks
                        text = ' '.join(text.split())  # Normalize whitespace
                        
                        # Create new document with cleaned text
                        processed_doc = Document(
                            text=text,
                            metadata={
                                **doc.metadata,
                                "file_name": os.path.basename(path),
                                "file_path": path,
                                "page_number": doc.metadata.get("page_number", "unknown")
                            }
                        )
                        processed_docs.append(processed_doc)
                    
                    all_documents.extend(processed_docs)
                else:
                    docs = SimpleDirectoryReader(
                        input_files=[path],
                        filename_as_id=True,
                        file_metadata=lambda x: {"file_name": os.path.basename(x), "file_path": x}
                    ).load_data()
                    logger.info(f"Loaded text document: {path}")
                    all_documents.extend(docs)
                
                # Log document details
                for doc in docs:
                    logger.debug(f"Document content length: {len(doc.text)} characters")
                    logger.debug(f"Document metadata: {doc.metadata}")
                    # Log a preview of the content
                    preview = doc.text[:200].replace('\n', ' ').strip()
                    logger.debug(f"Content preview: {preview}...")
                
            except Exception as e:
                logger.error(f"Error loading document {path}: {str(e)}")
                continue
                
        return all_documents

    def _initialize_index(self, document_paths: Optional[List[str]]) -> Optional[VectorStoreIndex]:
        """Initialize or load the vector index."""
        logger.info("Initializing index...")
        
        if document_paths:
            logger.info("Document paths provided, creating new index")
            return self._create_index(document_paths)
        
        # Try loading existing index
        index_path = os.path.join(self.persist_dir, "docstore.json")
        if os.path.exists(index_path):
            try:
                logger.info(f"Loading existing index from {index_path}")
                return load_index_from_storage(storage_context=self.storage_context)
            except Exception as e:
                logger.error(f"Failed to load existing index: {str(e)}")
        else:
            logger.warning("No existing index found and no documents provided")
        
        return None

    def _create_index(self, document_paths: List[str]) -> Optional[VectorStoreIndex]:
        """Create a new index from documents."""
        try:
            # Load documents with special PDF handling
            all_documents = self._load_documents(document_paths)

            if not all_documents:
                logger.warning("No valid documents found")
                return None

            logger.info(f"Processing {len(all_documents)} documents...")
            # Log document chunks
            total_chunks = 0
            for doc in all_documents:
                chunks = self.text_splitter.split_text(doc.text)
                total_chunks += len(chunks)
                logger.debug(f"Created {len(chunks)} chunks from document {doc.metadata.get('file_name', 'unknown')}")
                for i, chunk in enumerate(chunks[:2]):  # Log only first 2 chunks as preview
                    logger.debug(f"Chunk {i+1} preview ({len(chunk)} chars): {chunk[:100]}...")

            logger.info(f"Total chunks created: {total_chunks}")
            logger.info("Creating vector index...")
            
            index = VectorStoreIndex.from_documents(
                all_documents,
                storage_context=self.storage_context,
                transformations=[self.text_splitter],
                show_progress=True
            )
            
            # Persist index
            logger.info("Persisting index...")
            self.storage_context.persist(persist_dir=self.persist_dir)
            logger.info(f"Created and persisted index with {len(all_documents)} documents")
            
            return index

        except Exception as e:
            logger.error(f"Error creating index: {str(e)}")
            return None

    def execute(self, query: str, max_sources: int = 3) -> str:
        """Execute a multilingual query with enhanced response formatting."""
        try:
            if not self.index:
                raise ValueError("No index available. Please add documents first.")

            logger.info(f"Processing query: {query}")
            
            # Configure query engine with settings for detailed responses
            query_engine = self.index.as_query_engine(
                similarity_top_k=15,  # Get more candidates for better context
                node_postprocessors=[
                    SimilarityPostprocessor(similarity_cutoff=0.2)  # More lenient for broader context
                ],
                response_mode="tree_summarize",  # Better for synthesizing detailed responses
                response_kwargs={
                    "response_template": (
                        "Based on the provided documents, here is a detailed analysis:\n\n"
                        "{response}\n\n"
                        "Key points from the sources:\n"
                        "{context_str}"
                    )
                },
                streaming=False,
                verbose=True
            )
            logger.info("Query engine configured")

            # Execute query
            logger.info("Executing query...")
            response = query_engine.query(query)
            logger.debug(f"Raw response: {str(response)}")
            logger.debug(f"Number of source nodes: {len(response.source_nodes)}")
            
            # Log source nodes details
            for i, node in enumerate(response.source_nodes):
                logger.debug(f"Source node {i+1}:")
                logger.debug(f"  Score: {node.score}")
                logger.debug(f"  Text: {node.node.text[:300]}...")
                logger.debug(f"  Metadata: {node.node.metadata}")
                logger.debug(f"  Page: {node.node.metadata.get('page_number', 'N/A')}")
            
            # Format response
            result = self._format_response(response, max_sources)
            logger.info("Response formatted successfully")
            
            if not result.answer or result.answer.strip() == "Empty Response":
                logger.warning("Empty response received, using direct node text")
                # Enhanced fallback with structured information
                sections = []
                current_topic = None
                
                for node in response.source_nodes[:5]:
                    if node.score < 0.2:
                        continue
                    
                    text = node.node.text.strip()
                    if not text:
                        continue
                        
                    # Try to identify topic from content
                    if text.startswith('Art.'):
                        current_topic = "Legal Framework"
                    elif any(word in text.lower() for word in ['comité', 'committee', 'اللجنة']):
                        current_topic = "Committee Structure and Responsibilities"
                    elif any(word in text.lower() for word in ['recensement', 'census', 'تعداد']):
                        current_topic = "Census Operations"
                    else:
                        current_topic = "General Information"
                    
                    page_info = f"Page {node.node.metadata.get('page_number', 'N/A')}"
                    doc_info = f"Document: {node.node.metadata.get('file_name', 'Unknown')}"
                    sections.append(f"\n### {current_topic}\n{text}\n[Source: {doc_info} | {page_info} | Relevance: {node.score:.2f}]")
                
                if sections:
                    result.answer = "\n\n".join(sections)
                else:
                    result.answer = "No relevant content found in the documents."
            
            # Build enhanced output with detailed structure
            output = ["# Detailed Analysis\n"]
            output.append(result.answer)
            
            # Add source summary section
            output.append("\n## Source Documents\n")
            source_summary = {}
            
            for source in result.sources:
                file_name = source['file']
                if file_name not in source_summary:
                    source_summary[file_name] = {
                        'pages': set(),
                        'relevance_scores': [],
                        'excerpts': []
                    }
                
                source_summary[file_name]['pages'].add(source.get('page', 'N/A'))
                source_summary[file_name]['relevance_scores'].append(source['score'])
                source_summary[file_name]['excerpts'].append(source['content'])
            
            for file_name, summary in source_summary.items():
                output.append(f"\n### {file_name}")
                output.append(f"- Pages Referenced: {', '.join(sorted(summary['pages']))}")
                output.append(f"- Average Relevance: {sum(summary['relevance_scores']) / len(summary['relevance_scores']):.2f}%")
                output.append("\nKey Excerpts:")
                for i, excerpt in enumerate(summary['excerpts'], 1):
                    output.append(f"\n{i}. {excerpt}")
            
            return "\n".join(output)

        except Exception as e:
            logger.error(f"Query failed: {str(e)}")
            raise RuntimeError(f"Query failed: {str(e)}")

    def _format_response(self, response: Response, max_sources: int = 3) -> SearchResult:
        """Format the query response with source attribution."""
        sources = []
        for node in response.source_nodes[:max_sources]:
            if node.score < 0.2:  # Skip very low relevance nodes
                continue
                
            source_info = {
                "content": node.node.text[:300] + "..." if len(node.node.text) > 300 else node.node.text,
                "file": node.node.metadata.get("file_name", "Unknown"),
                "page": node.node.metadata.get("page_number", "N/A"),
                "score": round(node.score * 100, 2) if node.score else None,
            }
            sources.append(source_info)

        return SearchResult(
            answer=str(response),
            sources=sources,
            confidence=response.source_nodes[0].score if response.source_nodes else 0.0
        )

    def add_documents(self, document_paths: List[str]) -> bool:
        """Add new documents to the index."""
        try:
            new_index = self._create_index(document_paths)
            if new_index:
                self.index = new_index
                return True
            return False
        except Exception as e:
            logger.error(f"Error adding documents: {str(e)}")
            return False


if __name__ == "__main__":
    # Example usage
    logger.info("Starting example usage...")
    
    # Clean up any existing index
    import shutil
    if os.path.exists("./storage/multilingual_rag"):
        shutil.rmtree("./storage/multilingual_rag")
        logger.info("Cleaned up existing index")
    
    tool = MultilingualRagTool(
        persist_dir="./storage/multilingual_rag",
        document_paths=[
            "./docs/test/F2015054.pdf",
            "./docs/test/F2015055.pdf"
        ],
        chunk_size=512,  # Increased for PDF documents
        chunk_overlap=50
    )
    
    # Example queries in different languages
    queries = [
        "Donne moi toutes les lois lister dans mes documents, détaille chaqune des lois", 
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        try:
            print(tool.execute(query, max_sources=2))
        except Exception as e:
            print(f"Error: {str(e)}")
