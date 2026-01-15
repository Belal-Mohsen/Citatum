"""Helper functions for the application"""
from src.utils.config import config, Config


def get_settings() -> Config:
    """
    Get application settings/configuration.
    
    Returns:
        Config instance with application settings
    """
    return config
