"""Document API routes"""
import base64
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException, status
from fastapi.responses import JSONResponse

from src.controllers.DocumentController import DocumentController
from src.routes.dependencies import (
    get_db_client,
    get_vectordb_client,
    get_embedding_client,
)
from src.models.DocumentModel import DocumentModel
from src.models.TopicModel import TopicModel
from src.utils.config import config
from src.utils.logger import get_logger
from src.utils.uuid_validator import validate_uuid
from src.tasks.document_tasks import document_upload_and_process
router = APIRouter(
    prefix="/api/v1/documents",
    tags=["api_v1", "documents"],
)

logger = get_logger(__name__)




@router.post("/upload/{topic_name}")
async def upload_document(
    topic_name: str,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    doi: Optional[str] = Form(None),
    journal: Optional[str] = Form(None),
    publication_date: Optional[str] = Form(None),
):
    """
    Upload a document for a topic.
    
    This endpoint accepts a file upload and queues it for processing via Celery.
    The actual processing (validation, chunking, embedding, indexing) happens
    asynchronously in a background task.
    
    Args:
        topic_name: Topic name (used as identifier)
        file: Uploaded file
        title: Optional document title
        author: Optional document author
        doi: Optional Digital Object Identifier
        journal: Optional journal/conference name
        publication_date: Optional publication date
    
    Returns:
        JSON response with upload status, filename, and task_id.
        Note: Use task_id to poll for task completion and retrieve the actual
        document_db_id (UUID) needed for GET /documents/{document_id} requests.
    """
    filename = file.filename or "unknown"
    content_type = file.content_type or "application/octet-stream"
    
    try:
        # Validate file size before reading into memory
        # This prevents memory issues with very large files
        max_size_mb = config.file_max_size_mb
        max_size_bytes = max_size_mb * 1048576  # MB to bytes
        
        if file.size is not None and file.size > max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"file_size_exceeded: {file.size} bytes. Maximum size: {max_size_mb} MB ({max_size_bytes} bytes)"
            )
        
        # Validate file type before processing
        allowed_types = config.get_file_allowed_types()
        if content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"file_type_not_allowed: {content_type}. Allowed types: {', '.join(allowed_types)}"
            )
        
        # Read file content into memory (required for Celery serialization)
        # Note: For very large files, consider streaming to disk instead
        file_content = await file.read()
        
        # Verify actual file size matches reported size (if available)
        actual_size = len(file_content)
        if file.size is not None and actual_size != file.size:
            logger.warning(
                f"File size mismatch | filename={filename} | "
                f"reported={file.size} | actual={actual_size}"
            )
        
        # Double-check size after reading (in case file.size was None)
        if actual_size > max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"file_size_exceeded: {actual_size} bytes. Maximum size: {max_size_mb} MB ({max_size_bytes} bytes)"
            )
        
        # Encode file content as base64 for JSON serialization
        # Celery uses JSON serializer which cannot handle raw bytes
        file_content_b64 = base64.b64encode(file_content).decode('utf-8')
        
        # Queue the task with serializable parameters
        task = document_upload_and_process.delay(
            topic_name=topic_name,
            file_content_b64=file_content_b64,
            filename=filename,
            content_type=content_type,
            title=title,
            author=author,
            doi=doi,
            journal=journal,
            publication_date=publication_date,
        )

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "message": "file_upload_accepted",
                "filename": filename,
                "task_id": task.id,
                "note": "Use task_id to check task status and retrieve document_db_id (UUID) for document retrieval"
            }
        )
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
    except OSError as e:
        # File read errors
        logger.error(f"Error reading file {filename}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {str(e)}"
        )
    except Exception as e:
        # Celery queue errors or other unexpected errors
        logger.error(f"Error queuing document upload task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue document upload: {str(e)}"
        )




@router.get("/{document_id}")
async def get_document(
    document_id: str,
    request: Request,
):
    """
    Get document metadata by UUID.
    
    Args:
        document_id: Document UUID
        request: FastAPI request object
    
    Returns:
        JSON response with document metadata
    """
    try:
        # Validate UUID format before querying database
        document_id = validate_uuid(document_id, "document_id")
        
        # Get db_client from app state
        db_client = get_db_client(request)
        
        # Get document using DocumentModel
        document_model = DocumentModel(db_client)
        document = await document_model.get_document_by_id(document_id)
        
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found"
            )
        
        # Get topic for response
        topic_model = await TopicModel.create_instance(db_client)
        topic = await topic_model.get_topic_by_id(document.document_topic_id)
        topic_name = topic.topic_name if topic else None
        
        # Return document metadata as JSON
        return {
            "document_id": document.document_id,
            "document_type": document.document_type,
            "document_name": document.document_name,
            "document_size": document.document_size,
            "document_title": document.document_title,
            "document_author": document.document_author,
            "document_doi": document.document_doi,
            "document_journal": document.document_journal,
            "document_publication_date": document.document_publication_date.isoformat() if document.document_publication_date else None,
            "document_metadata": document.document_metadata,
            "topic_id": document.document_topic_id,
            "topic_name": topic_name,
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "updated_at": document.updated_at.isoformat() if document.updated_at else None,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        # Check if it's a UUID validation error from the database
        error_str = str(e).lower()
        if "invalid uuid" in error_str or "invalid input for query argument" in error_str:
            logger.warning(f"Invalid UUID format provided: {document_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid document_id format: '{document_id}'. Expected a valid UUID (e.g., '550e8400-e29b-41d4-a716-446655440000')"
            )
        logger.error(f"Error getting document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document: {str(e)}"
        )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    request: Request,
):
    """
    Delete a document and all related chunks from database, vector database, and storage.
    
    Uses DocumentController.delete_document() which handles cascade deletion:
    1. Deletes chunk embeddings from vector database
    2. Deletes chunks from database
    3. Deletes file from storage
    4. Deletes document from database
    
    Args:
        document_id: Document UUID
        request: FastAPI request object
    
    Returns:
        JSON response with deletion status
    """
    try:
        # Validate UUID format before querying database
        document_id = validate_uuid(document_id, "document_id")
        
        # Get clients from app state
        db_client = get_db_client(request)
        vectordb_client = get_vectordb_client(request)
        embedding_client = get_embedding_client(request)
        
        # Use DocumentController to handle cascade deletion
        doc_controller = DocumentController()
        result = await doc_controller.delete_document(
            document_id=document_id,
            db_client=db_client,
            vectordb_client=vectordb_client,
            embedding_client=embedding_client
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "document_deleted_successfully",
                "document_id": document_id,
                "deleted_chunks_count": result["deleted_chunks_count"],
                "deleted_embeddings_count": result["deleted_embeddings_count"],
                "file_deleted": result["file_deleted"],
            }
        )
    
    except ValueError as e:
        # Document not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        # Check if it's a UUID validation error from the database
        error_str = str(e).lower()
        if "invalid uuid" in error_str or "invalid input for query argument" in error_str:
            logger.warning(f"Invalid UUID format provided: {document_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid document_id format: '{document_id}'. Expected a valid UUID (e.g., '550e8400-e29b-41d4-a716-446655440000')"
            )
        logger.error(f"Error deleting document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )
