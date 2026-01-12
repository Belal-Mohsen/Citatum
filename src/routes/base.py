from fastapi import APIRouter, Depends
from src.utils.config import config, Config
from src.utils.logger import get_logger

router = APIRouter(
    prefix="/api/v1",
    tags=["base"],
)

logger = get_logger(__name__)

def get_config() -> Config:
    """Dependency to get application configuration"""
    return config


@router.get("/")
async def root(config: Config = Depends(get_config)):
    """Health check endpoint"""
    logger.info("Root endpoint accessed")
    return {
        "message": f"{config.app_name} Backend API",
        "status": "running",
        "version": config.app_version
    }


@router.get("/health")
async def health():
    """Health check endpoint"""
    logger.debug("Health check endpoint accessed")
    return {"status": "healthy"}
