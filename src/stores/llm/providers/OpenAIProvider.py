"""OpenAI provider for embeddings only"""
from typing import Optional
from openai import OpenAI

from src.stores.llm.LLMInterface import LLMInterface
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIProvider(LLMInterface):
    """OpenAI provider implementation for embeddings only"""
    
    def __init__(
        self, 
        api_key: str, 
        api_url: Optional[str] = None, 
        default_input_max_characters: int = 1000
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key
            api_url: Optional custom API URL (for OpenAI-compatible services)
            default_input_max_characters: Maximum characters for text processing (default: 1000)
        """
        self.api_key = api_key
        self.api_url = api_url
        self.default_input_max_characters = default_input_max_characters
        self.embedding_model_id: Optional[str] = None
        self.embedding_size: Optional[int] = None
        
        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_url if api_url else None
        )
    
    def set_embedding_model(self, model_id: str, embedding_size: int) -> None:
        """
        Set the embedding model and its dimension size.
        
        Args:
            model_id: Identifier of the embedding model (e.g., "text-embedding-3-small")
            embedding_size: Dimension size of the embedding vectors (e.g., 1536)
        """
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size
        logger.info(f"Set OpenAI embedding model: {model_id} (size: {embedding_size})")
    
    def embed_text(
        self, 
        text: str | list[str], 
        document_type: Optional[str] = None
    ) -> Optional[list[list[float]]]:
        """
        Generate embeddings for text or list of texts using OpenAI.
        
        Args:
            text: Single text string or list of text strings to embed
            document_type: Optional type hint (not used by OpenAI, but kept for interface compatibility)
        
        Returns:
            List of embedding vectors (list of floats), or None if error
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return None
        
        if not self.embedding_model_id:
            logger.error("Embedding model not set. Call set_embedding_model() first.")
            return None
        
        try:
            # Convert string to list if needed
            if isinstance(text, str):
                text_list = [text]
            else:
                text_list = text
            
            # Call OpenAI embeddings API
            response = self.client.embeddings.create(
                model=self.embedding_model_id,
                input=text_list
            )
            
            # Extract embeddings from response
            embeddings = [rec.embedding for rec in response.data]
            
            logger.debug(f"Generated {len(embeddings)} embeddings using OpenAI model {self.embedding_model_id}")
            return embeddings
        
        except Exception as e:
            logger.error(f"Error generating embeddings with OpenAI: {e}", exc_info=True)
            return None
    
    def process_text(self, text: str) -> str:
        """
        Process text by truncating to maximum characters.
        
        Args:
            text: Text string to process
        
        Returns:
            Processed text (truncated and stripped)
        """
        return text[:self.default_input_max_characters].strip()
