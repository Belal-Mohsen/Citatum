"""Document API routes"""
import os
import time
import aiofiles
from typing import Optional, Any, Callable
from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException, status
from fastapi.responses import JSONResponse

from src.controllers.DocumentController import DocumentController
from src.controllers.TopicController import TopicController
from src.controllers.ProcessController import ProcessController
from src.controllers.EvidenceController import EvidenceController
from src.routes.dependencies import (
    get_db_client,
    get_vectordb_client,
    get_embedding_client,
    get_or_create_topic,
)
from src.models.DocumentModel import DocumentModel
from src.models.TopicModel import TopicModel
from src.models.db_schemas.citatum.schemas.document import Document
from src.models.db_schemas.citatum.schemas.topic import Topic
from src.utils.config import config
from src.utils.logger import get_logger
from src.utils.uuid_validator import validate_uuid

router = APIRouter(
    prefix="/api/v1/documents",
    tags=["api_v1", "documents"],
)

logger = get_logger(__name__)




@router.post("/upload/{topic_name}")
async def upload_document(
    topic_name: str,
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
    
    This endpoint handles the complete document upload workflow:
    1. File validation
    2. File saving to disk
    3. Document metadata extraction
    4. Document record creation in database
    5. Document chunking
    6. Embedding generation and vector DB indexing
    
    Args:
        topic_name: Topic name (used as identifier)
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
    start_time = time.time()
    file_id = None
    document_db_id = None
    
    try:
        # Log request start with context
        filename = file.filename or "unknown"
        content_type = file.content_type or "unknown"
        logger.info(
            f"Document upload request received | "
            f"topic_name={topic_name} | filename={filename} | "
            f"content_type={content_type} | client_ip={request.client.host if request.client else 'unknown'}"
        )
        
        # Step 1: Initialize clients
        logger.debug(f"Initializing database and vector DB clients for topic_name={topic_name}")
        db_client = get_db_client(request)
        vectordb_client = get_vectordb_client(request)
        embedding_client = get_embedding_client(request)
        logger.debug("All clients initialized successfully")
        
        # Step 2: Get or create topic
        topic_start = time.time()
        logger.info(f"Getting or creating topic | topic_name={topic_name}")
        topic = await get_or_create_topic(db_client, topic_name)
        topic_time = time.time() - topic_start
        logger.info(
            f"Topic ready | topic_id={topic.topic_id} | topic_name={topic.topic_name} | "
            f"duration={topic_time:.3f}s"
        )

        # Step 3: Validate file
        validation_start = time.time()
        logger.info(f"Validating uploaded file | filename={filename} | topic_name={topic_name}")
        doc_controller = DocumentController()
        is_valid, message = doc_controller.validate_uploaded_file(file)
        validation_time = time.time() - validation_start
        
        if not is_valid:
            logger.warning(
                f"File validation failed | filename={filename} | topic_name={topic_name} | "
                f"reason={message} | duration={validation_time:.3f}s"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        logger.info(
            f"File validation passed | filename={filename} | size={file.size or 'unknown'} bytes | "
            f"content_type={content_type} | duration={validation_time:.3f}s"
        )
        
        # Step 4: Extract metadata
        metadata_start = time.time()
        logger.debug(f"Extracting document metadata | filename={filename}")
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
        metadata_time = time.time() - metadata_start
        logger.info(
            f"Metadata extracted | filename={filename} | metadata_keys={list(metadata.keys())} | "
            f"duration={metadata_time:.3f}s"
        )
        
        # Step 5: Generate unique filepath
        filepath_start = time.time()
        logger.debug(f"Generating unique filepath | filename={filename} | topic_name={topic_name}")
        file_path, file_id = doc_controller.generate_unique_filepath(
            file.filename,
            topic_name
        )
        filepath_time = time.time() - filepath_start
        logger.info(
            f"Filepath generated | file_id={file_id} | file_path={file_path} | "
            f"duration={filepath_time:.3f}s"
        )
        
        # Step 6: Save file to disk
        save_start = time.time()
        logger.info(f"Saving file to disk | file_id={file_id} | file_path={file_path}")
        chunk_size = getattr(config, "file_default_chunk_size", 8192)
        bytes_written = 0
        chunks_written = 0
        
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(chunk_size):
                await f.write(chunk)
                bytes_written += len(chunk)
                chunks_written += 1
                # Log progress for large files (every 100 chunks)
                if chunks_written % 100 == 0:
                    logger.debug(
                        f"File save progress | file_id={file_id} | "
                        f"chunks={chunks_written} | bytes={bytes_written}"
                    )
        
        file_size = os.path.getsize(file_path)
        save_time = time.time() - save_start
        logger.info(
            f"File saved successfully | file_id={file_id} | file_size={file_size} bytes | "
            f"chunks_written={chunks_written} | duration={save_time:.3f}s | "
            f"throughput={file_size/save_time:.0f} bytes/s"
        )
        
        # Step 7: Determine document type
        content_type = file.content_type or ""
        if "pdf" in content_type.lower():
            document_type = "PDF"
        elif "text" in content_type.lower():
            document_type = "TXT"
        else:
            document_type = "PDF"  # Default
        logger.debug(f"Document type determined | file_id={file_id} | type={document_type}")
        
        # Step 8: Create document record in database
        db_create_start = time.time()
        logger.info(f"Creating document record in database | file_id={file_id} | topic_name={topic_name}")
        document_model = DocumentModel(db_client)
        
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
        
        created_document = await document_model.create_document(document)
        document_db_id = created_document.document_id
        db_create_time = time.time() - db_create_start
        logger.info(
            f"Document record created | document_db_id={document_db_id} | file_id={file_id} | "
            f"duration={db_create_time:.3f}s"
        )
        
        # Step 9: Chunk the document and store chunks in DB
        chunking_start = time.time()
        logger.info(
            f"Starting document chunking | document_db_id={document_db_id} | "
            f"file_id={file_id} | topic_name={topic_name} | file_size={file_size} bytes"
        )
        process_controller = ProcessController(topic_name)  # Use topic_name instead of topic_id
        all_chunks, chunk_ids = await process_controller.chunk_and_store_document(
            file_path=file_path,
            topic=topic,
            document_db_id=created_document.document_id,
            db_client=db_client,
        )
        chunking_time = time.time() - chunking_start
        chunks_count = len(chunk_ids) if chunk_ids else 0
        
        if chunks_count == 0:
            logger.warning(
                f"No chunks generated | document_db_id={document_db_id} | file_id={file_id} | "
                f"topic_name={topic_name} | duration={chunking_time:.3f}s"
            )
        else:
            logger.info(
                f"Document chunking completed | document_db_id={document_db_id} | "
                f"chunks_count={chunks_count} | duration={chunking_time:.3f}s | "
                f"avg_chunk_time={chunking_time/chunks_count:.3f}s/chunk"
            )
        
        # Step 10: Generate embeddings and index into vector DB
        indexing_start = time.time()
        if all_chunks and chunk_ids:
            logger.info(
                f"Starting vector DB indexing | document_db_id={document_db_id} | "
                f"chunks_count={chunks_count} | topic_name={topic_name}"
            )
            try:
                evidence_controller = EvidenceController(
                    vectordb_client=vectordb_client,
                    embedding_client=embedding_client,
                )
                await evidence_controller.index_into_vector_db(
                    topic=topic,
                    chunks=all_chunks,
                    chunks_ids=chunk_ids,
                    do_reset=False,
                )
                indexing_time = time.time() - indexing_start
                logger.info(
                    f"Vector DB indexing completed | document_db_id={document_db_id} | "
                    f"chunks_indexed={chunks_count} | topic_name={topic_name} | "
                    f"duration={indexing_time:.3f}s | "
                    f"avg_indexing_time={indexing_time/chunks_count:.3f}s/chunk"
                )
            except Exception as e:
                indexing_time = time.time() - indexing_start
                logger.error(
                    f"Vector DB indexing failed | document_db_id={document_db_id} | "
                    f"chunks_count={chunks_count} | topic_name={topic_name} | "
                    f"duration={indexing_time:.3f}s | error={str(e)}",
                    exc_info=True
                )
                # Don't fail the upload if indexing fails - document is already saved
        else:
            logger.warning(
                f"Skipping vector DB indexing | document_db_id={document_db_id} | "
                f"reason=no_chunks_generated | chunks_count={chunks_count}"
            )
        
        # Calculate total processing time
        total_time = time.time() - start_time
        
        # Log success summary with metrics
        logger.info(
            f"Document upload completed successfully | "
            f"file_id={file_id} | document_db_id={document_db_id} | topic_name={topic_name} | "
            f"file_size={file_size} bytes | chunks_count={chunks_count} | "
            f"total_duration={total_time:.3f}s | "
            f"breakdown: topic={topic_time:.3f}s, validation={validation_time:.3f}s, "
            f"metadata={metadata_time:.3f}s, filepath={filepath_time:.3f}s, "
            f"save={save_time:.3f}s, db_create={db_create_time:.3f}s, "
            f"chunking={chunking_time:.3f}s, indexing={indexing_time if all_chunks else 0:.3f}s"
        )
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "file_upload_success",
                "document_id": file_id,
                "document_db_id": created_document.document_id,
                "chunks_count": chunks_count,
                "processing_time_seconds": round(total_time, 3),
            }
        )
    
    except HTTPException as e:
        total_time = time.time() - start_time
        logger.warning(
            f"Document upload rejected | topic_name={topic_name} | "
            f"status_code={e.status_code} | detail={e.detail} | "
            f"duration={total_time:.3f}s"
        )
        raise
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"Document upload failed | topic_name={topic_name} | file_id={file_id or 'unknown'} | "
            f"document_db_id={document_db_id or 'unknown'} | duration={total_time:.3f}s | "
            f"error={str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
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
