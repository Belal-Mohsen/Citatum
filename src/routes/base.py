from fastapi import APIRouter, Depends
from src.utils.helpers import get_settings
from src.utils.config import Config
from src.utils.logger import get_logger

router = APIRouter(
    prefix="/api/v1",
    tags=["api_v1, base"],
)

logger = get_logger(__name__)


@router.get("/")
async def welcome(settings: Config = Depends(get_settings)):
    logger.info("Welcome endpoint accessed")
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version
    }

@router.get("/health")
async def health():
    """Health check endpoint"""
    logger.debug("Health check endpoint accessed")
    return {"status": "healthy"}


@router.head("/health")
async def health_head():
    """Health check for HEAD requests"""
    return {}
