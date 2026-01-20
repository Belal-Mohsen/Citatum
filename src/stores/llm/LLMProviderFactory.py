"""Factory for creating LLM providers (embeddings only)"""
from typing import Optional

from src.stores.llm.LLMInterface import LLMInterface
from src.stores.llm.providers.OpenAIProvider import OpenAIProvider
from src.stores.llm.providers.CoHereProvider import CoHereProvider
from src.utils.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LLMProviderFactory:
    """Factory for creating LLM embedding providers"""
    
    def __init__(self, config: Config):
        """
        Initialize factory with configuration.
        
        Args:
            config: Application configuration object
        """
        self.config = config
    
    def create(self, provider: str) -> Optional[LLMInterface]:
        """
        Create LLM provider instance for embeddings.
        
        Args:
            provider: Provider name ("OPENAI" or "COHERE")
        
        Returns:
            LLMInterface instance or None if provider not supported
        """
        provider_upper = provider.upper()
        
        if provider_upper == "OPENAI":
            # Get OpenAI API key from config
            api_key = getattr(self.config, 'openai_api_key', '')
            if not api_key:
                logger.warning("OpenAI API key not found in config")
                return None
            
            # Get optional API URL (for OpenAI-compatible services)
            api_url = getattr(self.config, 'openai_api_url', None)
            
            # Get default input max characters (for text processing)
            default_input_max_characters = getattr(
                self.config, 
                'default_input_max_characters', 
                1000
            )
            
            provider_instance = OpenAIProvider(
                api_key=api_key,
                api_url=api_url,
                default_input_max_characters=default_input_max_characters
            )
            
            # Set embedding model from config
            embedding_model = getattr(self.config, 'embedding_model', 'text-embedding-3-small')
            embedding_dimension = getattr(self.config, 'embedding_dimension', 1536)
            provider_instance.set_embedding_model(embedding_model, embedding_dimension)
            
            logger.info(f"Created OpenAI provider with model {embedding_model}")
            return provider_instance
        
        elif provider_upper == "COHERE":
            # Get Cohere API key from config
            api_key = getattr(self.config, 'cohere_api_key', '')
            if not api_key:
                logger.warning("Cohere API key not found in config")
                return None
            
            # Get default input max characters
            default_input_max_characters = getattr(
                self.config, 
                'default_input_max_characters', 
                1000
            )
            
            provider_instance = CoHereProvider(
                api_key=api_key,
                default_input_max_characters=default_input_max_characters
            )
            
            # Set embedding model from config
            embedding_model = getattr(self.config, 'embedding_model', 'embed-english-v3.0')
            embedding_dimension = getattr(self.config, 'embedding_dimension', 1024)
            provider_instance.set_embedding_model(embedding_model, embedding_dimension)
            
            logger.info(f"Created Cohere provider with model {embedding_model}")
            return provider_instance
        
        else:
            logger.warning(f"Unsupported LLM provider: {provider}")
            return None
