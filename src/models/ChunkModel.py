"""Chunk data model for evidence chunk data access"""
from typing import Callable
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.BaseDataModel import BaseDataModel
from src.models.db_schemas.citatum.schemas.chunk import Chunk


class ChunkModel(BaseDataModel):
    """Data model for chunk operations"""
    
    def __init__(self, db_client: object):
        """
        Initialize ChunkModel with database client.
        
        Args:
            db_client: Callable that returns an AsyncSession
        """
        super().__init__(db_client)
    
    @classmethod
    async def create_instance(cls, db_client: object) -> "ChunkModel":
        """
        Async class method to create ChunkModel instance.
        
        Args:
            db_client: Callable that returns an AsyncSession
        
        Returns:
            ChunkModel instance
        """
        return cls(db_client)
    
    async def create_chunk(self, chunk: Chunk) -> Chunk:
        """
        Create single chunk, commit and refresh.
        
        Args:
            chunk: Chunk instance to create
        
        Returns:
            Created chunk with refreshed data
        """
        async with self.db_client() as session:
            session.add(chunk)
            await session.commit()
            await session.refresh(chunk)
            return chunk
    
    async def get_chunk(self, chunk_id: int) -> Chunk | None:
        """
        Get chunk by ID.
        
        Args:
            chunk_id: Chunk ID to get
        
        Returns:
            Chunk instance or None if not found
        """
        async with self.db_client() as session:
            stmt = select(Chunk).where(Chunk.chunk_id == chunk_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
    
    async def insert_many_chunks(
        self, 
        chunks: list[Chunk], 
        batch_size: int = 100
    ) -> int:
        """
        Batch insert chunks, return count.
        
        Args:
            chunks: List of Chunk instances to insert
            batch_size: Number of chunks to insert per batch
        
        Returns:
            Number of chunks inserted
        """
        async with self.db_client() as session:
            total_inserted = 0
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                session.add_all(batch)
                await session.commit()
                total_inserted += len(batch)
            return total_inserted
    
    async def delete_chunks_by_document_id(self, document_id: int) -> int:
        """
        Delete all chunks for a document, return row count.
        
        Args:
            document_id: Document ID to delete chunks for
        
        Returns:
            Number of chunks deleted
        """
        async with self.db_client() as session:
            stmt = delete(Chunk).where(Chunk.chunk_document_id == document_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount
    
    async def get_document_chunks(
        self, 
        document_id: int, 
        page_no: int = 1, 
        page_size: int = 50
    ) -> list[Chunk]:
        """
        Get paginated chunks for a document.
        
        Args:
            document_id: Document ID to filter by
            page_no: Page number (1-indexed)
            page_size: Number of items per page
        
        Returns:
            List of Chunk instances
        """
        async with self.db_client() as session:
            offset = (page_no - 1) * page_size
            stmt = (
                select(Chunk)
                .where(Chunk.chunk_document_id == document_id)
                .offset(offset)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
    
    async def get_total_chunks_count(self, document_id: int) -> int:
        """
        Get total chunk count for a document.
        
        Args:
            document_id: Document ID to count chunks for
        
        Returns:
            Total number of chunks
        """
        async with self.db_client() as session:
            stmt = (
                select(func.count(Chunk.chunk_id))
                .where(Chunk.chunk_document_id == document_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one()
