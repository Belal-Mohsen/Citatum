"""Abstract base class for vector database providers"""
from abc import ABC, abstractmethod
from typing import Optional, List, Any


class VectorDBInterface(ABC):
    """
    Abstract base class for vector database providers.
    
    All vector database providers must implement these methods for
    collection management, vector storage, and similarity search.
    """
    
    @property
    @abstractmethod
    def default_vector_size(self) -> int:
        """Default vector dimension size for this provider"""
        pass
    
    @abstractmethod
    async def create_collection(
        self, 
        collection_name: str, 
        vector_size: int, 
        do_reset: bool = False
    ) -> bool:
        """
        Create a vector collection.
        
        Args:
            collection_name: Name of the collection
            vector_size: Dimension size of vectors
            do_reset: If True, delete existing collection before creating
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a vector collection.
        
        Args:
            collection_name: Name of the collection to delete
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def list_collections(self) -> List[str]:
        """
        List all collections in the vector database.
        
        Returns:
            List of collection names
        """
        pass
    
    @abstractmethod
    async def get_collection_info(self, collection_name: str) -> Any:
        """
        Get information about a collection.
        
        Args:
            collection_name: Name of the collection
        
        Returns:
            Collection information (provider-specific format)
        """
        pass
    
    @abstractmethod
    async def insert_many(
        self,
        collection_name: str,
        texts: List[str],
        metadata: List[dict],
        vectors: List[List[float]],
        record_ids: Optional[List[str]] = None
    ) -> bool:
        """
        Insert multiple vectors into a collection.
        
        Args:
            collection_name: Name of the collection
            texts: List of text strings
            metadata: List of metadata dictionaries
            vectors: List of embedding vectors
            record_ids: Optional list of record UUIDs (e.g., chunk_id as UUID string)
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def search_by_vector(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10
    ) -> List[dict]:
        """
        Search for similar vectors in a collection.
        
        Args:
            collection_name: Name of the collection
            query_vector: Query embedding vector
            limit: Maximum number of results
        
        Returns:
            List of result dictionaries with text, metadata, and score
        """
        pass
    
    @abstractmethod
    async def delete_by_ids(
        self,
        collection_name: str,
        record_ids: List[str]
    ) -> bool:
        """
        Delete records from a collection by their IDs.
        
        Args:
            collection_name: Name of the collection
            record_ids: List of record UUIDs (strings) to delete
        
        Returns:
            True if successful
        """
        pass
