"""Celery tasks for document processing"""
import os
import time
import asyncio
import aiofiles
import base64
from typing import Optional, Dict, Any
from celery import Task
from src.core.celery_app import celery_app
from src.utils.config import config
from src.utils.logger import get_logger
from src.utils.database import create_db_session_factory
from src.stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from src.stores.llm.LLMProviderFactory import LLMProviderFactory
from src.controllers.ProcessController import ProcessController
from src.controllers.EvidenceController import EvidenceController
from src.controllers.DocumentController import DocumentController
from src.models.DocumentModel import DocumentModel
from src.models.db_schemas.citatum.schemas.document import Document
from src.models.TopicModel import TopicModel
from src.routes.dependencies import get_or_create_topic
from src.models.db_schemas.citatum.schemas.topic import Topic

logger = get_logger(__name__)


@celery_app.task(
    name="tasks.document_tasks.document_upload_and_process", 
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60})
def document_upload_and_process(
    self: Task,
    topic_name: str,
    file_content_b64: str,
    filename: str,
    content_type: str,
    title: Optional[str] = None,
    author: Optional[str] = None,
    doi: Optional[str] = None,
    journal: Optional[str] = None,
    publication_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Celery task to upload and process a document.
    
    Args:
        self: Celery task instance
        topic_name: Topic name
        file_content_b64: File content as base64-encoded string (for JSON serialization)
        filename: Original filename
        content_type: MIME type of the file
        title: Optional document title
        author: Optional document author
        doi: Optional Digital Object Identifier
        journal: Optional journal/conference name
        publication_date: Optional publication date
    
    Returns:
        Dictionary with processing results
    """
    try:
        # Decode base64-encoded file content back to bytes
        file_content = base64.b64decode(file_content_b64.encode('utf-8'))
        
        # Run async processing
        result = asyncio.run(
            _process_document_async(
                topic_name=topic_name,
                file_content=file_content,
                filename=filename,
                content_type=content_type,
                title=title,
                author=author,
                doi=doi,
                journal=journal,
                publication_date=publication_date,
            )
        )
        
        logger.info(
            f"Document processing completed successfully: {filename}, "
            f"document_db_id: {result.get('document_db_id')}, "
            f"chunks_count: {result.get('chunks_count', 0)}"
        )
        
        return result
    
    except Exception as e:
        logger.error(
            f"Error processing document {filename} in Celery task: {e}",
            exc_info=True
        )
        # Update task state
        self.update_state(
            state="FAILURE",
            meta={"error": str(e), "filename": filename, "topic_name": topic_name}
        )
        raise


async def _process_document_async(
    topic_name: str,
    file_content: bytes,
    filename: str,
    content_type: str,
    title: Optional[str] = None,
    author: Optional[str] = None,
    doi: Optional[str] = None,
    journal: Optional[str] = None,
    publication_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Async function to process document upload.
    
    Args:
        topic_name: Topic name
        file_content: File content as bytes
        filename: Original filename
        content_type: MIME type of the file
        title: Optional document title
        author: Optional document author
        doi: Optional Digital Object Identifier
        journal: Optional journal/conference name
        publication_date: Optional publication date
    
    Returns:
        Dictionary with processing results
    
    Raises:
        ValueError: If file validation fails or client creation fails
        Exception: For other processing errors
    """
    start_time = time.time()
    file_id = None
    document_db_id = None
    vectordb_client = None
    indexing_time = 0.0
    
    try:
        # Log request start with context
        logger.info(
            f"Document upload request received | "
            f"topic_name={topic_name} | filename={filename} | "
            f"content_type={content_type}"
        )
        
        # Step 1: Initialize clients
        logger.debug(f"Initializing database and vector DB clients for topic_name={topic_name}")
        # Create database session factory (callable that returns AsyncSession)
        # Note: Models expect a factory, not a session instance
        db_client = create_db_session_factory(config)
        
        vectordb_factory = VectorDBProviderFactory(config)
        vectordb_client = vectordb_factory.create(config.vector_db_type.upper())
        if vectordb_client is None:
            raise ValueError(
                f"Failed to create vector database client for provider: {config.vector_db_type}"
            )
        
        llm_factory = LLMProviderFactory(config)
        embedding_client = llm_factory.create(config.llm_provider.upper())
        if embedding_client is None:
            raise ValueError(
                f"Failed to create embedding client for provider: {config.llm_provider}"
            )
        
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
        
        # Create a mock UploadFile-like object for validation
        # We need to validate file size and type
        file_size = len(file_content)
        max_size_mb = config.file_max_size_mb
        max_size_bytes = max_size_mb * 1048576  # MB to bytes
        
        # Validate file size
        if file_size > max_size_bytes:
            raise ValueError(
                f"file_size_exceeded: {file_size} bytes. Maximum size: {max_size_mb} MB ({max_size_bytes} bytes)"
            )
        
        # Validate file type
        allowed_types = config.get_file_allowed_types()
        if content_type not in allowed_types:
            raise ValueError(
                f"file_type_not_allowed: {content_type}. Allowed types: {', '.join(allowed_types)}"
            )
        
        validation_time = time.time() - validation_start
        logger.info(
            f"File validation passed | filename={filename} | size={file_size} bytes | "
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
        
        # Create a simple dict for metadata extraction
        metadata = form_data.copy()
        metadata["filename"] = filename
        metadata["content_type"] = content_type
        metadata_time = time.time() - metadata_start
        logger.info(
            f"Metadata extracted | filename={filename} | metadata_keys={list(metadata.keys())} | "
            f"duration={metadata_time:.3f}s"
        )
        
        # Step 5: Generate unique filepath
        filepath_start = time.time()
        logger.debug(f"Generating unique filepath | filename={filename} | topic_name={topic_name}")
        file_path, file_id = doc_controller.generate_unique_filepath(
            filename,
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
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save file content to disk
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_content)
        
        save_time = time.time() - save_start
        logger.info(
            f"File saved successfully | file_id={file_id} | file_size={file_size} bytes | "
            f"duration={save_time:.3f}s | "
            f"throughput={file_size/save_time:.0f} bytes/s"
        )
        
        # Step 7: Determine document type
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
        process_controller = ProcessController(topic_name)
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
                # Continue execution to return success response
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
            f"chunking={chunking_time:.3f}s, indexing={indexing_time:.3f}s"
        )
        return {
            "success": True,
            "message": "file_upload_success",
            "document_id": file_id,
            "document_db_id": created_document.document_id,
            "chunks_count": chunks_count,
            "processing_time_seconds": round(total_time, 3),
        }
        
    except ValueError as e:
        total_time = time.time() - start_time
        logger.warning(
            f"Document upload rejected | topic_name={topic_name} | "
            f"filename={filename} | detail={str(e)} | "
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
        raise
    finally:
        # Cleanup vector database connection if needed
        if vectordb_client and hasattr(vectordb_client, 'close'):
            try:
                await vectordb_client.close()
            except Exception as e:
                logger.warning(f"Error closing vector database client: {e}")
