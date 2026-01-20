"""Shared route dependencies/helpers (avoid duplication across routes)."""

from typing import Any, Callable

from fastapi import HTTPException, Request, status

from src.models.TopicModel import TopicModel
from src.models.db_schemas.citatum.schemas.topic import Topic


def _require_app_state(request: Request, attr: str, missing_detail: str) -> Any:
    value = getattr(request.app.state, attr, None)
    if value is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=missing_detail,
        )
    return value


def get_db_client(request: Request) -> Callable:
    """Get database session factory from app state."""
    return _require_app_state(request, "db_client", "Database client not configured")


def get_vectordb_client(request: Request) -> Any:
    """Get vector database client from app state."""
    return _require_app_state(request, "vectordb_client", "Vector database client not configured")


def get_embedding_client(request: Request) -> Any:
    """Get embedding client from app state."""
    return _require_app_state(request, "embedding_client", "Embedding client not configured")


async def get_or_create_topic(db_client: Callable, topic_id: int) -> Topic:
    """Get or create Topic row for a numeric topic_id."""
    topic_model = await TopicModel.create_instance(db_client)
    return await topic_model.get_topic_or_create(f"topic_{topic_id}")

