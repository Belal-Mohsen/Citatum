from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped
from typing import TYPE_CHECKING, Any
from datetime import datetime

from src.models.db_schemas.citatum.citatum_base import CitatumBase

if TYPE_CHECKING:
    from .topic import Topic
    from .document import Document


class Citation(CitatumBase):
    """SQLAlchemy model for the citations table"""
    
    __tablename__ = "citations"
    
    # Primary key
    citation_id: int = Column(Integer, primary_key=True, autoincrement=True)
    
    # UUID
    citation_uuid: str = Column(
        UUID(as_uuid=False),
        unique=True,
        nullable=False,
        server_default=func.uuid_generate_v4(),
        index=True
    )
    
    # Citation fields
    citation_text: str = Column(Text, nullable=False)
    citation_metadata: dict[str, Any] | None = Column(JSONB, nullable=True)
    citation_order: int = Column(Integer, nullable=False)
    citation_page_number: int | None = Column(Integer, nullable=True)
    citation_section: str | None = Column(String, nullable=True)
    
    # Foreign keys
    citation_topic_id: int = Column(
        Integer,
        ForeignKey("topics.topic_id", ondelete="CASCADE"),
        nullable=False
    )
    citation_document_id: int = Column(
        Integer,
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False
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
        back_populates="citations"
    )
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="citations"
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_citation_topic_id", "citation_topic_id"),
        Index("ix_citation_document_id", "citation_document_id"),
        Index("ix_citation_page_number", "citation_page_number"),
    )
    
