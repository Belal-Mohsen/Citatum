"""Document controller for document upload and validation"""
import os
import re
from typing import Union, Tuple, Optional, Any
from fastapi import UploadFile

from src.controllers.BaseController import BaseController
from src.controllers.TopicController import TopicController
from src.controllers.EvidenceController import EvidenceController
from src.models.DocumentModel import DocumentModel
from src.models.ChunkModel import ChunkModel
from src.models.TopicModel import TopicModel
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DocumentController(BaseController):
    """Controller for document upload and validation"""
    
    def __init__(self):
        """Initialize DocumentController with size scale for MB to bytes conversion"""
        super().__init__()
        self.size_scale = 1048576  # MB to bytes conversion
    
    def validate_uploaded_file(self, file: UploadFile) -> Tuple[bool, str]:
        """
        Validate uploaded file type and size.
        
        Args:
            file: FastAPI UploadFile object
        
        Returns:
            Tuple of (is_valid: bool, message: str)
            - (True, "file_validate_successfully") if valid
            - (False, error_message) if invalid
        """
        # Get allowed types from config (from environment variable FILE_ALLOWED_TYPES)
        allowed_types = self.app_settings.get_file_allowed_types()
        
        if file.content_type not in allowed_types:
            return (False, f"file_type_not_allowed: {file.content_type}. Allowed types: {', '.join(allowed_types)}")
        
        # Get max file size from config (from environment variable FILE_MAX_SIZE_MB)
        max_size_mb = self.app_settings.file_max_size_mb
        max_size_bytes = max_size_mb * self.size_scale
        
        if file.size and file.size > max_size_bytes:
            return (False, f"file_size_exceeded: {file.size} bytes. Maximum size: {max_size_mb} MB ({max_size_bytes} bytes)")
        
        return (True, "file_validate_successfully")
    
    def generate_unique_filepath(self, orig_file_name: str, topic_id: Union[str, int]) -> Tuple[str, str]:
        """
        Generate unique file path for uploaded document.
        
        Args:
            orig_file_name: Original filename from upload
            topic_id: Topic identifier (str or int)
        
        Returns:
            Tuple of (file_path: str, file_id: str)
            - file_path: Full path to the file
            - file_id: Unique file identifier in format {random_key}*{cleaned_filename}
        """
        # Get topic path using TopicController
        topic_controller = TopicController()
        topic_path = topic_controller.get_topic_path(topic_id)
        
        # Clean filename
        cleaned_filename = self.get_clean_file_name(orig_file_name)
        
        # Generate unique path
        max_attempts = 10
        for attempt in range(max_attempts):
            # Generate random key
            random_key = self.generate_random_string()
            
            # Create path: {topic_path}/{random_key}_{cleaned_filename}
            file_path = os.path.join(topic_path, f"{random_key}_{cleaned_filename}")
            
            # Check if path exists
            if not os.path.exists(file_path):
                # Path is unique, return it
                file_id = f"{random_key}*{cleaned_filename}"
                return (os.path.abspath(file_path), file_id)
        
        # If we couldn't generate a unique path after max attempts, raise error
        raise RuntimeError(f"Failed to generate unique filepath after {max_attempts} attempts")
    
    def get_clean_file_name(self, orig_file_name: str) -> str:
        """
        Clean filename by removing special characters and replacing spaces.
        
        Args:
            orig_file_name: Original filename
        
        Returns:
            Cleaned filename with special characters removed (except underscore and dot)
            and spaces replaced with underscores
        """
        # Remove special characters except underscore and dot
        # Keep alphanumeric, underscore, dot, and dash
        cleaned = re.sub(r'[^a-zA-Z0-9_\.\-]', '', orig_file_name)
        
        # Replace spaces with underscores (in case any remain)
        cleaned = cleaned.replace(' ', '_')
        
        # Strip whitespace
        cleaned = cleaned.strip()
        
        return cleaned
    
    def extract_document_metadata(self, file: UploadFile, form_data: dict = None) -> dict:
        """
        Extract document metadata from form data and/or PDF file.
        
        Args:
            file: FastAPI UploadFile object
            form_data: Optional dictionary with form data (title, author, doi, journal, publication_date)
        
        Returns:
            Dictionary with metadata fields (all optional):
            - title: Document title
            - author: Document author(s)
            - doi: Digital Object Identifier
            - journal: Journal/conference name
            - publication_date: Publication date
        """
        metadata = {}
        
        # Extract from form_data if provided
        if form_data:
            if 'title' in form_data:
                metadata['title'] = form_data['title']
            if 'author' in form_data:
                metadata['author'] = form_data['author']
            if 'doi' in form_data:
                metadata['doi'] = form_data['doi']
            if 'journal' in form_data:
                metadata['journal'] = form_data['journal']
            if 'publication_date' in form_data:
                metadata['publication_date'] = form_data['publication_date']
        
        # Try to extract metadata from PDF if file is PDF
        # Note: This is optional and can be implemented later with PyMuPDF
        # For now, we'll just return the metadata from form_data
        if file and hasattr(file, 'content_type') and file.content_type == "application/pdf":
            # TODO: Implement PDF metadata extraction using PyMuPDF
            # This would extract title, author, etc. from PDF metadata
            pass
        
        return metadata
    
    async def delete_document(
        self,
        document_id: int,
        db_client: Any,
        vectordb_client: Optional[Any] = None,
        embedding_client: Optional[Any] = None
    ) -> dict:
        """
        Delete a document and cascade delete all related chunks and embeddings.
        
        This method handles the complete deletion process:
        1. Get document and all its chunks
        2. Delete chunk embeddings from vector database
        3. Delete chunks from database
        4. Delete file from storage
        5. Delete document from database
        
        Args:
            document_id: Document database ID
            db_client: Database client (session factory)
            vectordb_client: Optional vector database client (required for embedding deletion)
            embedding_client: Optional embedding client (required for vector DB operations)
        
        Returns:
            Dictionary with deletion results:
            - deleted: bool - Whether document was deleted
            - deleted_chunks_count: int - Number of chunks deleted
            - deleted_embeddings_count: int - Number of embeddings deleted
        
        Raises:
            ValueError: If document not found
            Exception: If deletion fails at any step
        """
        # Initialize models
        document_model = DocumentModel(db_client)
        chunk_model = ChunkModel(db_client)
        
        # Get document from database
        document = await document_model.get_document_by_id(document_id)
        if document is None:
            raise ValueError(f"Document with ID {document_id} not found")
        
        # Get all chunks for this document (get all chunks without pagination limit)
        chunks = await chunk_model.get_document_chunks(document_id, page_no=1, page_size=100000)
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        deleted_embeddings_count = 0
        
        # Step 1: Delete chunk embeddings from vector database
        if vectordb_client and embedding_client and chunk_ids:
            try:
                # Get topic for vector database operations
                topic_model = TopicModel(db_client)
                topic = await topic_model.get_topic_by_id(document.document_topic_id)
                
                if topic:
                    evidence_controller = EvidenceController(vectordb_client, embedding_client)
                    await evidence_controller.delete_chunks_from_vector_db(topic, chunk_ids)
                    deleted_embeddings_count = len(chunk_ids)
                    logger.info(
                        f"Deleted {deleted_embeddings_count} chunk embeddings from vector database "
                        f"for document {document_id}"
                    )
                else:
                    logger.warning(
                        f"Topic {document.document_topic_id} not found, "
                        f"skipping vector database deletion for document {document_id}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to delete chunks from vector database for document {document_id}: {e}",
                    exc_info=True
                )
                # Continue with other deletions even if vector DB deletion fails
                # This ensures data consistency in the main database
        
        # Step 2: Delete chunks from database
        deleted_chunks_count = await chunk_model.delete_chunks_by_document_id(document_id)
        logger.info(f"Deleted {deleted_chunks_count} chunks from database for document {document_id}")
        
        # Step 3: Delete file from storage
        file_deleted = False
        document_name = document.document_name
        if "*" in document_name:
            random_key, cleaned_filename = document_name.split("*", 1)
            # Get topic path
            topic_controller = TopicController()
            topic_path = topic_controller.get_topic_path(document.document_topic_id)
            # Reconstruct file path: {topic_path}/{random_key}_{cleaned_filename}
            file_path = os.path.join(topic_path, f"{random_key}_{cleaned_filename}")
            
            # Delete file if it exists
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    file_deleted = True
                    logger.info(f"Deleted file from storage: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete file from storage {file_path}: {e}")
                    # Continue with database deletion even if file deletion fails
            else:
                logger.warning(f"File not found in storage: {file_path}")
        else:
            logger.warning(f"Could not parse document_name to reconstruct file path: {document_name}")
        
        # Step 4: Delete document from database
        deleted = await document_model.delete_document(document_id)
        if not deleted:
            raise RuntimeError(f"Failed to delete document {document_id} from database")
        
        logger.info(
            f"Successfully deleted document {document_id}: "
            f"{deleted_chunks_count} chunks, {deleted_embeddings_count} embeddings, "
            f"file_deleted={file_deleted}"
        )
        
        return {
            "deleted": True,
            "deleted_chunks_count": deleted_chunks_count,
            "deleted_embeddings_count": deleted_embeddings_count,
            "file_deleted": file_deleted
        }