"""Factory for creating vector database providers"""
from typing import Optional

from src.stores.vectordb.VectorDBInterface import VectorDBInterface
from src.stores.vectordb.providers.PGVectorProvider import PGVectorProvider
from src.stores.vectordb.providers.QdrantDBProvider import QdrantDBProvider
from src.utils.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class VectorDBProviderFactory:
    """Factory for creating vector database providers"""
    
    def __init__(self, config: Config):
        """
        Initialize factory with configuration.
        
        Args:
            config: Application configuration object
        """
        self.config = config
    
    def create(self, provider: str) -> Optional[VectorDBInterface]:
        """
        Create vector database provider instance.
        
        Args:
            provider: Provider name ("PGVECTOR", "QDRANT", "CHROMA", "PINECONE", "WEAVIATE")
        
        Returns:
            VectorDBInterface instance or None if provider not supported
        """
        provider_upper = provider.upper()
        
        if provider_upper == "PGVECTOR":
            try:
                provider_instance = PGVectorProvider(self.config)
                logger.info("Created PGVector provider")
                return provider_instance
            except Exception as e:
                logger.error(f"Failed to create PGVector provider: {e}", exc_info=True)
                return None
        
        elif provider_upper == "QDRANT":
            try:
                provider_instance = QdrantDBProvider(self.config)
                logger.info("Created Qdrant provider")
                return provider_instance
            except Exception as e:
                logger.error(f"Failed to create Qdrant provider: {e}", exc_info=True)
                return None
        
        elif provider_upper in ("CHROMA", "PINECONE", "WEAVIATE"):
            logger.warning(
                f"Vector database provider '{provider_upper}' is not yet implemented. "
                f"Supported providers: PGVECTOR, QDRANT"
            )
            return None
        
        else:
            logger.warning(f"Unsupported vector database provider: {provider}")
            return None
