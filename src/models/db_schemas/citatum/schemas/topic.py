from sqlalchemy import Column, String, Text, DateTime, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped
from typing import List, TYPE_CHECKING
from datetime import datetime

from src.models.db_schemas.citatum.citatum_base import CitatumBase

if TYPE_CHECKING:
    from .document import Document
    from .chunk import Chunk



class Topic(CitatumBase):
    """SQLAlchemy model for the topics table"""
    
    __tablename__ = "topics"
    
    # Primary key - UUID
    topic_id: str = Column(
        UUID(as_uuid=False),
        primary_key=True,
        nullable=False,
        server_default=func.uuid_generate_v4()
    )
    
    # Topic fields
    topic_name: str = Column(String, nullable=False, unique=True, index=True)
    topic_description: str | None = Column(Text, nullable=True)
    
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
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="topic",
        cascade="all, delete-orphan"
    )
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk",
        back_populates="topic",
        cascade="all, delete-orphan"
    )
