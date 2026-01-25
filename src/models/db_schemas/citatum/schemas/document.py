from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped
from typing import Any, List, TYPE_CHECKING
from datetime import datetime, date

from src.models.db_schemas.citatum.citatum_base import CitatumBase

if TYPE_CHECKING:
    from .topic import Topic
    from .chunk import Chunk


class Document(CitatumBase):
    """SQLAlchemy model for the documents table"""
    
    __tablename__ = "documents"
    
    # Primary key - UUID
    document_id: str = Column(
        UUID(as_uuid=False),
        primary_key=True,
        nullable=False,
        server_default=func.uuid_generate_v4()
    )
    
    # Document fields
    document_type: str = Column(String, nullable=False)
    document_name: str = Column(String, nullable=False)
    document_size: int = Column(Integer, nullable=False)
    document_title: str | None = Column(String, nullable=True)
    document_author: str | None = Column(String, nullable=True)
    document_publication_date: date | None = Column(Date, nullable=True)
    document_doi: str | None = Column(String, nullable=True)
    document_journal: str | None = Column(String, nullable=True)
    document_metadata: dict[str, Any] | None = Column(JSONB, nullable=True)
    
    # Foreign key - references topic UUID
    document_topic_id: str = Column(
        UUID(as_uuid=False),
        ForeignKey("topics.topic_id", ondelete="CASCADE"),
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
        back_populates="documents"
    )
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_document_topic_id", "document_topic_id"),
        Index("ix_document_type", "document_type"),
        Index("ix_document_doi", "document_doi"),
        Index("ix_document_name", "document_name"),
    )
    
