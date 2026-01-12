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
    vector_db_type: Literal["chroma", "pinecone", "weaviate", "qdrant"] = "chroma"
    vector_db_path: str = "./data/vector_db"
    vector_db_host: str = "localhost"
    vector_db_port: int = 8000
    
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
    
    # Logging
    log_level: str = "INFO"


# Create a global config instance
config = Config()
