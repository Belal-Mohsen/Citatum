from fastapi import APIRouter, Depends
from src.utils.config import config, Config

router = APIRouter(
    prefix="/api/v1",
    tags=["base"],
)

def get_config() -> Config:
    """Dependency to get application configuration"""
    return config


@router.get("/")
async def root(config: Config = Depends(get_config)):
    """Health check endpoint"""
    return {
        "message": f"{config.app_name} Backend API",
        "status": "running",
        "version": config.app_version
    }


@router.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}
