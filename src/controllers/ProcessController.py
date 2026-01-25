"""Process controller for document processing and chunk extraction"""
import os
from typing import Union, List, Optional, Tuple, Any, Callable
from langchain_community.document_loaders import TextLoader, PyMuPDFLoader
from langchain_core.documents import Document as LangChainDocument

from src.utils.logger import get_logger
from src.utils.config import config
from .BaseController import BaseController
from .TopicController import TopicController
from src.models.ChunkModel import ChunkModel
from src.models.db_schemas.citatum.schemas.topic import Topic

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
        return ext.lower()  # Normalize to lowercase for comparison
    
    def get_file_loader(self, file_path: str) -> Optional[object]:
        """
        Get appropriate LangChain loader for the document.
        
        Args:
            file_path: Full absolute path to the file
        
        Returns:
            LangChain loader instance (TextLoader or PyMuPDFLoader) or None if unsupported
        """
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(
                f"File not found at path: {file_path} | "
                f"topic_id={self.topic_id} | project_path={self.project_path}"
            )
            # List files in topic directory for debugging
            if os.path.exists(self.project_path):
                try:
                    files_in_dir = os.listdir(self.project_path)
                    logger.debug(f"Files in topic directory ({self.project_path}): {files_in_dir}")
                except Exception as e:
                    logger.warning(f"Could not list topic directory: {e}")
            return None
        
        # Get file extension
        extension = self.get_file_extension(file_path)
        logger.debug(f"File extension: {extension} for {file_path}")
        
        # Return appropriate loader based on extension
        if extension == '.txt':
            return TextLoader(file_path, encoding="utf-8")
        elif extension == '.pdf':
            return PyMuPDFLoader(file_path)
        else:
            logger.warning(f"Unsupported file extension: {extension} for {file_path}")
            return None
    
    def get_file_content(self, file_path: str) -> Optional[List[LangChainDocument]]:
        """
        Load document content with page numbers.
        
        Args:
            file_path: Full absolute path to the file
        
        Returns:
            List of LangChain Document objects or None if file cannot be loaded
        """
        logger.info(f"Loading file content from path: {file_path}")
        
        # Get file loader
        loader = self.get_file_loader(file_path)
        
        if loader is None:
            logger.error(f"Failed to create file loader for: {file_path}")
            return None
        
        # Call loader.load() if loader exists
        try:
            logger.debug(f"Calling loader.load() for: {file_path}")
            documents = loader.load()
            logger.info(
                f"Successfully loaded file | path={file_path} | "
                f"documents_count={len(documents)} | "
                f"total_chars={sum(len(doc.page_content) for doc in documents)}"
            )
            return documents
        except Exception as e:
            # Log error and return None
            logger.error(
                f"Error loading file {file_path} | error={str(e)}",
                exc_info=True
            )
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
        logger.debug(
            f"Processing file content: {len(file_content)} document(s), "
            f"chunk_size={chunk_size}, overlap_size={overlap_size}"
        )
        
        # Extract page_content from each document
        texts = [doc.page_content for doc in file_content]
        total_text_length = sum(len(text) for text in texts)
        logger.debug(
            f"Extracted {len(texts)} text segment(s), total length: {total_text_length} characters"
        )
        
        # Extract metadata from each document (preserve page numbers if available)
        metadatas = [doc.metadata for doc in file_content]
        
        # Call process_simpler_splitter with texts, metadatas, chunk_size
        logger.debug("Starting text splitting process")
        chunks = self.process_simpler_splitter(texts, metadatas, chunk_size)
        
        logger.debug(f"Text splitting completed: {len(chunks)} chunks created")
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
        logger.debug(
            f"Splitting {len(texts)} text segment(s) with chunk_size={chunk_size}, "
            f"splitter_tag={repr(splitter_tag)}"
        )
        
        # Join all texts with space
        combined_text = " ".join(texts)
        combined_length = len(combined_text)
        logger.debug(f"Combined text length: {combined_length} characters")
        
        # Split by splitter_tag (newline)
        lines = combined_text.split(splitter_tag)
        logger.debug(f"Split into {len(lines)} lines")
        
        # Filter empty lines (length > 1 after strip)
        filtered_lines = [line for line in lines if len(line.strip()) > 1]
        logger.debug(f"Filtered to {len(filtered_lines)} non-empty lines")
        
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
    
    async def chunk_and_store_document(
        self,
        file_path: str,
        topic: Topic,
        document_db_id: int,
        db_client: Callable,
    ) -> Tuple[List[Any], List[int]]:
        """
        Chunk a document and store chunks in the database.
        
        Args:
            file_path: Full path to the saved document file
            topic: Topic model instance
            document_db_id: Database ID of the created document
            db_client: Database client (session factory)
        
        Returns:
            Tuple of (all_chunks: list[Chunk], chunk_ids: list[int])
            Returns empty lists if chunking fails
        """
        logger.info(
            f"Starting chunking process for document {document_db_id} "
            f"(topic_id={topic.topic_id}, file_path={file_path})"
        )
        
        # Verify file exists at the provided absolute path
        if not os.path.exists(file_path):
            logger.error(
                f"File does not exist at provided path | file_path={file_path} | "
                f"topic_id={topic.topic_id} | document_db_id={document_db_id} | "
                f"project_path={self.project_path}"
            )
            # List files in topic directory for debugging
            if os.path.exists(self.project_path):
                try:
                    files_in_dir = os.listdir(self.project_path)
                    logger.debug(f"Files in topic directory ({self.project_path}): {files_in_dir}")
                except Exception as e:
                    logger.warning(f"Could not list topic directory: {e}")
            return [], []
        
        # Extract filename for logging
        filename_on_disk = os.path.basename(file_path)
        logger.debug(
            f"Processing file | filename={filename_on_disk} | "
            f"absolute_path={file_path} | topic_id={topic.topic_id}"
        )
        
        # Load file content using the absolute path directly
        logger.info(f"Loading file content from absolute path: {file_path}")
        file_content = self.get_file_content(file_path)
        if file_content is None:
            logger.error(
                f"Failed to load file content for chunking | file_path={file_path} | "
                f"filename={filename_on_disk} | topic_id={topic.topic_id} | "
                f"document_db_id={document_db_id} | project_path={self.project_path}"
            )
            return [], []
        
        logger.info(
            f"File loaded successfully | file_path={file_path} | "
            f"documents_count={len(file_content)} | "
            f"total_chars={sum(len(doc.page_content) for doc in file_content)}"
        )
        
        # Chunk the file content using configured chunk_size / overlap
        chunk_size = getattr(config, "chunk_size", 1000)
        chunk_overlap = getattr(config, "chunk_overlap", 200)
        logger.info(
            f"Starting chunking process with chunk_size={chunk_size}, "
            f"chunk_overlap={chunk_overlap}"
        )
        
        chunk_docs = self.process_file_content(
            file_content=file_content,
            document_id=filename_on_disk,
            chunk_size=chunk_size,
            overlap_size=chunk_overlap,
        )
        
        if not chunk_docs:
            logger.warning(
                f"No chunks generated for document {document_db_id} "
                f"(topic_id={topic.topic_id})"
            )
            return [], []
        
        logger.info(
            f"Chunking completed: {len(chunk_docs)} chunks created from document "
            f"{document_db_id}"
        )
        
        # Persist chunks into database
        logger.info(f"Preparing to persist {len(chunk_docs)} chunks to database")
        chunk_model = await ChunkModel.create_instance(db_client)
        chunk_entities = []
        
        from src.models.db_schemas.citatum.schemas.chunk import Chunk as ChunkSchema
        
        logger.debug("Building chunk entities from LangChain documents")
        for idx, lc_doc in enumerate(chunk_docs, start=1):
            meta = dict(lc_doc.metadata or {})
            
            # Derive page number / section from metadata if available
            page_number = meta.get("page") or meta.get("page_number")
            section = meta.get("section")
            
            # Build chunk metadata to store additional context
            chunk_metadata = {
                **meta,
                "chunk_order": idx,
                "chunk_page_number": page_number,
                "chunk_section": section,
                "document_id": document_db_id,
                "topic_id": topic.topic_id,
            }
            
            chunk_entity = ChunkSchema(
                chunk_text=lc_doc.page_content,
                chunk_metadata=chunk_metadata,
                chunk_order=idx,
                chunk_page_number=page_number,
                chunk_section=section,
                chunk_topic_id=topic.topic_id,
                chunk_document_id=document_db_id,
            )
            chunk_entities.append(chunk_entity)
            
            # Log progress for large documents (every 100 chunks)
            if idx % 100 == 0:
                logger.debug(f"Processed {idx}/{len(chunk_docs)} chunks")
        
        logger.info(f"Inserting {len(chunk_entities)} chunks into database")
        inserted_count = await chunk_model.insert_many_chunks(chunk_entities)
        logger.info(
            f"Successfully inserted {inserted_count} chunks for document {document_db_id} "
            f"(topic_id={topic.topic_id})"
        )
        
        # Reload chunks from DB to get their primary keys
        logger.debug(f"Reloading chunks from database to get primary keys")
        all_chunks = await chunk_model.get_document_chunks(
            document_id=document_db_id,
            page_no=1,
            page_size=max(inserted_count, 1_000_000),
        )
        chunk_ids = [c.chunk_id for c in all_chunks]
        
        logger.info(
            f"Chunking process completed successfully for document {document_db_id}: "
            f"{len(chunk_ids)} chunks stored (topic_id={topic.topic_id})"
        )
        
        return all_chunks, chunk_ids