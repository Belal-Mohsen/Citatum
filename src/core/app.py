"""FastAPI application factory"""
from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.core.middleware import setup_middleware
from src.routes import base
from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info(f"Starting {config.app_name} v{config.app_version}")
    logger.info(f"Server running on {config.api_host}:{config.api_port}")
    yield
    # Shutdown
    logger.info(f"Shutting down {config.app_name}")


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
    
    return app
