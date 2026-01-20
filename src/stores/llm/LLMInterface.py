"""Abstract base class for LLM providers (embeddings only)"""
from abc import ABC, abstractmethod
from typing import Optional


class LLMInterface(ABC):
    """
    Abstract base class for LLM providers.
    
    This interface focuses on embeddings only - no text generation functionality.
    All providers must implement embedding methods for vector database operations.
    """
    
    @abstractmethod
    def set_embedding_model(self, model_id: str, embedding_size: int) -> None:
        """
        Set the embedding model and its dimension size.
        
        Args:
            model_id: Identifier of the embedding model (e.g., "text-embedding-3-small")
            embedding_size: Dimension size of the embedding vectors (e.g., 1536)
        """
        pass
    
    @abstractmethod
    def embed_text(
        self, 
        text: str | list[str], 
        document_type: Optional[str] = None
    ) -> Optional[list[list[float]]]:
        """
        Generate embeddings for text or list of texts.
        
        Args:
            text: Single text string or list of text strings to embed
            document_type: Optional type hint ("document" or "query") for some providers
        
        Returns:
            List of embedding vectors (list of floats), or None if error
            - For single text: Returns list with one embedding vector
            - For list of texts: Returns list of embedding vectors
        """
        pass
    
    @abstractmethod
    def process_text(self, text: str) -> str:
        """
        Process text by truncating to maximum characters.
        
        Args:
            text: Text string to process
        
        Returns:
            Processed text (truncated and stripped)
        """
        pass
