# Routes package

# Expose routers
from src.routes.base import router as base_router
from src.routes.documents import router as documents_router
from src.routes.evidence import router as evidence_router

__all__ = ["base_router", "documents_router", "evidence_router"]
