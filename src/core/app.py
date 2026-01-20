"""FastAPI application factory"""
from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.core.middleware import setup_middleware
from src.routes import base, documents, evidence
from src.utils.config import config
from src.utils.logger import get_logger
from src.utils.database import create_db_session_factory
from src.stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from src.stores.llm.LLMProviderFactory import LLMProviderFactory

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info(f"Starting {config.app_name} v{config.app_version}")
    logger.info(f"Server running on {config.api_host}:{config.api_port}")
    
    # Initialize database client
    try:
        db_session_factory = create_db_session_factory(config)
        app.state.db_client = db_session_factory
        logger.info("Database client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database client: {e}")
        raise
    
    # Initialize vector database client
    try:
        vectordb_factory = VectorDBProviderFactory(config)
        vectordb_client = vectordb_factory.create(config.vector_db_type.upper())
        
        if vectordb_client is None:
            logger.warning(
                f"Failed to create vector database client for provider: {config.vector_db_type}. "
                f"Vector database operations will not be available."
            )
            app.state.vectordb_client = None
        else:
            app.state.vectordb_client = vectordb_client
            logger.info(f"Vector database client ({config.vector_db_type}) initialized")
    except Exception as e:
        logger.error(f"Failed to initialize vector database client: {e}", exc_info=True)
        # Don't raise - vector DB might not be critical for all operations
        app.state.vectordb_client = None
    
    # Initialize embedding client
    try:
        llm_factory = LLMProviderFactory(config)
        embedding_client = llm_factory.create(config.llm_provider.upper())
        if embedding_client is None:
            logger.warning(f"Failed to create embedding client for provider: {config.llm_provider}")
            app.state.embedding_client = None
        else:
            app.state.embedding_client = embedding_client
            logger.info(f"Embedding client ({config.llm_provider}) initialized")
    except Exception as e:
        logger.error(f"Failed to initialize embedding client: {e}")
        app.state.embedding_client = None
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {config.app_name}")
    
    # Cleanup vector database connection
    if hasattr(app.state, 'vectordb_client') and app.state.vectordb_client:
        try:
            # PGVectorProvider has a close() method to close the connection pool
            if hasattr(app.state.vectordb_client, 'close'):
                await app.state.vectordb_client.close()
                logger.info("Vector database client connection pool closed")
        except Exception as e:
            logger.warning(f"Error closing vector database client: {e}")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title=config.app_name,
        description="Research Reproducibility and Traceability Assistant for processing academic documents into citable evidence chunks and retrieving verifiable evidence with exact quotes and provenance.",
        version=config.app_version,
        lifespan=lifespan,
    )
    
    # Setup middleware (must be before routers)
    setup_middleware(app)
    
    # Include routers
    app.include_router(base.router)
    app.include_router(documents.router)
    app.include_router(evidence.router)
    
    return app
