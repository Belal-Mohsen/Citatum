"""Evidence controller for vector database operations and evidence retrieval"""
import json
from typing import Union, List, Tuple, Optional, Any
from dataclasses import dataclass

from src.controllers.BaseController import BaseController
from src.models.db_schemas.citatum.schemas.topic import Topic
from src.models.db_schemas.citatum.schemas.chunk import Chunk


@dataclass
class RetrievedDocument:
    """Represents a retrieved document from vector search"""
    text: str
    metadata: dict
    score: float = 0.0


class EvidenceController(BaseController):
    """Controller for vector database operations and evidence retrieval"""
    
    def __init__(self, vectordb_client: Any, embedding_client: Any):
        """
        Initialize EvidenceController with vector database and embedding clients.
        
        Args:
            vectordb_client: Vector database client instance
            embedding_client: Embedding client instance
        """
        super().__init__()
        self.vectordb_client = vectordb_client
        self.embedding_client = embedding_client
    
    def create_collection_name(self, topic_id: Union[str, int]) -> str:
        """
        Generate collection name for vector database.
        
        Args:
            topic_id: Topic identifier (str or int)
        
        Returns:
            Collection name in format: "pgvector_{vector_size}_{topic_id}"
        """
        vector_size = self.vectordb_client.default_vector_size
        collection_name = f"pgvector_{vector_size}_{topic_id}"
        return collection_name.strip()
    
    async def reset_evidence_collection(self, topic: Topic) -> bool:
        """
        Reset (delete) evidence collection for a topic.
        
        Args:
            topic: Topic model instance
        
        Returns:
            True if successful
        """
        # Get collection name using topic_id
        collection_name = self.create_collection_name(topic.topic_id)
        
        # Delete collection
        await self.vectordb_client.delete_collection(collection_name)
        
        return True
    
    async def get_evidence_collection_info(self, topic: Topic) -> dict:
        """
        Get collection information for a topic.
        
        Args:
            topic: Topic model instance
        
        Returns:
            Dictionary with collection information (JSON-serializable)
        """
        # Get collection name
        collection_name = self.create_collection_name(topic.topic_id)
        
        # Get collection info from vector database
        collection_info = await self.vectordb_client.get_collection_info(collection_name)
        
        # Convert to JSON-serializable dict
        # Using json.loads(json.dumps(...)) to handle any non-serializable objects
        try:
            json_str = json.dumps(collection_info, default=lambda x: x.__dict__ if hasattr(x, '__dict__') else str(x))
            collection_dict = json.loads(json_str)
        except (TypeError, ValueError):
            # Fallback: convert to dict manually
            if hasattr(collection_info, '__dict__'):
                collection_dict = collection_info.__dict__
            else:
                collection_dict = {"info": str(collection_info)}
        
        return collection_dict
    
    async def index_into_vector_db(
        self,
        topic: Topic,
        chunks: List[Chunk],
        chunks_ids: List[int],
        do_reset: bool = False
    ) -> bool:
        """
        Index chunks into vector database.
        
        Args:
            topic: Topic model instance
            chunks: List of Chunk model instances
            chunks_ids: List of chunk IDs corresponding to chunks
            do_reset: Whether to reset collection before indexing (default: False)
        
        Returns:
            True if successful
        """
        # Get collection name
        collection_name = self.create_collection_name(topic.topic_id)
        
        # Extract texts from chunks
        texts = [c.chunk_text for c in chunks]
        
        # Extract metadata from chunks
        metadata = [c.chunk_metadata if c.chunk_metadata else {} for c in chunks]
        
        # Generate embeddings
        embeddings = self.embedding_client.embed_text(text=texts, document_type="document")
        
        if not embeddings or len(embeddings) == 0:
            raise ValueError("Failed to generate embeddings for chunks")
        
        # Get embedding size from first embedding
        embedding_size = len(embeddings[0]) if embeddings else self.vectordb_client.default_vector_size
        
        # Create collection
        await self.vectordb_client.create_collection(
            collection_name,
            embedding_size,
            do_reset
        )
        
        # Insert into vector database
        await self.vectordb_client.insert_many(
            collection_name,
            texts,
            metadata,
            embeddings,
            record_ids=chunks_ids
        )
        
        return True
    
    async def delete_chunks_from_vector_db(
        self,
        topic: Topic,
        chunk_ids: List[int]
    ) -> bool:
        """
        Delete chunks from vector database by their IDs.
        
        Args:
            topic: Topic model instance
            chunk_ids: List of chunk IDs to delete
        
        Returns:
            True if successful
        """
        if not chunk_ids:
            return True
        
        # Get collection name
        collection_name = self.create_collection_name(topic.topic_id)
        
        # Delete chunks by IDs from vector database
        # Assuming vectordb_client has a delete_by_ids method
        # If not, this will need to be implemented in the vectordb_client
        if hasattr(self.vectordb_client, 'delete_by_ids'):
            await self.vectordb_client.delete_by_ids(collection_name, chunk_ids)
        elif hasattr(self.vectordb_client, 'delete_many'):
            await self.vectordb_client.delete_many(collection_name, chunk_ids)
        else:
            # If no delete method exists, log warning but don't fail
            # Import logger here to avoid circular imports
            from src.utils.logger import get_logger
            logger = get_logger(__name__)
            logger.warning(f"Vector database client does not support deleting by IDs. Chunks {chunk_ids} may still exist in vector DB.")
        
        return True
    
    async def search_evidence_collection(
        self,
        topic: Topic,
        text: str,
        limit: int = 10
    ) -> Union[List[RetrievedDocument], bool]:
        """
        Search evidence collection using semantic search.
        
        Args:
            topic: Topic model instance
            text: Search query text
            limit: Maximum number of results to return (default: 10)
        
        Returns:
            List of RetrievedDocument objects or False if error
        """
        # Get collection name
        collection_name = self.create_collection_name(topic.topic_id)
        
        # Generate query embedding
        query_embeddings = self.embedding_client.embed_text(text=text, document_type="query")
        
        # Check if embedding is valid
        if not query_embeddings or len(query_embeddings) == 0:
            return False
        
        # Extract first vector from list if list
        if isinstance(query_embeddings, list):
            query_vector = query_embeddings[0] if len(query_embeddings) > 0 else None
        else:
            query_vector = query_embeddings
        
        if query_vector is None:
            return False
        
        # Search vector database
        try:
            results = await self.vectordb_client.search_by_vector(
                collection_name,
                query_vector,
                limit
            )
            
            # Convert results to RetrievedDocument objects
            retrieved_docs = []
            for result in results:
                if isinstance(result, dict):
                    retrieved_docs.append(RetrievedDocument(
                        text=result.get('text', ''),
                        metadata=result.get('metadata', {}),
                        score=result.get('score', 0.0)
                    ))
                elif hasattr(result, 'text') and hasattr(result, 'metadata'):
                    retrieved_docs.append(RetrievedDocument(
                        text=result.text,
                        metadata=result.metadata if hasattr(result.metadata, '__dict__') else {},
                        score=getattr(result, 'score', 0.0)
                    ))
            
            return retrieved_docs
        except Exception as e:
            print(f"Error searching evidence collection: {e}")
            return False
    
    async def verify_claim(
        self,
        topic: Topic,
        claim: str,
        limit: int = 10
    ) -> Tuple[Optional[str], List[dict], List[dict]]:
        """
        Verify a claim by searching for relevant evidence chunks.
        
        Args:
            topic: Topic model instance
            claim: Claim text to verify
            limit: Maximum number of results to return (default: 10)
        
        Returns:
            Tuple of (claim, supporting_evidence, refuting_evidence)
            - claim: The original claim text or None if no results
            - supporting_evidence: List of evidence dicts supporting the claim
            - refuting_evidence: List of evidence dicts refuting the claim (empty for now)
        
        Note:
            This method does NOT use LLM generation - only retrieval and formatting.
            Classification of supporting vs refuting evidence would require additional logic.
        """
        # Search for relevant chunks
        search_results = await self.search_evidence_collection(topic, claim, limit)
        
        # If no results, return empty
        if not search_results or search_results is False:
            return (None, [], [])
        
        # Process results into evidence format
        supporting_evidence = []
        refuting_evidence = []  # Currently empty - would need classification logic
        
        for result in search_results:
            if isinstance(result, RetrievedDocument):
                # Extract chunk_id from metadata
                chunk_id = result.metadata.get('chunk_id') or result.metadata.get('id')
                chunk_document_id = result.metadata.get('chunk_document_id') or result.metadata.get('document_id')
                
                # Format evidence dict
                evidence_dict = {
                    "chunk_text": result.text,
                    "chunk_id": chunk_id,
                    "document": result.metadata.get('document', {}),
                    "page_number": result.metadata.get('chunk_page_number') or result.metadata.get('page_number'),
                    "section": result.metadata.get('chunk_section') or result.metadata.get('section'),
                    "similarity_score": result.score
                }
                
                # For now, all evidence is considered supporting
                # In the future, this could be classified based on similarity score or other criteria
                if result.score > 0.5:  # Threshold for supporting evidence
                    supporting_evidence.append(evidence_dict)
                else:
                    refuting_evidence.append(evidence_dict)
        
        return (claim, supporting_evidence, refuting_evidence)
