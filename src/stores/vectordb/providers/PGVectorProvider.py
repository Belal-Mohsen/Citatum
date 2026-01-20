"""PGVector provider for PostgreSQL with pgvector extension"""
import asyncpg
from typing import List, Optional, Any
import json

from src.stores.vectordb.VectorDBInterface import VectorDBInterface
from src.utils.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PGVectorProvider(VectorDBInterface):
    """PostgreSQL vector database provider using pgvector extension"""
    
    def __init__(self, config: Config):
        """
        Initialize PGVector provider.
        
        Args:
            config: Application configuration with database_url
        """
        self.config = config
        self.connection_pool: Optional[asyncpg.Pool] = None
        self._default_vector_size = getattr(config, 'embedding_dimension', 1536)
        
        # Get distance method from config (cosine, l2, inner_product)
        self.distance_method = getattr(config, 'vector_db_distance_method', 'cosine').lower()
        
        # Get index type from config (hnsw, ivfflat)
        self.index_type = getattr(config, 'pgvector_index_type', 'hnsw').lower()
        
        # Get index threshold for IVFFlat
        self.index_threshold = getattr(config, 'pgvector_index_threshold', 100)
        
        # Map distance method to pgvector operators and index ops
        self._distance_operators = {
            'cosine': ('<=>', 'vector_cosine_ops'),
            'l2': ('<->', 'vector_l2_ops'),
            'inner_product': ('<#>', 'vector_ip_ops')
        }
        
        if self.distance_method not in self._distance_operators:
            logger.warning(
                f"Unknown distance method '{self.distance_method}', defaulting to 'cosine'"
            )
            self.distance_method = 'cosine'
        
        self.distance_operator, self.index_ops = self._distance_operators[self.distance_method]
        logger.info(
            f"PGVector configured: distance_method={self.distance_method}, "
            f"index_type={self.index_type}, index_threshold={self.index_threshold}"
        )
    
    @property
    def default_vector_size(self) -> int:
        """Default vector dimension size"""
        return self._default_vector_size
    
    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create connection pool"""
        if self.connection_pool is None:
            database_url = self.config.get_database_url()
            if not database_url:
                raise ValueError("Database URL not configured")
            
            # Normalize URL for asyncpg (strip SQLAlchemy driver suffix)
            # asyncpg expects postgresql:// or postgres://, not postgresql+asyncpg://
            if database_url.startswith('postgresql+asyncpg://'):
                database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://', 1)
            elif database_url.startswith('postgresql+psycopg2://'):
                database_url = database_url.replace('postgresql+psycopg2://', 'postgresql://', 1)
            elif database_url.startswith('postgres+asyncpg://'):
                database_url = database_url.replace('postgres+asyncpg://', 'postgres://', 1)
            elif database_url.startswith('postgres+psycopg2://'):
                database_url = database_url.replace('postgres+psycopg2://', 'postgres://', 1)
            
            self.connection_pool = await asyncpg.create_pool(
                database_url,
                min_size=1,
                max_size=10
            )
            logger.info("Created PostgreSQL connection pool for PGVector")
        
        return self.connection_pool
    
    async def create_collection(
        self, 
        collection_name: str, 
        vector_size: int, 
        do_reset: bool = False
    ) -> bool:
        """
        Create a vector collection (table) in PostgreSQL.
        
        Args:
            collection_name: Name of the collection (table name)
            vector_size: Dimension size of vectors
            do_reset: If True, drop existing table before creating
        
        Returns:
            True if successful
        """
        pool = await self._get_pool()
        
        try:
            async with pool.acquire() as conn:
                # Drop table if do_reset
                if do_reset:
                    await conn.execute(f"DROP TABLE IF EXISTS {collection_name} CASCADE")
                    logger.info(f"Dropped existing collection: {collection_name}")
                
                # Create table with pgvector
                # Foreign key references chunks table
                create_table_sql = f"""
                    CREATE TABLE IF NOT EXISTS {collection_name} (
                        id SERIAL PRIMARY KEY,
                        chunk_id INTEGER NOT NULL,
                        text TEXT NOT NULL,
                        metadata JSONB,
                        embedding vector({vector_size}),
                        FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id) ON DELETE CASCADE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """
                
                await conn.execute(create_table_sql)
                
                # Create vector index based on configuration
                # Check row count for IVFFlat threshold
                if self.index_type == 'ivfflat':
                    row_count = await conn.fetchval(f"SELECT COUNT(*) FROM {collection_name}")
                    
                    if row_count < self.index_threshold:
                        logger.info(
                            f"Collection {collection_name} has {row_count} rows, "
                            f"below threshold {self.index_threshold}. "
                            f"Skipping IVFFlat index creation. "
                            f"Index will be created automatically when threshold is met."
                        )
                    else:
                        # Create IVFFlat index (requires lists parameter, using default)
                        # IVFFlat needs number of lists (typically sqrt of row count)
                        num_lists = max(10, int((row_count / 1000) ** 0.5))
                        index_sql = f"""
                            CREATE INDEX IF NOT EXISTS {collection_name}_embedding_idx 
                            ON {collection_name} 
                            USING ivfflat (embedding {self.index_ops}) 
                            WITH (lists = {num_lists});
                        """
                        await conn.execute(index_sql)
                        logger.info(
                            f"Created IVFFlat index for {collection_name} with {num_lists} lists"
                        )
                else:
                    # Create HNSW index (default)
                    index_sql = f"""
                        CREATE INDEX IF NOT EXISTS {collection_name}_embedding_idx 
                        ON {collection_name} 
                        USING hnsw (embedding {self.index_ops});
                    """
                    await conn.execute(index_sql)
                    logger.debug(f"Created HNSW index for {collection_name} with {self.distance_method} distance")
                
                # Create index on chunk_id for faster lookups
                chunk_id_index_sql = f"""
                    CREATE INDEX IF NOT EXISTS {collection_name}_chunk_id_idx 
                    ON {collection_name} (chunk_id);
                """
                
                await conn.execute(chunk_id_index_sql)
                
                logger.info(f"Created collection: {collection_name} with vector size {vector_size}")
                return True
        
        except Exception as e:
            logger.error(f"Error creating collection {collection_name}: {e}", exc_info=True)
            raise
    
    async def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a vector collection (table).
        
        Args:
            collection_name: Name of the collection to delete
        
        Returns:
            True if successful
        """
        pool = await self._get_pool()
        
        try:
            async with pool.acquire() as conn:
                await conn.execute(f"DROP TABLE IF EXISTS {collection_name} CASCADE")
                logger.info(f"Deleted collection: {collection_name}")
                return True
        
        except Exception as e:
            logger.error(f"Error deleting collection {collection_name}: {e}", exc_info=True)
            raise
    
    async def list_collections(self) -> List[str]:
        """
        List all vector collections (tables) in PostgreSQL.
        
        Returns:
            List of collection names (table names)
        """
        pool = await self._get_pool()
        
        try:
            async with pool.acquire() as conn:
                # Query to find all tables that have an embedding column (vector type)
                # This identifies pgvector collections
                collections = await conn.fetch("""
                    SELECT tablename 
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                    AND tablename IN (
                        SELECT table_name 
                        FROM information_schema.columns 
                        WHERE column_name = 'embedding' 
                        AND data_type = 'USER-DEFINED'
                        AND udt_name = 'vector'
                    )
                    ORDER BY tablename
                """)
                
                collection_names = [row['tablename'] for row in collections]
                logger.debug(f"Found {len(collection_names)} collections in PostgreSQL")
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
        pool = await self._get_pool()
        
        try:
            async with pool.acquire() as conn:
                # Check if table exists first
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = $1
                    )
                """, collection_name)
                
                if not table_exists:
                    # Collection doesn't exist, return empty collection info
                    logger.info(f"Collection {collection_name} does not exist")
                    return {
                        "collection_name": collection_name,
                        "row_count": 0,
                        "vector_dimension": None,
                        "provider": "pgvector",
                        "exists": False
                    }
                
                # Get row count
                count_result = await conn.fetchval(
                    f"SELECT COUNT(*) FROM {collection_name}"
                )
                
                # Get vector dimension from table definition
                dimension_result = await conn.fetchval("""
                    SELECT atttypmod 
                    FROM pg_attribute 
                    WHERE attrelid = $1::regclass 
                    AND attname = 'embedding'
                """, collection_name)
                
                vector_dimension = dimension_result if dimension_result else None
                
                info = {
                    "collection_name": collection_name,
                    "row_count": count_result,
                    "vector_dimension": vector_dimension,
                    "provider": "pgvector",
                    "exists": True
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
            record_ids: List of chunk IDs (required for PGVector)
        
        Returns:
            True if successful
        """
        if record_ids is None or len(record_ids) != len(texts):
            raise ValueError("record_ids (chunk_ids) must be provided and match texts length")

        # Ensure all input lists are aligned to avoid silent truncation by zip()
        expected_len = len(texts)
        if len(metadata) != expected_len:
            raise ValueError(
                f"Metadata length ({len(metadata)}) does not match texts length ({expected_len})"
            )
        if len(vectors) != expected_len:
            raise ValueError(
                f"Vectors length ({len(vectors)}) does not match texts length ({expected_len})"
            )
        
        pool = await self._get_pool()
        
        try:
            async with pool.acquire() as conn:
                # Prepare data for batch insert
                values = []
                for i, (text, meta, vector, chunk_id) in enumerate(zip(texts, metadata, vectors, record_ids)):
                    # Ensure metadata includes chunk_id
                    if meta is None:
                        meta = {}
                    meta['chunk_id'] = chunk_id
                    
                    # Convert vector list to string format for pgvector
                    # Format: '[0.1,0.2,0.3]' (no spaces, comma-separated)
                    vector_str = '[' + ','.join(str(float(v)) for v in vector) + ']'
                    
                    values.append((
                        chunk_id,
                        text,
                        json.dumps(meta),
                        vector_str
                    ))
                
                # Batch insert using executemany
                # Note: We pass vector as string and cast to vector type in SQL
                await conn.executemany(
                    f"""
                    INSERT INTO {collection_name} (chunk_id, text, metadata, embedding)
                    VALUES ($1, $2, $3::jsonb, $4::vector)
                    """,
                    values
                )
                
                logger.info(f"Inserted {len(values)} vectors into {collection_name}")
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
        Search for similar vectors in a collection using configured distance method.
        
        Args:
            collection_name: Name of the collection
            query_vector: Query embedding vector
            limit: Maximum number of results
        
        Returns:
            List of result dictionaries with text, metadata, score, and chunk_id
        """
        pool = await self._get_pool()
        
        try:
            async with pool.acquire() as conn:
                # Build query based on distance method
                # For cosine: 1 - distance = similarity
                # For l2: lower distance = higher similarity (inverse)
                # For inner_product: higher value = higher similarity (direct)
                if self.distance_method == 'cosine':
                    # Cosine: 1 - distance = similarity (0 to 1, higher is better)
                    score_expr = f"1 - (embedding {self.distance_operator} $1::vector)"
                    order_expr = f"embedding {self.distance_operator} $1::vector"
                elif self.distance_method == 'l2':
                    # L2: lower distance = higher similarity (inverse)
                    # Use negative distance as similarity score
                    score_expr = f"-(embedding {self.distance_operator} $1::vector)"
                    order_expr = f"embedding {self.distance_operator} $1::vector"
                else:  # inner_product
                    # Inner product: higher value = higher similarity (direct)
                    score_expr = f"embedding {self.distance_operator} $1::vector"
                    order_expr = f"embedding {self.distance_operator} $1::vector DESC"
                
                results = await conn.fetch(
                    f"""
                    SELECT 
                        chunk_id,
                        text,
                        metadata,
                        {score_expr} as similarity_score
                    FROM {collection_name}
                    ORDER BY {order_expr}
                    LIMIT $2
                    """,
                    query_vector,
                    limit
                )
                
                # Format results
                formatted_results = []
                for row in results:
                    result_dict = {
                        'chunk_id': row['chunk_id'],
                        'text': row['text'],
                        'metadata': json.loads(row['metadata']) if row['metadata'] else {},
                        'score': float(row['similarity_score'])
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
        pool = await self._get_pool()
        
        try:
            async with pool.acquire() as conn:
                deleted_count = await conn.execute(
                    f"""
                    DELETE FROM {collection_name}
                    WHERE chunk_id = ANY($1::int[])
                    """,
                    record_ids
                )
                
                logger.info(f"Deleted {deleted_count} records from {collection_name}")
                return True
        
        except Exception as e:
            logger.error(f"Error deleting records from {collection_name}: {e}", exc_info=True)
            raise
    
    async def close(self):
        """Close the connection pool"""
        if self.connection_pool:
            await self.connection_pool.close()
            logger.info("Closed PostgreSQL connection pool")
