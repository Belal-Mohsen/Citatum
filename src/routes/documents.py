"""Document API routes"""
import os
import aiofiles
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException, status
from fastapi.responses import JSONResponse

from src.controllers.DocumentController import DocumentController
from src.controllers.TopicController import TopicController
from src.controllers.EvidenceController import EvidenceController
from src.models.TopicModel import TopicModel
from src.models.DocumentModel import DocumentModel
from src.models.ChunkModel import ChunkModel
from src.models.db_schemas.citatum.schemas.document import Document
from src.models.db_schemas.citatum.schemas.topic import Topic
from src.utils.config import config
from src.utils.logger import get_logger

router = APIRouter(
    prefix="/api/v1/documents",
    tags=["api_v1", "documents"],
)

logger = get_logger(__name__)


def get_db_client(request: Request):
    db_client = getattr(request.app.state, "db_client", None)
    if db_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database client not configured"
        )
    return db_client


def get_vectordb_client(request: Request):
    """Get vector database client from app state"""
    vectordb_client = getattr(request.app.state, "vectordb_client", None)
    if vectordb_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Vector database client not configured"
        )
    return vectordb_client


def get_embedding_client(request: Request):
    """Get embedding client from app state"""
    embedding_client = getattr(request.app.state, "embedding_client", None)
    if embedding_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Embedding client not configured"
        )
    return embedding_client


@router.post("/upload/{topic_id}")
async def upload_document(
    topic_id: int,
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    doi: Optional[str] = Form(None),
    journal: Optional[str] = Form(None),
    publication_date: Optional[str] = Form(None),
):
    """
    Upload a document for a topic.
    
    Args:
        topic_id: Topic identifier
        file: Uploaded file
        title: Optional document title
        author: Optional document author
        doi: Optional Digital Object Identifier
        journal: Optional journal/conference name
        publication_date: Optional publication date
        request: FastAPI request object
    
    Returns:
        JSON response with upload status and document_id
    """
    try:
        # Get db_client from app state
        db_client = get_db_client(request)
        
        # Create TopicModel instance and get or create topic
        topic_model = await TopicModel.create_instance(db_client)
        topic = await topic_model.get_topic_or_create(f"topic_{topic_id}")
        
        # Validate file using DocumentController
        doc_controller = DocumentController()
        is_valid, message = doc_controller.validate_uploaded_file(file)
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        # Extract metadata using DocumentController
        form_data = {}
        if title:
            form_data["title"] = title
        if author:
            form_data["author"] = author
        if doi:
            form_data["doi"] = doi
        if journal:
            form_data["journal"] = journal
        if publication_date:
            form_data["publication_date"] = publication_date
        
        metadata = doc_controller.extract_document_metadata(file, form_data)
        
        # Generate filepath using DocumentController
        file_path, file_id = doc_controller.generate_unique_filepath(
            file.filename,
            topic_id
        )
        
        # Save file using aiofiles in chunks
        chunk_size = getattr(config, "file_default_chunk_size", 8192)
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(chunk_size):
                await f.write(chunk)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Determine document type from content_type
        content_type = file.content_type or ""
        if "pdf" in content_type.lower():
            document_type = "PDF"
        elif "text" in content_type.lower():
            document_type = "TXT"
        else:
            document_type = "PDF"  # Default
        
        # Create Document record with metadata using DocumentModel
        document_model = DocumentModel(db_client)
        
        # Create Document instance
        document = Document(
            document_type=document_type,
            document_name=file_id,
            document_size=file_size,
            document_title=metadata.get("title"),
            document_author=metadata.get("author"),
            document_doi=metadata.get("doi"),
            document_journal=metadata.get("journal"),
            document_topic_id=topic.topic_id,
            document_metadata=metadata if metadata else None,
        )
        
        # Save document to database
        created_document = await document_model.create_document(document)
        
        logger.info(f"Document uploaded successfully: {file_id} for topic {topic_id}")
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "file_upload_success",
                "document_id": file_id,
                "document_db_id": created_document.document_id,
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.get("/{document_id}")
async def get_document(
    document_id: int,
    request: Request,
):
    """
    Get document metadata by ID.
    
    Args:
        document_id: Document database ID
        request: FastAPI request object
    
    Returns:
        JSON response with document metadata
    """
    try:
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
        
        # Return document metadata as JSON
        return {
            "document_id": document.document_id,
            "document_uuid": str(document.document_uuid),
            "document_type": document.document_type,
            "document_name": document.document_name,
            "document_size": document.document_size,
            "document_title": document.document_title,
            "document_author": document.document_author,
            "document_doi": document.document_doi,
            "document_journal": document.document_journal,
            "document_publication_date": document.document_publication_date.isoformat() if document.document_publication_date else None,
            "document_metadata": document.document_metadata,
            "document_topic_id": document.document_topic_id,
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "updated_at": document.updated_at.isoformat() if document.updated_at else None,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document: {str(e)}"
        )


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
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
        document_id: Document database ID
        request: FastAPI request object
    
    Returns:
        JSON response with deletion status
    """
    try:
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
        logger.error(f"Error deleting document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )
