"""Middleware configuration for FastAPI application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.utils.config import config


def setup_middleware(app: FastAPI) -> None:
    """
    Configure all middleware for the FastAPI application.
    
    Middleware is added in order, but executed in reverse order.
    So the last middleware added will be executed first.
    
    Args:
        app: FastAPI application instance
    """
    # CORS middleware - should be added first (executed last)
    # Parse CORS origins from config (comma-separated string or "*" for all)
    if config.cors_origins == "*":
        cors_origins = ["*"]
    else:
        cors_origins = [origin.strip() for origin in config.cors_origins.split(",") if origin.strip()]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add other middleware here as needed
    # Example: Authentication, Rate Limiting, etc.
