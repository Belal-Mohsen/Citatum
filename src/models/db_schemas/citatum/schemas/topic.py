from sqlalchemy import Column, Integer, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped
from typing import List, TYPE_CHECKING
from datetime import datetime

from src.models.db_schemas.citatum.citatum_base import CitatumBase

if TYPE_CHECKING:
    from .document import Document
    from .citation import Citation



class Topic(CitatumBase):
    """SQLAlchemy model for the topics table"""
    
    __tablename__ = "topics"
    
    # Primary key
    topic_id: int = Column(Integer, primary_key=True, autoincrement=True)
    
    # UUID
    topic_uuid: str = Column(
        UUID(as_uuid=False),
        unique=True,
        nullable=False,
        server_default=func.uuid_generate_v4(),
        index=True
    )
    
    # Topic fields
    topic_name: str = Column(String, nullable=False)
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
    citations: Mapped[List["Citation"]] = relationship(
        "Citation",
        back_populates="topic",
        cascade="all, delete-orphan"
    )
