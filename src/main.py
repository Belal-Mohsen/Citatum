from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.routes import base
from src.utils.config import config


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    pass


# Create FastAPI app
app = FastAPI(
    title=config.app_name,
    description="Research Reproducibility and Traceability Assistant for processing academic documents into citable evidence chunks and retrieving verifiable evidence with exact quotes and provenance.",
    version=config.app_version,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(base.router)


def main():
    """Run the FastAPI application with uvicorn"""
    uvicorn.run(
        "src.main:app",
        host=config.api_host,
        port=config.api_port,
        reload=config.debug,
    )


if __name__ == "__main__":
    main()
