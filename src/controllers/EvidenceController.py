"""Evidence controller for vector database operations and evidence retrieval"""
import json
import time
from typing import Union, List, Tuple, Optional, Any
from dataclasses import dataclass

from src.controllers.BaseController import BaseController
from src.models.db_schemas.citatum.schemas.topic import Topic
from src.models.db_schemas.citatum.schemas.chunk import Chunk
from src.utils.logger import get_logger

logger = get_logger(__name__)


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
    
    def create_collection_name(self, topic_name: str) -> str:
        """
        Generate collection name for vector database.
        
        Args:
            topic_name: Topic name (used in collection name)
        
        Returns:
            Collection name in format: "pgvector_{vector_size}_{sanitized_topic_name}"
        """
        vector_size = self.vectordb_client.default_vector_size
        # Sanitize topic_name for use in collection name (replace special chars)
        safe_topic_name = topic_name.replace("/", "_").replace("\\", "_").replace("..", "_").replace(" ", "_")
        collection_name = f"pgvector_{vector_size}_{safe_topic_name}"
        return collection_name.strip()
    
    async def reset_evidence_collection(self, topic: Topic) -> bool:
        """
        Reset (delete) evidence collection for a topic.
        
        Args:
            topic: Topic model instance
        
        Returns:
            True if successful
        """
        # Get collection name using topic_name
        collection_name = self.create_collection_name(topic.topic_name)
        
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
        # Get collection name (use topic_name to match how collections are created)
        collection_name = self.create_collection_name(topic.topic_name)
        logger.info(
            f"Retrieving collection info | collection={collection_name} | "
            f"topic={topic.topic_name}"
        )
        
        info_start = time.time()
        try:
            # Get collection info from vector database
            collection_info = await self.vectordb_client.get_collection_info(collection_name)
            info_time = time.time() - info_start
            
            exists = collection_info.get('exists', False)
            row_count = collection_info.get('row_count', 0)
            
            logger.info(
                f"Collection info retrieved | collection={collection_name} | "
                f"topic={topic.topic_name} | exists={exists} | row_count={row_count} | "
                f"duration={info_time:.3f}s"
            )
        except Exception as e:
            info_time = time.time() - info_start
            logger.error(
                f"Error retrieving collection info | collection={collection_name} | "
                f"topic={topic.topic_name} | duration={info_time:.3f}s | error={str(e)}",
                exc_info=True
            )
            raise
        
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
        chunks_ids: List[str],
        do_reset: bool = False
    ) -> bool:
        """
        Index chunks into vector database.
        
        Args:
            topic: Topic model instance
            chunks: List of Chunk model instances
            chunks_ids: List of chunk UUIDs (strings) corresponding to chunks
            do_reset: Whether to reset collection before indexing (default: False)
        
        Returns:
            True if successful
        """
        start_time = time.time()
        logger.info(
            f"Starting embedding and indexing process | topic={topic.topic_name} | "
            f"chunks_count={len(chunks)} | chunks_ids_count={len(chunks_ids)} | "
            f"do_reset={do_reset}"
        )
        
        # Get collection name using topic_name
        collection_name = self.create_collection_name(topic.topic_name)
        logger.debug(f"Collection name: {collection_name}")
        
        # Extract texts from chunks
        logger.debug("Extracting texts from chunks")
        texts = [c.chunk_text for c in chunks]
        total_text_length = sum(len(text) for text in texts)
        logger.debug(
            f"Extracted {len(texts)} text(s), total length: {total_text_length} characters"
        )
        
        # Extract metadata from chunks and ensure document_id is included
        logger.debug("Extracting metadata from chunks")
        metadata = []
        for c in chunks:
            meta = c.chunk_metadata.copy() if c.chunk_metadata else {}
            # Ensure document_id is in metadata (from chunk_document_id if not already present)
            if 'document_id' not in meta and hasattr(c, 'chunk_document_id'):
                meta['document_id'] = c.chunk_document_id
            # Ensure topic_id is in metadata
            if 'topic_id' not in meta and hasattr(c, 'chunk_topic_id'):
                meta['topic_id'] = c.chunk_topic_id
            metadata.append(meta)
        
        # Generate embeddings
        embedding_start = time.time()
        logger.info(
            f"Generating embeddings | chunks_count={len(texts)} | "
            f"model={self.embedding_client.embedding_model_id} | "
            f"embedding_size={self.embedding_client.embedding_size} | "
            f"topic={topic.topic_name} | collection={collection_name}"
        )
        
        try:
            embeddings = self.embedding_client.embed_text(text=texts, document_type="document")
            embedding_time = time.time() - embedding_start
            
            if not embeddings or len(embeddings) == 0:
                logger.error(
                    f"Embedding generation failed: empty result | "
                    f"chunks_count={len(texts)} | topic={topic.topic_name} | "
                    f"duration={embedding_time:.3f}s"
                )
                raise ValueError("Failed to generate embeddings for chunks")

            if len(embeddings) != len(texts):
                logger.error(
                    f"Embedding count mismatch | expected={len(texts)} | "
                    f"got={len(embeddings)} | topic={topic.topic_name} | "
                    f"duration={embedding_time:.3f}s"
                )
                raise ValueError(
                    f"Embedding client returned {len(embeddings)} embeddings for "
                    f"{len(texts)} texts"
                )
            
            # Log embedding dimension validation
            embedding_dim = len(embeddings[0]) if embeddings else 0
            logger.info(
                f"Embeddings generated successfully | chunks_count={len(texts)} | "
                f"embeddings_count={len(embeddings)} | embedding_dim={embedding_dim} | "
                f"topic={topic.topic_name} | duration={embedding_time:.3f}s | "
                f"avg_time={embedding_time/len(texts):.3f}s/chunk"
            )
        except Exception as e:
            embedding_time = time.time() - embedding_start
            logger.error(
                f"Error generating embeddings | chunks_count={len(texts)} | "
                f"topic={topic.topic_name} | duration={embedding_time:.3f}s | "
                f"error={str(e)}",
                exc_info=True
            )
            raise
        
        # Get embedding size from first embedding
        embedding_size = len(embeddings[0]) if embeddings else self.vectordb_client.default_vector_size
        logger.debug(f"Embedding dimension: {embedding_size}")
        
        # Create collection
        collection_start = time.time()
        logger.info(
            f"Creating/updating vector database collection | collection={collection_name} | "
            f"dimension={embedding_size} | do_reset={do_reset} | topic={topic.topic_name}"
        )
        try:
            await self.vectordb_client.create_collection(
                collection_name,
                embedding_size,
                do_reset
            )
            collection_time = time.time() - collection_start
            logger.info(
                f"Collection ready for indexing | collection={collection_name} | "
                f"dimension={embedding_size} | topic={topic.topic_name} | "
                f"duration={collection_time:.3f}s"
            )
        except Exception as e:
            logger.error(
                f"Error creating collection {collection_name}: {e}",
                exc_info=True
            )
            raise
        
        # Insert into vector database
        insert_start = time.time()
        logger.info(
            f"Inserting vectors into collection | collection={collection_name} | "
            f"vectors_count={len(chunks_ids)} | embedding_dim={embedding_size} | "
            f"topic={topic.topic_name}"
        )
        try:
            await self.vectordb_client.insert_many(
                collection_name,
                texts,
                metadata,
                embeddings,
                record_ids=chunks_ids
            )
            insert_time = time.time() - insert_start
            logger.info(
                f"Vectors inserted successfully | collection={collection_name} | "
                f"vectors_count={len(chunks_ids)} | topic={topic.topic_name} | "
                f"duration={insert_time:.3f}s | avg_time={insert_time/len(chunks_ids):.3f}s/vector"
            )
        except Exception as e:
            insert_time = time.time() - insert_start
            logger.error(
                f"Error inserting vectors | collection={collection_name} | "
                f"vectors_count={len(chunks_ids)} | topic={topic.topic_name} | "
                f"duration={insert_time:.3f}s | error={str(e)}",
                exc_info=True
            )
            raise
        
        logger.info(
            f"Embedding and indexing process completed successfully for topic {topic.topic_name}: "
            f"{len(chunks_ids)} chunks indexed"
        )
        
        return True
    
    async def delete_chunks_from_vector_db(
        self,
        topic: Topic,
        chunk_ids: List[str]
    ) -> bool:
        """
        Delete chunks from vector database by their IDs.
        
        Args:
            topic: Topic model instance
            chunk_ids: List of chunk UUIDs to delete
        
        Returns:
            True if successful
        """
        if not chunk_ids:
            return True
        
        # Get collection name (use topic_name to match how collections are created)
        collection_name = self.create_collection_name(topic.topic_name)
        
        # Delete chunks by IDs from vector database
        delete_start = time.time()
        logger.info(
            f"Deleting chunks from vector database | collection={collection_name} | "
            f"chunks_count={len(chunk_ids)} | topic={topic.topic_name}"
        )
        
        try:
            # Assuming vectordb_client has a delete_by_ids method
            # If not, this will need to be implemented in the vectordb_client
            if hasattr(self.vectordb_client, 'delete_by_ids'):
                await self.vectordb_client.delete_by_ids(collection_name, chunk_ids)
            elif hasattr(self.vectordb_client, 'delete_many'):
                await self.vectordb_client.delete_many(collection_name, chunk_ids)
            else:
                # If no delete method exists, log warning but don't fail
                logger.warning(
                    f"Vector database client does not support deleting by IDs | "
                    f"collection={collection_name} | chunks_count={len(chunk_ids)} | "
                    f"topic={topic.topic_name}. Chunks may still exist in vector DB."
                )
                return True
            
            delete_time = time.time() - delete_start
            logger.info(
                f"Chunks deleted from vector database | collection={collection_name} | "
                f"chunks_count={len(chunk_ids)} | topic={topic.topic_name} | "
                f"duration={delete_time:.3f}s"
            )
        except Exception as e:
            delete_time = time.time() - delete_start
            logger.error(
                f"Error deleting chunks from vector database | collection={collection_name} | "
                f"chunks_count={len(chunk_ids)} | topic={topic.topic_name} | "
                f"duration={delete_time:.3f}s | error={str(e)}",
                exc_info=True
            )
            raise
        
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
        # Get collection name (use topic_name to match how collections are created)
        collection_name = self.create_collection_name(topic.topic_name)
        logger.debug(
            f"Search request received | collection={collection_name} | "
            f"query_length={len(text)} chars | limit={limit} | topic={topic.topic_name}"
        )
        
        # Generate query embedding
        embedding_start = time.time()
        logger.info(
            f"Generating query embedding | query_length={len(text)} chars | "
            f"model={self.embedding_client.embedding_model_id} | topic={topic.topic_name}"
        )
        
        try:
            query_embeddings = self.embedding_client.embed_text(text=text, document_type="query")
            embedding_time = time.time() - embedding_start
            
            # Check if embedding is valid
            if not query_embeddings or len(query_embeddings) == 0:
                logger.warning(
                    f"Query embedding generation returned empty result | "
                    f"query_length={len(text)} | topic={topic.topic_name} | "
                    f"duration={embedding_time:.3f}s"
                )
                return False
            
            # Extract first vector from list if list
            if isinstance(query_embeddings, list):
                query_vector = query_embeddings[0] if len(query_embeddings) > 0 else None
            else:
                query_vector = query_embeddings
            
            if query_vector is None:
                logger.warning(
                    f"Query vector is None after extraction | "
                    f"query_length={len(text)} | topic={topic.topic_name} | "
                    f"duration={embedding_time:.3f}s"
                )
                return False
            
            query_dim = len(query_vector) if query_vector else 0
            logger.info(
                f"Query embedding generated successfully | query_length={len(text)} | "
                f"embedding_dim={query_dim} | topic={topic.topic_name} | "
                f"duration={embedding_time:.3f}s"
            )
        except Exception as e:
            embedding_time = time.time() - embedding_start
            logger.error(
                f"Error generating query embedding | query_length={len(text)} | "
                f"topic={topic.topic_name} | duration={embedding_time:.3f}s | "
                f"error={str(e)}",
                exc_info=True
            )
            return False
        
        # Search vector database
        logger.info(
            f"Starting vector search | collection={collection_name} | "
            f"query_length={len(text)} chars | limit={limit} | topic={topic.topic_name}"
        )
        
        try:
            search_start = time.time()
            results = await self.vectordb_client.search_by_vector(
                collection_name,
                query_vector,
                limit
            )
            search_time = time.time() - search_start
            
            if not results:
                logger.warning(
                    f"Vector search returned no results | collection={collection_name} | "
                    f"topic={topic.topic_name} | search_time={search_time:.3f}s"
                )
                return False
            
            logger.info(
                f"Vector search completed | collection={collection_name} | "
                f"results_count={len(results)} | topic={topic.topic_name} | "
                f"search_time={search_time:.3f}s"
            )
            
        except ValueError as e:
            # Collection doesn't exist
            logger.warning(
                f"Collection does not exist | collection={collection_name} | "
                f"topic={topic.topic_name} | error={str(e)}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Error during vector search | collection={collection_name} | "
                f"topic={topic.topic_name} | error={str(e)}",
                exc_info=True
            )
            return False
        
        # Convert results to RetrievedDocument objects
        logger.debug(f"Converting {len(results)} search results to RetrievedDocument objects")
        retrieved_docs = []
        for idx, result in enumerate(results, start=1):
            try:
                if isinstance(result, dict):
                    retrieved_doc = RetrievedDocument(
                        text=result.get('text', ''),
                        metadata=result.get('metadata', {}),
                        score=result.get('score', 0.0)
                    )
                elif hasattr(result, 'text') and hasattr(result, 'metadata'):
                    retrieved_doc = RetrievedDocument(
                        text=result.text,
                        metadata=result.metadata if hasattr(result.metadata, '__dict__') else {},
                        score=getattr(result, 'score', 0.0)
                    )
                else:
                    logger.warning(
                        f"Unexpected result format at index {idx} | "
                        f"type={type(result)} | collection={collection_name}"
                    )
                    continue
                
                retrieved_docs.append(retrieved_doc)
                
            except Exception as e:
                logger.warning(
                    f"Error converting result at index {idx} | "
                    f"collection={collection_name} | error={str(e)}"
                )
                continue
        
        logger.info(
            f"Search results processed successfully | collection={collection_name} | "
            f"topic={topic.topic_name} | retrieved_docs_count={len(retrieved_docs)} | "
            f"original_results_count={len(results)}"
        )
        
        return retrieved_docs if retrieved_docs else False
    
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
        verify_start = time.time()
        collection_name = self.create_collection_name(topic.topic_name)
        logger.info(
            f"Starting claim verification | claim_length={len(claim)} chars | "
            f"limit={limit} | topic={topic.topic_name} | collection={collection_name}"
        )
        
        # Search for relevant chunks
        search_results = await self.search_evidence_collection(topic, claim, limit)
        
        # If no results, return empty
        if not search_results or search_results is False:
            verify_time = time.time() - verify_start
            logger.warning(
                f"Claim verification returned no evidence | claim_length={len(claim)} | "
                f"topic={topic.topic_name} | collection={collection_name} | "
                f"duration={verify_time:.3f}s"
            )
            return (None, [], [])
        
        # Process results into evidence format
        logger.debug(
            f"Processing {len(search_results)} search results for claim verification | "
            f"topic={topic.topic_name}"
        )
        supporting_evidence = []
        refuting_evidence = []  # Currently empty - would need classification logic
        
        for idx, result in enumerate(search_results, start=1):
            try:
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
                else:
                    logger.warning(
                        f"Unexpected result type in verify_claim at index {idx} | "
                        f"type={type(result)} | topic={topic.topic_name}"
                    )
            except Exception as e:
                logger.warning(
                    f"Error processing result at index {idx} in verify_claim | "
                    f"topic={topic.topic_name} | error={str(e)}"
                )
                continue
        
        verify_time = time.time() - verify_start
        logger.info(
            f"Claim verification completed | claim_length={len(claim)} | "
            f"topic={topic.topic_name} | collection={collection_name} | "
            f"supporting_evidence_count={len(supporting_evidence)} | "
            f"refuting_evidence_count={len(refuting_evidence)} | "
            f"total_results={len(search_results)} | duration={verify_time:.3f}s"
        )
        
        return (claim, supporting_evidence, refuting_evidence)
