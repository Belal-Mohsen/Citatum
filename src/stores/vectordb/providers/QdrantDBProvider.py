"""Qdrant provider for vector database operations"""
import asyncio
from typing import List, Optional, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.http import models

from src.stores.vectordb.VectorDBInterface import VectorDBInterface
from src.utils.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class QdrantDBProvider(VectorDBInterface):
    """Qdrant vector database provider"""
    
    def __init__(self, config: Config):
        """
        Initialize Qdrant provider.
        
        Args:
            config: Application configuration with Qdrant connection settings
        """
        self.config = config
        self.client: Optional[QdrantClient] = None
        self._default_vector_size = getattr(config, 'embedding_dimension', 1536)
        
        # Get distance method from config (cosine, l2, inner_product)
        distance_method = getattr(config, 'vector_db_distance_method', 'cosine').lower()
        
        # Map distance method to Qdrant Distance enum
        distance_map = {
            'cosine': Distance.COSINE,
            'l2': Distance.EUCLID,
            'inner_product': Distance.DOT
        }
        
        if distance_method not in distance_map:
            logger.warning(
                f"Unknown distance method '{distance_method}', defaulting to 'cosine'"
            )
            distance_method = 'cosine'
        
        self.distance = distance_map[distance_method]
        
        # Get Qdrant connection settings
        qdrant_host = getattr(config, 'vector_db_host', 'localhost')
        qdrant_port = getattr(config, 'vector_db_port', 6333)
        qdrant_url = getattr(config, 'qdrant_url', None)
        qdrant_api_key = getattr(config, 'qdrant_api_key', None)
        
        # Initialize Qdrant client
        if qdrant_url:
            # Use URL (for cloud Qdrant)
            self.client = QdrantClient(
                url=qdrant_url,
                api_key=qdrant_api_key
            )
        else:
            # Use host/port (for local Qdrant)
            self.client = QdrantClient(
                host=qdrant_host,
                port=qdrant_port
            )
        
        logger.info(
            f"Initialized Qdrant client: {qdrant_url or f'{qdrant_host}:{qdrant_port}'} "
            f"with distance method: {distance_method}"
        )
    
    @property
    def default_vector_size(self) -> int:
        """Default vector dimension size"""
        return self._default_vector_size
    
    async def create_collection(
        self, 
        collection_name: str, 
        vector_size: int, 
        do_reset: bool = False
    ) -> bool:
        """
        Create a vector collection in Qdrant.
        
        Args:
            collection_name: Name of the collection
            vector_size: Dimension size of vectors
            do_reset: If True, delete existing collection before creating
        
        Returns:
            True if successful
        """
        try:
            # Delete collection if do_reset (run in thread pool to avoid blocking)
            if do_reset:
                try:
                    await asyncio.to_thread(self.client.delete_collection, collection_name)
                    logger.info(f"Deleted existing collection: {collection_name}")
                except Exception:
                    # Collection might not exist, ignore error
                    pass
            
            # Check if collection exists (run in thread pool)
            collections = await asyncio.to_thread(self.client.get_collections)
            collection_names = [c.name for c in collections.collections]
            
            if collection_name not in collection_names:
                # Create collection (run in thread pool)
                await asyncio.to_thread(
                    self.client.create_collection,
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=self.distance
                    )
                )
                logger.info(f"Created collection: {collection_name} with vector size {vector_size}")
            else:
                logger.info(f"Collection {collection_name} already exists")
            
            return True
        
        except Exception as e:
            logger.error(f"Error creating collection {collection_name}: {e}", exc_info=True)
            raise
    
    async def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a vector collection.
        
        Args:
            collection_name: Name of the collection to delete
        
        Returns:
            True if successful
        """
        try:
            await asyncio.to_thread(self.client.delete_collection, collection_name)
            logger.info(f"Deleted collection: {collection_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error deleting collection {collection_name}: {e}", exc_info=True)
            raise
    
    async def list_collections(self) -> List[str]:
        """
        List all collections in Qdrant.
        
        Returns:
            List of collection names
        """
        try:
            # Get all collections (run in thread pool to avoid blocking)
            collections = await asyncio.to_thread(self.client.get_collections)
            collection_names = [c.name for c in collections.collections]
            logger.debug(f"Found {len(collection_names)} collections in Qdrant")
            return collection_names
        
        except Exception as e:
            logger.error(f"Error listing collections: {e}", exc_info=True)
            raise
    
    async def get_collection_info(self, collection_name: str) -> dict:
        """
        Get information about a collection.
        
        Args:
            collection_name: Name of the collection
        
        Returns:
            Dictionary with collection information
        """
        try:
            collection_info = await asyncio.to_thread(self.client.get_collection, collection_name)
            
            info = {
                "collection_name": collection_name,
                "points_count": collection_info.points_count,
                "vectors_count": collection_info.vectors_count,
                "config": {
                    "vector_size": collection_info.config.params.vectors.size,
                    "distance": collection_info.config.params.vectors.distance.value
                },
                "provider": "qdrant"
            }
            
            return info
        
        except Exception as e:
            logger.error(f"Error getting collection info for {collection_name}: {e}", exc_info=True)
            raise
    
    async def insert_many(
        self,
        collection_name: str,
        texts: List[str],
        metadata: List[dict],
        vectors: List[List[float]],
        record_ids: Optional[List[int]] = None
    ) -> bool:
        """
        Insert multiple vectors into a collection.
        
        Args:
            collection_name: Name of the collection
            texts: List of text strings
            metadata: List of metadata dictionaries
            vectors: List of embedding vectors
            record_ids: List of chunk IDs (required, stored in metadata)
        
        Returns:
            True if successful
        """
        if record_ids is None or len(record_ids) != len(texts):
            raise ValueError("record_ids (chunk_ids) must be provided and match texts length")
        
        try:
            # Prepare points for insertion
            points = []
            for i, (text, meta, vector, chunk_id) in enumerate(zip(texts, metadata, vectors, record_ids)):
                # Ensure metadata includes chunk_id
                if meta is None:
                    meta = {}
                meta['chunk_id'] = chunk_id
                meta['text'] = text  # Store text in metadata for retrieval
                
                # Use chunk_id as point ID if available, otherwise use index
                point_id = chunk_id if chunk_id else i
                
                point = PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=meta
                )
                points.append(point)
            
            # Insert points (run in thread pool)
            await asyncio.to_thread(
                self.client.upsert,
                collection_name=collection_name,
                points=points
            )
            
            logger.info(f"Inserted {len(points)} vectors into {collection_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error inserting vectors into {collection_name}: {e}", exc_info=True)
            raise
    
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
            List of result dictionaries with text, metadata, score, and chunk_id
        """
        try:
            # Search in Qdrant (run in thread pool)
            search_results = await asyncio.to_thread(
                self.client.search,
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit
            )
            
            # Format results
            formatted_results = []
            for result in search_results:
                payload = result.payload or {}
                
                # Extract chunk_id from metadata
                chunk_id = payload.get('chunk_id')
                if chunk_id is None:
                    # Fallback: try to get from point ID if it's an integer
                    chunk_id = result.id if isinstance(result.id, int) else None
                
                # Extract text from metadata
                text = payload.get('text', '')
                
                result_dict = {
                    'chunk_id': chunk_id,
                    'text': text,
                    'metadata': payload,
                    'score': float(result.score)
                }
                formatted_results.append(result_dict)
            
            logger.debug(f"Found {len(formatted_results)} results in {collection_name}")
            return formatted_results
        
        except Exception as e:
            logger.error(f"Error searching {collection_name}: {e}", exc_info=True)
            raise
    
    async def delete_by_ids(
        self,
        collection_name: str,
        record_ids: List[int]
    ) -> bool:
        """
        Delete records from a collection by their chunk IDs.
        
        Args:
            collection_name: Name of the collection
            record_ids: List of chunk IDs to delete
        
        Returns:
            True if successful
        """
        try:
            # Qdrant allows filtering by payload
            # We need to delete points where chunk_id matches
            # Since Qdrant uses point IDs, we'll use the chunk_ids as point IDs
            # (assuming they were inserted with chunk_id as point ID)
            
            # Delete points by ID (assuming chunk_id was used as point ID)
            # Run in thread pool to avoid blocking
            await asyncio.to_thread(
                self.client.delete,
                collection_name=collection_name,
                points_selector=models.PointIdsList(
                    points=record_ids
                )
            )
            
            logger.info(f"Deleted {len(record_ids)} records from {collection_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error deleting records from {collection_name}: {e}", exc_info=True)
            raise
