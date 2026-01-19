"""Topic controller for research topic directory management"""
import os
from typing import Union

from src.controllers.BaseController import BaseController


class TopicController(BaseController):
    """Controller for managing research topic directories"""
    
    def __init__(self):
        """Initialize TopicController"""
        super().__init__()
    
    def get_topic_path(self, topic_id: Union[str, int]) -> str:
        """
        Get or create topic directory at {self.files_dir}/{topic_id}.
        
        Args:
            topic_id: Topic identifier (str or int) - converted to string for path
        
        Returns:
            Absolute path to topic directory (created if doesn't exist)
        
        Raises:
            OSError: If directory creation fails
        """
        try:
            # Convert topic_id to string for path construction
            topic_id_str = str(topic_id)
            topic_path = os.path.join(self.files_dir, topic_id_str)
            
            # Create directory if it doesn't exist
            os.makedirs(topic_path, exist_ok=True)
            
            return os.path.abspath(topic_path)
        except OSError as e:
            raise OSError(f"Failed to create topic directory for topic_id {topic_id}: {e}") from e
