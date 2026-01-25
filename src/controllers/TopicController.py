"""Topic controller for research topic directory management"""
import os
from typing import Union

from src.controllers.BaseController import BaseController


class TopicController(BaseController):
    """Controller for managing research topic directories"""
    
    def __init__(self):
        """Initialize TopicController"""
        super().__init__()
    
    def get_topic_path(self, topic_name: str) -> str:
        """
        Get or create topic directory at {self.files_dir}/{topic_name}.
        
        Args:
            topic_name: Topic name (used as directory name)
        
        Returns:
            Absolute path to topic directory (created if doesn't exist)
        
        Raises:
            OSError: If directory creation fails
        """
        try:
            # Sanitize topic_name for filesystem safety
            # Replace any path separators and other unsafe characters
            safe_topic_name = topic_name.replace("/", "_").replace("\\", "_").replace("..", "_")
            topic_path = os.path.join(self.files_dir, safe_topic_name)
            
            # Create directory if it doesn't exist
            os.makedirs(topic_path, exist_ok=True)
            
            return os.path.abspath(topic_path)
        except OSError as e:
            raise OSError(f"Failed to create topic directory for topic_name {topic_name}: {e}") from e
