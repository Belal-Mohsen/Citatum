"""Process controller for document processing and chunk extraction"""
import os
from typing import Union, List, Optional
from langchain_community.document_loaders import TextLoader, PyMuPDFLoader
from langchain_core.documents import Document as LangChainDocument

from src.utils.logger import get_logger
from .BaseController import BaseController
from .TopicController import TopicController

logger = get_logger(__name__)


class ProcessController(BaseController):
    """Controller for document processing and chunk extraction"""
    
    def __init__(self, topic_id: Union[str, int]):
        """
        Initialize ProcessController with topic_id.
        
        Args:
            topic_id: Topic identifier (str or int)
        """
        super().__init__()
        self.topic_id = topic_id
        
        # Get topic path using TopicController and store as project_path
        topic_controller = TopicController()
        self.project_path = topic_controller.get_topic_path(topic_id)
    
    def get_file_extension(self, document_id: str) -> str:
        """
        Extract file extension from document_id.
        
        Args:
            document_id: Document identifier (filename or path)
        
        Returns:
            File extension (e.g., '.txt', '.pdf') including the dot
        """
        _, ext = os.path.splitext(document_id)
        return ext
    
    def get_file_loader(self, document_id: str) -> Optional[object]:
        """
        Get appropriate LangChain loader for the document.
        
        Args:
            document_id: Document identifier (filename)
        
        Returns:
            LangChain loader instance (TextLoader or PyMuPDFLoader) or None if unsupported
        """
        # Construct file path: {self.project_path}/{document_id}
        file_path = os.path.join(self.project_path, document_id)
        
        # Check if file exists
        if not os.path.exists(file_path):
            return None
        
        # Get file extension
        extension = self.get_file_extension(document_id)
        
        # Return appropriate loader based on extension
        if extension == '.txt':
            return TextLoader(file_path, encoding="utf-8")
        elif extension == '.pdf':
            return PyMuPDFLoader(file_path)
        else:
            # Unsupported format
            return None
    
    def get_file_content(self, document_id: str) -> Optional[List[LangChainDocument]]:
        """
        Load document content with page numbers.
        
        Args:
            document_id: Document identifier (filename)
        
        Returns:
            List of LangChain Document objects or None if file cannot be loaded
        """
        # Get file loader
        loader = self.get_file_loader(document_id)
        
        if loader is None:
            return None
        
        # Call loader.load() if loader exists
        try:
            documents = loader.load()
            return documents
        except Exception as e:
            # Log error and return None
            logger.error(f"Error loading file {document_id}: {e}")
            return None
    
    def process_file_content(
        self,
        file_content: List[LangChainDocument],
        document_id: str,
        chunk_size: int = 100,
        overlap_size: int = 20
    ) -> List[LangChainDocument]:
        """
        Process file content into chunks with page tracking.
        
        Args:
            file_content: List of LangChain Document objects from loader
            document_id: Document identifier
            chunk_size: Size of each chunk in characters (default: 100)
            overlap_size: Overlap size between chunks (default: 20, not used in simple splitter)
        
        Returns:
            List of LangChain Document objects with chunks
        """
        # Extract page_content from each document
        texts = [doc.page_content for doc in file_content]
        
        # Extract metadata from each document (preserve page numbers if available)
        metadatas = [doc.metadata for doc in file_content]
        
        # Call process_simpler_splitter with texts, metadatas, chunk_size
        chunks = self.process_simpler_splitter(texts, metadatas, chunk_size)
        
        return chunks
    
    def process_simpler_splitter(
        self,
        texts: List[str],
        metadatas: List[dict],
        chunk_size: int,
        splitter_tag: str = "\n"
    ) -> List[LangChainDocument]:
        """
        Simple text splitter that splits by newline and accumulates lines until chunk_size.
        
        Args:
            texts: List of text strings
            metadatas: List of metadata dictionaries (preserve page numbers)
            chunk_size: Maximum size of each chunk in characters
            splitter_tag: Tag to split by (default: "\n" for newline)
        
        Returns:
            List of LangChain Document objects with chunks
        """
        # Join all texts with space
        combined_text = " ".join(texts)
        
        # Split by splitter_tag (newline)
        lines = combined_text.split(splitter_tag)
        
        # Filter empty lines (length > 1 after strip)
        filtered_lines = [line for line in lines if len(line.strip()) > 1]
        
        # Accumulate lines until chunk_size is reached
        chunks = []
        current_chunk = []
        current_size = 0
        current_metadata = metadatas[0] if metadatas else {}  # Use first metadata as base
        
        for line in filtered_lines:
            line_stripped = line.strip()
            line_size = len(line_stripped)
            
            # If adding this line would exceed chunk_size, save current chunk and start new one
            if current_size + line_size > chunk_size and current_chunk:
                # Create chunk from accumulated lines
                chunk_text = " ".join(current_chunk).strip()
                if chunk_text:
                    chunks.append(LangChainDocument(
                        page_content=chunk_text,
                        metadata=current_metadata.copy()
                    ))
                
                # Reset for new chunk
                current_chunk = [line_stripped]
                current_size = line_size
            else:
                # Add line to current chunk
                current_chunk.append(line_stripped)
                current_size += line_size
        
        # Add remaining chunk if any
        if current_chunk:
            chunk_text = " ".join(current_chunk).strip()
            if chunk_text:
                chunks.append(LangChainDocument(
                    page_content=chunk_text,
                    metadata=current_metadata.copy()
                ))
        
        return chunks
