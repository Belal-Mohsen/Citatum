"""Cohere provider for embeddings only"""
from typing import Optional
import cohere

from src.stores.llm.LLMInterface import LLMInterface
from src.stores.llm.LLMEnums import DocumentTypeEnum
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CoHereProvider(LLMInterface):
    """Cohere provider implementation for embeddings only"""
    
    def __init__(
        self, 
        api_key: str, 
        default_input_max_characters: int = 1000
    ):
        """
        Initialize Cohere provider.
        
        Args:
            api_key: Cohere API key
            default_input_max_characters: Maximum characters for text processing (default: 1000)
        """
        self.api_key = api_key
        self.default_input_max_characters = default_input_max_characters
        self.embedding_model_id: Optional[str] = None
        self.embedding_size: Optional[int] = None
        
        # Initialize Cohere client
        self.client = cohere.Client(api_key=api_key)
    
    def set_embedding_model(self, model_id: str, embedding_size: int) -> None:
        """
        Set the embedding model and its dimension size.
        
        Args:
            model_id: Identifier of the embedding model (e.g., "embed-english-v3.0")
            embedding_size: Dimension size of the embedding vectors
        """
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size
        logger.info(f"Set Cohere embedding model: {model_id} (size: {embedding_size})")
    
    def embed_text(
        self, 
        text: str | list[str], 
        document_type: Optional[str] = None
    ) -> Optional[list[list[float]]]:
        """
        Generate embeddings for text or list of texts using Cohere.
        
        Args:
            text: Single text string or list of text strings to embed
            document_type: Type hint ("document" or "query") to determine input_type
        
        Returns:
            List of embedding vectors (list of floats), or None if error
        """
        if not self.client:
            logger.error("Cohere client not initialized")
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
            
            # Determine input_type based on document_type
            # Cohere uses "search_document" for documents and "search_query" for queries
            if document_type == DocumentTypeEnum.QUERY.value or document_type == "query":
                input_type = "search_query"
            else:
                input_type = "search_document"
            
            # Process texts (truncate if needed)
            processed_texts = [self.process_text(t) for t in text_list]
            
            # Call Cohere embed API
            response = self.client.embed(
                model=self.embedding_model_id,
                texts=processed_texts,
                input_type=input_type,
                embedding_types=['float']
            )
            
            # Extract embeddings from response
            # Cohere returns embeddings in response.embeddings.float
            embeddings = [f for f in response.embeddings.float]
            
            logger.debug(f"Generated {len(embeddings)} embeddings using Cohere model {self.embedding_model_id}")
            return embeddings
        
        except Exception as e:
            logger.error(f"Error generating embeddings with Cohere: {e}", exc_info=True)
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
