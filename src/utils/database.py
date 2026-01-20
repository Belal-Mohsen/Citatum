"""Database connection utilities"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import Callable

from src.utils.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def create_db_session_factory(config: Config) -> Callable[[], AsyncSession]:
    """
    Create a database session factory.
    
    Args:
        config: Application configuration with database_url
    
    Returns:
        Callable that returns an AsyncSession context manager
    """
    database_url = config.get_database_url()
    
    # Create async engine
    engine = create_async_engine(
        database_url,
        echo=False,  # Set to True for SQL query logging
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,
        max_overflow=10,
    )
    
    # Create session factory
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    logger.info(f"Database session factory created for: {database_url.split('@')[-1] if '@' in database_url else 'database'}")
    
    # Return a callable that returns a session context manager
    def get_session() -> AsyncSession:
        return async_session_maker()
    
    return get_session
