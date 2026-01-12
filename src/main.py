import uvicorn

from src.core.app import create_app
from src.utils.config import config
from src.utils.logger import setup_logging, get_logger

# Set up logging before creating the app
setup_logging()

logger = get_logger(__name__)

# Create FastAPI app
app = create_app()


def main():
    """Run the FastAPI application with uvicorn"""
    from src.utils.logger import get_uvicorn_log_config
    log_config = get_uvicorn_log_config()
    
    uvicorn.run(
        "src.main:app",
        host=config.api_host,
        port=config.api_port,
        reload=config.debug,
        log_config=log_config,
    )


if __name__ == "__main__":
    main()
