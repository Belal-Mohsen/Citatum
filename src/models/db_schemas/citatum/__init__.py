# Citatum database schema package

# Expose base and models for easier imports
from src.models.db_schemas.citatum.citatum_base import CitatumBase
from src.models.db_schemas.citatum.schemas import Topic, Document, Chunk

__all__ = ["CitatumBase", "Topic", "Document", "Chunk"]
