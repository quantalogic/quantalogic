"""Enhanced RAG Tool with Mistral AI OCR and Embeddings.

This tool provides advanced RAG capabilities with:
- Mistral AI OCR for document processing
- Mistral AI embeddings for better semantic search
- Markdown conversion for structured output
- Persistent ChromaDB storage
- Enhanced response formatting
"""

import os
from typing import List, Optional, Dict
from dataclasses import dataclass
import json
from pathlib import Path

import chromadb
from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
    Response,
    Settings,
    Document,
)
from llama_index.llms.mistralai import MistralAI
from llama_index.embeddings.mistralai import MistralAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.readers.file.docs import PDFReader
from loguru import logger
import fitz  # PyMuPDF for enhanced PDF processing
import markdown
from PIL import Image
import pytesseract

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
    markdown_content: str

class MistralOcrRagTool(Tool):
    """Enhanced RAG tool with Mistral AI OCR and embeddings."""

    name: str = "mistral_ocr_rag"
    description: str = (
        "Advanced RAG tool using Mistral AI for OCR and embeddings, "
        "with markdown conversion and detailed responses."
    )
    arguments: List[ToolArgument] = [
        ToolArgument(
            name="query",
            arg_type="string",
            description="Natural language query for document search",
            required=True,
            example="What are the main points discussed in the document?",
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
        persist_dir: str = "./storage/mistral_rag",
        document_paths: Optional[List[str]] = None,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        mistral_api_key: Optional[str] = None,
    ):
        """Initialize the Mistral AI RAG tool."""
        super().__init__()
        self.persist_dir = os.path.abspath(persist_dir)
        self.mistral_api_key = mistral_api_key or os.getenv("MISTRAL_API_KEY")
        
        if not self.mistral_api_key:
            raise ValueError("Mistral API key is required. Set it via MISTRAL_API_KEY environment variable")
            
        logger.info(f"Initializing MistralOcrRagTool with persist_dir: {self.persist_dir}")
        
        # Initialize Mistral AI components
        self.llm = MistralAI(
            api_key=self.mistral_api_key,
            model="mistral-medium"
        )
        
        self.embed_model = MistralAIEmbedding(
            model_name="mistral-embed",
            api_key=self.mistral_api_key
        )
        
        # Configure global settings
        Settings.llm = self.llm
        Settings.embed_model = self.embed_model
        Settings.chunk_size = chunk_size
        Settings.chunk_overlap = chunk_overlap
        Settings.num_output = 1024
        
        # Configure ChromaDB
        chroma_persist_dir = os.path.join(self.persist_dir, "chroma")
        os.makedirs(chroma_persist_dir, exist_ok=True)
        logger.info(f"Setting up ChromaDB at: {chroma_persist_dir}")
        
        chroma_client = chromadb.PersistentClient(path=chroma_persist_dir)
        collection = chroma_client.create_collection(
            name="mistral_collection",
            get_or_create=True
        )
        
        self.vector_store = ChromaVectorStore(chroma_collection=collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        
        # Initialize text splitter
        self.text_splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            paragraph_separator="\n\n"
        )
        
        # Initialize or load index
        self.index = self._initialize_index(document_paths)

    def _extract_text_from_image(self, image_path: str) -> str:
        """Extract text from image using Tesseract OCR."""
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            return text
        except Exception as e:
            logger.error(f"Error extracting text from image {image_path}: {str(e)}")
            return ""

    def _convert_to_markdown(self, text: str) -> str:
        """Convert text to markdown format using Mistral AI."""
        try:
            prompt = f"Convert the following text to well-formatted markdown, maintaining the original structure and meaning:\n\n{text}"
            response = self.llm.complete(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error converting to markdown: {str(e)}")
            return text

    def _process_pdf_with_ocr(self, pdf_path: str) -> List[Dict[str, str]]:
        """Process PDF with enhanced OCR capabilities."""
        pages = []
        try:
            pdf_document = fitz.open(pdf_path)
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                
                # Extract text directly from PDF
                text = page.get_text()
                
                # If text extraction yields poor results, try OCR
                if len(text.strip()) < 50:  # Arbitrary threshold
                    pix = page.get_pixmap()
                    image_path = f"temp_page_{page_num}.png"
                    pix.save(image_path)
                    
                    # Extract text using OCR
                    text = self._extract_text_from_image(image_path)
                    
                    # Clean up temporary image
                    os.remove(image_path)
                
                # Convert to markdown
                markdown_text = self._convert_to_markdown(text)
                
                pages.append({
                    "text": markdown_text,
                    "page_num": page_num + 1,
                    "source": pdf_path
                })
                
            pdf_document.close()
            return pages
            
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
            return []

    def _load_documents(self, document_paths: List[str]) -> List[Document]:
        """Load and process documents with OCR and markdown conversion."""
        all_documents = []
        
        for path in document_paths:
            if not os.path.exists(path):
                logger.warning(f"Document path does not exist: {path}")
                continue
                
            logger.info(f"Processing document: {path}")
            try:
                if path.lower().endswith('.pdf'):
                    # Process PDF with OCR
                    pages = self._process_pdf_with_ocr(path)
                    
                    for page in pages:
                        doc = Document(
                            text=page["text"],
                            metadata={
                                "file_name": os.path.basename(path),
                                "file_path": path,
                                "page_number": page["page_num"],
                                "is_markdown": True
                            }
                        )
                        all_documents.append(doc)
                        
                else:
                    # Handle other file types
                    with open(path, 'r', encoding='utf-8') as f:
                        text = f.read()
                        
                    # Convert to markdown
                    markdown_text = self._convert_to_markdown(text)
                    
                    doc = Document(
                        text=markdown_text,
                        metadata={
                            "file_name": os.path.basename(path),
                            "file_path": path,
                            "is_markdown": True
                        }
                    )
                    all_documents.append(doc)
                
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
                
        return None

    def _create_index(self, document_paths: List[str]) -> Optional[VectorStoreIndex]:
        """Create a new index from documents."""
        try:
            all_documents = self._load_documents(document_paths)
            
            if not all_documents:
                logger.warning("No valid documents found")
                return None
                
            logger.info(f"Creating index with {len(all_documents)} documents...")
            
            index = VectorStoreIndex.from_documents(
                all_documents,
                storage_context=self.storage_context,
                transformations=[self.text_splitter],
                show_progress=True
            )
            
            # Persist index
            self.storage_context.persist(persist_dir=self.persist_dir)
            logger.info("Index created and persisted successfully")
            
            return index
            
        except Exception as e:
            logger.error(f"Error creating index: {str(e)}")
            return None

    def execute(self, query: str, max_sources: int = 3) -> str:
        """Execute a query with enhanced markdown formatting."""
        try:
            if not self.index:
                raise ValueError("No index available. Please add documents first.")
                
            logger.info(f"Processing query: {query}")
            
            # Configure query engine
            query_engine = self.index.as_query_engine(
                similarity_top_k=max_sources * 2,
                node_postprocessors=[
                    SimilarityPostprocessor(similarity_cutoff=0.2)
                ],
                response_mode="tree_summarize",
                verbose=True
            )
            
            # Execute query
            response = query_engine.query(query)
            
            # Format response with markdown
            result = self._format_response(response, max_sources)
            
            # Build final output
            output = [
                "# Query Results\n",
                result.answer,
                "\n## Sources\n"
            ]
            
            for source in result.sources:
                output.extend([
                    f"\n### {source['file']}",
                    f"- Page: {source.get('page', 'N/A')}",
                    f"- Relevance: {source['score']}%",
                    "\n```markdown",
                    source['content'],
                    "```\n"
                ])
                
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Query failed: {str(e)}")
            raise RuntimeError(f"Query failed: {str(e)}")

    def _format_response(self, response: Response, max_sources: int = 3) -> SearchResult:
        """Format the query response with markdown and source attribution."""
        sources = []
        markdown_content = ""
        
        for node in response.source_nodes[:max_sources]:
            if node.score < 0.2:
                continue
                
            source_info = {
                "content": node.node.text[:300] + "..." if len(node.node.text) > 300 else node.node.text,
                "file": node.node.metadata.get("file_name", "Unknown"),
                "page": node.node.metadata.get("page_number", "N/A"),
                "score": round(node.score * 100, 2)
            }
            sources.append(source_info)
            
            # Accumulate markdown content
            if node.node.metadata.get("is_markdown"):
                markdown_content += f"\n\n{node.node.text}"
                
        return SearchResult(
            answer=str(response),
            sources=sources,
            confidence=response.source_nodes[0].score if response.source_nodes else 0.0,
            markdown_content=markdown_content
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
    if os.path.exists("./storage/mistral_rag"):
        shutil.rmtree("./storage/mistral_rag")
        logger.info("Cleaned up existing index")
    
    # Initialize tool with Mistral API key
    tool = MistralOcrRagTool(
        persist_dir="./storage/mistral_rag",
        document_paths=[
            "./docs/test/F2015054.pdf",
            "./docs/test/F2015055.pdf"
        ],
        chunk_size=512,
        chunk_overlap=50,
        mistral_api_key="your-api-key-here"  # Replace with actual API key
    )
    
    # Example query
    query = "What are the main points discussed in the documents?"
    try:
        print(tool.execute(query, max_sources=2))
    except Exception as e:
        print(f"Error: {str(e)}")
