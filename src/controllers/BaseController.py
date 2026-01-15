"""Base controller class for application controllers"""
import os
import random
import string
from pathlib import Path

from src.utils.helpers import get_settings
from src.utils.config import Config

# TODO: Consider implementing cloud storage (AWS S3, Google Cloud Storage) as an alternative
#       to local file storage. This would allow:
#       - Scalable file storage
#       - Better reliability and redundancy
#       - CDN integration for faster file access
#       - Reduced local disk usage
#       Implementation could use boto3 (S3) or google-cloud-storage (GCS) libraries

# TODO: Database will be cloud-based in the future (Supabase, AWS RDS, Google Cloud SQL, etc.)
#       Current local database storage is temporary. Migration plan should include:
#       - Connection pooling configuration
#       - Environment-based database URL management
#       - Cloud database credentials and security best practices
#       - Backup and disaster recovery strategies

class BaseController:
    """Base controller class with common functionality"""
    
    def __init__(self):
        """Initialize base controller with app settings"""
        self.app_settings: Config = get_settings()
        self._base_dir: str | None = None
        self._files_dir: str | None = None
        self._database_dir: str | None = None
    
    @property
    def base_dir(self) -> str:
        """
        Get application base directory (parent of controllers directory).
        
        Returns:
            Absolute path to base directory
        """
        if self._base_dir is None:
            # Get the directory where this file is located (controllers/)
            controllers_dir = os.path.dirname(os.path.abspath(__file__))
            # Parent directory is the base (src/)
            self._base_dir = os.path.dirname(controllers_dir)
        return self._base_dir
    
    @property
    def files_dir(self) -> str:
        """
        Get base file storage directory at {base_dir}/assets/topics.
        
        Returns:
            Absolute path to topics directory (created if doesn't exist)
        """
        if self._files_dir is None:
            files_path = os.path.join(self.base_dir, "assets", "topics")
            os.makedirs(files_path, exist_ok=True)
            self._files_dir = os.path.abspath(files_path)
        return self._files_dir
    
    def get_topic_files_dir(self, topic_name: str) -> str:
        """
        Get file storage directory for a specific topic at {base_dir}/assets/topics/{topic_name}/files.
        
        Args:
            topic_name: Name of the topic (used as directory name)
        
        Returns:
            Absolute path to topic's files directory (created if doesn't exist)
        """
        topic_files_path = os.path.join(self.files_dir, topic_name, "files")
        os.makedirs(topic_files_path, exist_ok=True)
        return os.path.abspath(topic_files_path)
    
    @property
    def database_dir(self) -> str:
        """
        Get database storage directory at {base_dir}/assets/database.
        
        Returns:
            Absolute path to database directory (created if doesn't exist)
        """
        if self._database_dir is None:
            db_path = os.path.join(self.base_dir, "assets", "database")
            os.makedirs(db_path, exist_ok=True)
            self._database_dir = os.path.abspath(db_path)
        return self._database_dir
    
    def generate_random_string(self, length: int = 12) -> str:
        """
        Generate random alphanumeric string (lowercase + digits).
        
        Args:
            length: Length of the random string (default: 12)
        
        Returns:
            Random alphanumeric string
        """
        characters = string.ascii_lowercase + string.digits
        return ''.join(random.choice(characters) for _ in range(length))
    
    def get_database_path(self, db_name: str) -> str:
        """
        Get or create database directory path, return the path.
        
        Args:
            db_name: Name of the database
        
        Returns:
            Absolute path to the database directory
        """
        db_path = os.path.join(self.database_dir, db_name)
        os.makedirs(db_path, exist_ok=True)
        return os.path.abspath(db_path)
