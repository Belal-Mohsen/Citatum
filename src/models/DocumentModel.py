"""Document data model for academic document management"""
from sqlalchemy import select, delete, func
from src.models.BaseDataModel import BaseDataModel
from src.models.db_schemas.citatum.schemas.document import Document


class DocumentModel(BaseDataModel):
    """Data model for document operations"""
    
    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)
        self.db_client = db_client
    
    @classmethod
    async def create_instance(cls, db_client: object) -> "DocumentModel":
        return cls(db_client)
    
    async def create_document(self, document: Document) -> Document:
        async with self.db_client() as session:
            session.add(document)
            await session.commit()
            await session.refresh(document)
            return document
    
    async def get_all_topic_documents(
        self, 
        topic_id: int, 
        document_type: str = "PDF",
        page: int = 1, 
        page_size: int = 10
    ) -> tuple[list[Document], int]:
        """
        Get paginated documents for a topic with total count.
        
        Args:
            topic_id: Topic ID to filter by
            document_type: Document type to filter by
            page: Page number (1-indexed)
            page_size: Number of items per page
        
        Returns:
            Tuple of (list of documents, total count)
        """
        async with self.db_client() as session:
            async with session.begin():
                # Get total count
                count_query = (
                    select(func.count(Document.document_id))
                    .where(Document.document_topic_id == topic_id)
                    .where(Document.document_type == document_type)
                )
                count_result = await session.execute(count_query)
                total_count = count_result.scalar_one()
                
                # Get paginated documents
                offset = (page - 1) * page_size
                stmt = (
                    select(Document)
                    .where(Document.document_topic_id == topic_id)
                    .where(Document.document_type == document_type)
                    .offset(offset)
                    .limit(page_size)
                )
                result = await session.execute(stmt)
                documents = list(result.scalars().all())
                
                return documents, total_count
    
    async def get_document_record(self, topic_id: int, document_name: str) -> Document | None:
        """
        Get specific document by topic_id and name.
        
        Args:
            topic_id: Topic ID to filter by
            document_name: Document name to filter by
        
        Returns:
            Document instance or None if not found
        """
        async with self.db_client() as session:
            stmt = (
                select(Document)
                .where(Document.document_topic_id == topic_id)
                .where(Document.document_name == document_name)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
    
    async def get_document_by_id(self, document_id: int) -> Document | None:
        """
        Get document by document_id.
        
        Args:
            document_id: Document ID to get
        
        Returns:
            Document instance or None if not found
        """
        async with self.db_client() as session:
            stmt = select(Document).where(Document.document_id == document_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
    
    async def insert_many_documents(self,documents: list[Document],batch_size: int = 100) -> int:
        """
        Batch insert documents, return count.
        
        Args:
            documents: List of Document instances to insert
            batch_size: Number of documents to insert per batch
        
        Returns:
            Number of documents inserted
        """
        async with self.db_client() as session:
            total_inserted = 0
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                session.add_all(batch)
                await session.commit()
                total_inserted += len(batch)
            return total_inserted
    
    async def delete_document(self, document_id: int) -> bool:
        """
        Delete document by document_id.
        
        Args:
            document_id: Document ID to delete
        
        Returns:
            True if document was deleted, False if not found
        """
        async with self.db_client() as session:
            stmt = delete(Document).where(Document.document_id == document_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
    
    async def delete_all_topic_documents(self, topic_id: int) -> int:
        """
        Delete all documents for a specific topic.
        
        Args:
            topic_id: Topic ID to delete documents for
        
        Returns:
            Number of documents deleted
        """
        async with self.db_client() as session:
            stmt = delete(Document).where(Document.document_topic_id == topic_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount