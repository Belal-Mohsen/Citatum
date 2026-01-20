"""Evidence API routes"""
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse

from src.controllers.EvidenceController import EvidenceController
from src.routes.dependencies import (
    get_db_client,
    get_vectordb_client,
    get_embedding_client,
    get_or_create_topic,
)
from src.utils.logger import get_logger

router = APIRouter(
    prefix="/api/v1/evidence",
    tags=["api_v1", "evidence"],
)

logger = get_logger(__name__)


# Pydantic models for request/response
class PushRequest(BaseModel):
    """Request model for pushing evidence to vector database"""
    do_reset: Optional[int] = 0


class SearchRequest(BaseModel):
    """Request model for searching evidence"""
    text: str
    limit: Optional[int] = 5


@router.get("/index/info/{topic_id}")
async def get_evidence_collection_info(
    topic_id: int,
    request: Request,
):
    """
    Get evidence collection information for a topic.
    
    Args:
        topic_id: Topic identifier
        request: FastAPI request object
    
    Returns:
        JSON response with collection information
    """
    try:
        # Get clients from app state
        db_client = get_db_client(request)
        vectordb_client = get_vectordb_client(request)
        embedding_client = get_embedding_client(request)
        
        topic = await get_or_create_topic(db_client, topic_id)
        
        # Create EvidenceController instance
        evidence_controller = EvidenceController(vectordb_client, embedding_client)
        
        # Call get_evidence_collection_info
        collection_info = await evidence_controller.get_evidence_collection_info(topic)
        
        logger.info(f"Retrieved collection info for topic {topic_id}")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "vectordb_collection_retrieved",
                "collection_info": collection_info,
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting collection info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get collection info: {str(e)}"
        )


@router.post("/search/{topic_id}")
async def search_evidence(
    topic_id: int,
    search_request: SearchRequest,
    request: Request,
):
    """
    Search evidence collection for relevant chunks.
    
    Args:
        topic_id: Topic identifier
        search_request: Search request with text and limit
        request: FastAPI request object
    
    Returns:
        JSON response with search results
    """
    try:
        # Get clients from app state
        db_client = get_db_client(request)
        vectordb_client = get_vectordb_client(request)
        embedding_client = get_embedding_client(request)
        
        topic = await get_or_create_topic(db_client, topic_id)
        
        # Create EvidenceController
        evidence_controller = EvidenceController(vectordb_client, embedding_client)
        
        # Call search_evidence_collection
        results = await evidence_controller.search_evidence_collection(
            topic,
            search_request.text,
            search_request.limit
        )
        
        if results is False or not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No evidence found for the search query"
            )
        
        # Format results with full document metadata
        formatted_results = []
        for result in results:
            formatted_result = {
                "text": result.text,
                "metadata": result.metadata,
                "score": result.score,
            }
            formatted_results.append(formatted_result)
        
        logger.info(f"Search completed for topic {topic_id}: {len(formatted_results)} results")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "vectordb_search_success",
                "results": formatted_results,
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching evidence: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search evidence: {str(e)}"
        )


@router.post("/verify/{topic_id}")
async def verify_claim(
    topic_id: int,
    search_request: SearchRequest,
    request: Request,
):
    """
    Verify a claim by searching for relevant evidence chunks.
    
    Args:
        topic_id: Topic identifier
        search_request: Search request (text is used as claim)
        request: FastAPI request object
    
    Returns:
        JSON response with claim verification results
    """
    try:
        # Get clients from app state
        db_client = get_db_client(request)
        vectordb_client = get_vectordb_client(request)
        embedding_client = get_embedding_client(request)
        
        topic = await get_or_create_topic(db_client, topic_id)
        
        # Create EvidenceController
        evidence_controller = EvidenceController(vectordb_client, embedding_client)
        
        # Call verify_claim (use text as claim)
        claim, supporting_evidence, refuting_evidence = await evidence_controller.verify_claim(
            topic,
            search_request.text,
            search_request.limit
        )
        
        if claim is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No evidence found for the claim"
            )
        
        total_evidence_count = len(supporting_evidence) + len(refuting_evidence)
        
        logger.info(
            f"Claim verification completed for topic {topic_id}: "
            f"{len(supporting_evidence)} supporting, {len(refuting_evidence)} refuting"
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "evidence_verification_success",
                "claim": claim,
                "supporting_evidence": supporting_evidence,
                "refuting_evidence": refuting_evidence,
                "citation_format": "APA",  # Note: citation_format refers to academic citation style, not database model
                "total_evidence_count": total_evidence_count,
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying claim: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify claim: {str(e)}"
        )
