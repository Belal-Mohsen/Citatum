"""Base data model class for database operations"""
from typing import Callable, TYPE_CHECKING

from src.utils.helpers import get_settings
from src.utils.config import Config

class BaseDataModel:
    """Base class for all data models"""
    
    def __init__(self, db_client: object):
        """
        Initialize base data model with database client.
        
        Args:
            db_client: Database client object
        """
        self.db_client = db_client
        self.app_settings: Config = get_settings()
