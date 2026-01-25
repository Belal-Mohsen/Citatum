from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped
from typing import TYPE_CHECKING, Any
from datetime import datetime

from src.models.db_schemas.citatum.citatum_base import CitatumBase

if TYPE_CHECKING:
    from .topic import Topic
    from .document import Document


class Chunk(CitatumBase):
    """SQLAlchemy model for the chunks table"""
    
    __tablename__ = "chunks"
    
    # Primary key - UUID
    chunk_id: str = Column(
        UUID(as_uuid=False),
        primary_key=True,
        nullable=False,
        server_default=func.uuid_generate_v4()
    )
    
    # Chunk fields
    chunk_text: str = Column(Text, nullable=False)
    chunk_metadata: dict[str, Any] | None = Column(JSONB, nullable=True)
    chunk_order: int = Column(Integer, nullable=False)
    chunk_page_number: int | None = Column(Integer, nullable=True)
    chunk_section: str | None = Column(String, nullable=True)
    
    # Foreign keys - references UUIDs
    chunk_topic_id: str = Column(
        UUID(as_uuid=False),
        ForeignKey("topics.topic_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    chunk_document_id: str = Column(
        UUID(as_uuid=False),
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Timestamps
    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at: datetime | None = Column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now()
    )
    
    # Relationships
    topic: Mapped["Topic"] = relationship(
        "Topic",
        back_populates="chunks"
    )
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks"
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_chunk_topic_id", "chunk_topic_id"),
        Index("ix_chunk_document_id", "chunk_document_id"),
        Index("ix_chunk_page_number", "chunk_page_number"),
        Index("ix_chunk_order", "chunk_order"),
    )
    
