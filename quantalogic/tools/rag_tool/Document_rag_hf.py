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
import asyncio
import shutil

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

# Configure tool-specific logging
logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
)

@dataclass
class SearchResult:
    """Structured search result with source attribution."""
    answer: str
    sources: List[Dict[str, str]]
    confidence: float

class RagToolHf(Tool):
    """Enhanced RAG tool with multilingual support and improved response formatting."""

    name: str = "rag_tool_hf"
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
        name: str = "rag_tool_hf", 
        persist_dir: str = "./storage/multilingual_rag",
        document_paths: Optional[List[str]] = None,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        use_ocr_for_pdfs: bool = False,
        ocr_model: str = "openai/gpt-4o-mini", # "gemini/gemini-2.0-flash",
        embed_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2" # "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    ):
        """Initialize the multilingual RAG tool."""
        super().__init__()
        self.name = name
        self.persist_dir = os.path.abspath(persist_dir)
        self.use_ocr_for_pdfs = use_ocr_for_pdfs
        self.ocr_model = ocr_model
        
        # Clean up existing index if embedding model changed
        chroma_persist_dir = os.path.join(self.persist_dir, "chroma")
        if os.path.exists(chroma_persist_dir):
            shutil.rmtree(chroma_persist_dir)
            logger.info("Cleaned up existing index due to embedding model change")

        # Use paraphrase-multilingual-mpnet-base-v2 for better multilingual understanding
        self.embed_model = HuggingFaceEmbedding(
            model_name=embed_model,
            embed_batch_size=8  # Smaller batch size for better memory usage
        )
        
        # Configure ChromaDB
        chroma_persist_dir = os.path.join(self.persist_dir, "chroma")
        os.makedirs(chroma_persist_dir, exist_ok=True)
        
        chroma_client = chromadb.PersistentClient(path=chroma_persist_dir)
        collection = chroma_client.create_collection(
            name="multilingual_collection",
            get_or_create=True
        )
        
        self.vector_store = ChromaVectorStore(chroma_collection=collection)
        
        # Configure llama-index settings
        Settings.embed_model = self.embed_model
        Settings.chunk_size = chunk_size
        Settings.chunk_overlap = chunk_overlap
        Settings.num_output = 1024  # Increased output length
        
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

    async def _process_pdf_with_ocr(self, path: str) -> List[Document]:
        """Process a PDF file using OCR and convert to Documents."""
        try:
            converter = PDFToMarkdownConverter(
                model=self.ocr_model,
                custom_system_prompt=(
                    "Convert the PDF page to clean, well-formatted text. "
                    "Preserve all content including tables, lists, and mathematical notation. "
                    "For images and charts, provide detailed descriptions. "
                    "Maintain the original document structure and hierarchy."
                )
            )
            
            markdown_content = await converter.convert_pdf(path)
            if not markdown_content:
                logger.warning(f"OCR produced no content for {path}")
                return []
                
            # Create a single document with the full content
            doc = Document(
                text=markdown_content,
                metadata={
                    "file_name": os.path.basename(path),
                    "file_path": path,
                    "processing_method": "ocr"
                }
            )
            return [doc]
            
        except Exception as e:
            logger.error(f"Error processing PDF with OCR {path}: {e}")
            return []

    def _load_documents(self, document_paths: List[str]) -> List[Document]:
        """Load documents with special handling for PDFs."""
        all_documents = []
        pdf_reader = PDFReader()
        
        for path in document_paths:
            if not os.path.exists(path):
                logger.warning(f"Document path does not exist: {path}")
                continue
            
            try:
                if path.lower().endswith('.pdf'):
                    if self.use_ocr_for_pdfs:
                        # Use asyncio to run the async OCR function
                        docs = asyncio.run(self._process_pdf_with_ocr(path))
                    else:
                        # Use standard PDF reader
                        docs = pdf_reader.load_data(
                            path,
                            extra_info={
                                "file_name": os.path.basename(path),
                                "file_path": path,
                                "processing_method": "standard"
                            }
                        )
                    
                    if not self.use_ocr_for_pdfs:
                        # Process each page to improve text quality (only for standard PDF reader)
                        processed_docs = []
                        for doc in docs:
                            # Clean up text
                            text = doc.text
                            text = text.replace('\n\n', '[PAGE_BREAK]')
                            text = text.replace('\n', ' ')
                            text = text.replace('[PAGE_BREAK]', '\n\n')
                            text = ' '.join(text.split())
                            
                            processed_doc = Document(
                                text=text,
                                metadata={
                                    **doc.metadata,
                                    "file_name": os.path.basename(path),
                                    "file_path": path,
                                    "page_number": doc.metadata.get("page_number", "unknown"),
                                    "processing_method": "standard"
                                }
                            )
                            processed_docs.append(processed_doc)
                        docs = processed_docs
                else:
                    docs = SimpleDirectoryReader(
                        input_files=[path],
                        filename_as_id=True,
                        file_metadata=lambda x: {"file_name": os.path.basename(x), "file_path": x}
                    ).load_data()
                
                all_documents.extend(docs)
                
                # Log document details
                for doc in docs:
                    logger.debug(f"Document content length: {len(doc.text)} characters")
                    logger.debug(f"Document metadata: {doc.metadata}")
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
            return self._create_index(document_paths)
        
        # Try loading existing index
        index_path = os.path.join(self.persist_dir, "docstore.json")
        if os.path.exists(index_path):
            try:
                return load_index_from_storage(storage_context=self.storage_context)
            except Exception as e:
                logger.error(f"Failed to load existing index: {str(e)}")
        else:
            logger.warning("No existing index found and no documents provided")
        
        return None

    def _create_index(self, document_paths: List[str]) -> Optional[VectorStoreIndex]:
        """Create a new index from documents."""
        try:
            all_documents = self._load_documents(document_paths)

            if not all_documents:
                logger.warning("No valid documents found")
                return None

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
            
            query_engine = self.index.as_query_engine(
                similarity_top_k=15,  
                node_postprocessors=[
                    SimilarityPostprocessor(similarity_cutoff=0.2)  
                ],
                response_mode="tree_summarize",  
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
            
            response = query_engine.query(query)
            logger.debug(f"Raw response: {str(response)}")
            logger.debug(f"Number of source nodes: {len(response.source_nodes)}")
            
            for i, node in enumerate(response.source_nodes):
                logger.debug(f"Source node {i+1}:")
                logger.debug(f"  Score: {node.score}")
                logger.debug(f"  Text: {node.node.text[:300]}...")
                logger.debug(f"  Metadata: {node.node.metadata}")
                logger.debug(f"  Page: {node.node.metadata.get('page_number', 'N/A')}")
            
            result = self._format_response(response, max_sources)
            
            if not result.answer or result.answer.strip() == "Empty Response":
                logger.warning("Empty response received, using direct node text")
                sections = []
                current_topic = None
                
                for node in response.source_nodes[:5]:
                    if node.score < 0.2:
                        continue
                    
                    text = node.node.text.strip()
                    if not text:
                        continue
                        
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
            
            output = ["# Detailed Analysis\n"]
            output.append(result.answer)
            
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
            if node.score < 0.2:  
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
    # logger.info("Starting example usage...")
    
    # Clean up any existing index
    if os.path.exists("./storage/multilingual_rag"):
        shutil.rmtree("./storage/multilingual_rag")
        # logger.info("Cleaned up existing index")
    
    tool = RagToolHf(
        persist_dir="./storage/multilingual_rag",
        document_paths=[
            "./docs/test/Code_Civil.pdf",
        ],
        chunk_size=512,  
        chunk_overlap=50,
        use_ocr_for_pdfs=False,
        ocr_model="gemini/gemini-2.0-flash"
    )
    
    queries = [
        "Donne moi toutes les lois lister dans mes documents, détaille chaqune des lois", 
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        try:
            print(tool.execute(query, max_sources=2))
        except Exception as e:
            print(f"Error: {str(e)}")
