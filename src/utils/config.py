from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Config(BaseSettings):
    """Application configuration loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Configuration
    app_name: str = "Citatum"
    app_version: str = "0.1.0"
    
    # API Keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    
    # Vector Database Configuration
    vector_db_type: Literal["pgvector","chroma", "pinecone", "weaviate", "qdrant"] = "pgvector"
    vector_db_path: str = "./data/vector_db"
    vector_db_host: str = "localhost"
    vector_db_port: int = 8000
    
    # Vector Database Distance Method (applies to all providers)
    # Options: "cosine" (default), "l2" (Euclidean), "inner_product" (dot product)
    vector_db_distance_method: Literal["cosine", "l2", "inner_product"] = Field(
        default="cosine",
        description="Distance method for vector similarity search. "
                    "Set via VECTOR_DB_DISTANCE_METHOD environment variable. "
                    "Options: cosine, l2, inner_product. Applies to all vector DB providers."
    )
    
    # PGVector-specific Index Configuration
    # Index type: "hnsw" (default, fast queries) or "ivfflat" (faster build, requires threshold)
    pgvector_index_type: Literal["hnsw", "ivfflat"] = Field(
        default="hnsw",
        description="Index type for PGVector. Set via PGVECTOR_INDEX_TYPE environment variable. "
                    "Options: hnsw (default, fast queries), ivfflat (faster build, requires threshold)"
    )
    
    # PGVector IVFFlat Index Threshold
    # Minimum number of rows before creating IVFFlat index (typically 100+)
    pgvector_index_threshold: int = Field(
        default=100,
        description="Minimum rows required before creating IVFFlat index. "
                    "Set via PGVECTOR_INDEX_THRESHOLD environment variable. "
                    "Only applies when pgvector_index_type is 'ivfflat'. "
                    "IVFFlat indexes are only useful with sufficient data (typically 100+ rows)."
    )
    
    # Vector Database Distance Method
    # Options: "cosine" (default), "l2" (Euclidean), "inner_product" (dot product)
    # Applies to all vector DB providers (PGVector, Qdrant, etc.)
    vector_db_distance_method: Literal["cosine", "l2", "inner_product"] = Field(
        default="cosine",
        description="Distance method for vector similarity search. "
                    "Set via VECTOR_DB_DISTANCE_METHOD environment variable. "
                    "Options: cosine, l2, inner_product"
    )
    
    # PGVector-specific Index Configuration
    # Index type: "hnsw" (default, fast queries) or "ivfflat" (faster build, requires threshold)
    pgvector_index_type: Literal["hnsw", "ivfflat"] = Field(
        default="hnsw",
        description="Index type for PGVector. Set via PGVECTOR_INDEX_TYPE environment variable. "
                    "Options: hnsw (default), ivfflat"
    )
    
    # PGVector IVFFlat Index Threshold
    # Minimum number of rows before creating IVFFlat index (typically 100+)
    pgvector_index_threshold: int = Field(
        default=100,
        description="Minimum rows required before creating IVFFlat index. "
                    "Set via PGVECTOR_INDEX_THRESHOLD environment variable. "
                    "Only applies when pgvector_index_type is 'ivfflat'"
    )
    
    # Embedding Model Configuration
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    
    # LLM Configuration
    llm_provider: Literal["openai", "anthropic"] = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2000
    
    # RAG Configuration
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k_retrieval: int = 5
    
    # Server Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    cors_origins: str = "*"  # Comma-separated list of allowed origins, or "*" for all
    
    # Database Configuration
    database_url: str = Field(
        default="",
        description="PostgreSQL database connection URL. Must be set via DATABASE_URL environment variable."
    )
    
    def get_database_url(self) -> str:
        """
        Get database URL with validation.
        Raises ValueError if DATABASE_URL is not set.
        """
        if not self.database_url or not self.database_url.strip():
            raise ValueError(
                "DATABASE_URL environment variable is required but not set. "
                "Please set DATABASE_URL in your .env file. "
                "Example: DATABASE_URL=postgresql://user:password@localhost:5432/citatum"
            )
        return self.database_url
    
    # File Upload Configuration
    file_allowed_types: str = Field(
        default="application/pdf,text/plain",
        description="Comma-separated list of allowed MIME types for file uploads. "
                    "Set via FILE_ALLOWED_TYPES environment variable."
    )
    
    file_max_size_mb: int = Field(
        default=50,
        description="Maximum file size in megabytes for uploads. "
                    "Set via FILE_MAX_SIZE_MB environment variable."
    )
    
    def get_file_allowed_types(self) -> list[str]:
        """
        Get list of allowed file types from configuration.
        
        Returns:
            List of allowed MIME types
        """
        if not self.file_allowed_types:
            return ["application/pdf", "text/plain"]  # Default fallback
        
        # Split by comma and strip whitespace
        types = [t.strip() for t in self.file_allowed_types.split(",") if t.strip()]
        return types if types else ["application/pdf", "text/plain"]  # Default fallback
    
    # Logging
    log_level: str = "INFO"


# Create a global config instance
config = Config()
