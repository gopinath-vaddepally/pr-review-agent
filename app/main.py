"""
FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.middleware.logging import RequestLoggingMiddleware
from app.api import webhooks, repositories, agents
from app.utils.logging import setup_logging, get_logger

# Configure structured logging
setup_logging(settings.log_level)

logger = get_logger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Azure DevOps PR Review Agent",
    description="Automated code review system for Azure DevOps pull requests",
    version="0.1.0"
)

# Configure CORS for Angular frontend
# In production, replace with specific frontend URL
frontend_origins = [
    "http://localhost:4200",  # Angular dev server
    "http://localhost:80",    # Production frontend
    "http://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins if hasattr(settings, 'environment') and settings.environment == 'production' else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Azure DevOps PR Review Agent API",
        "version": "0.1.0",
        "docs": "/docs"
    }


# Include API routers
app.include_router(webhooks.router)
app.include_router(repositories.router)
app.include_router(agents.router)


@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    logger.info("Starting Azure DevOps PR Review Agent API")
    
    # Initialize repository config service
    from app.services.repository_config import get_repository_config_service
    repo_service = get_repository_config_service()
    await repo_service.initialize()
    logger.info("Repository config service initialized")
    
    # Initialize Redis client
    from app.services.redis_client import get_redis_client
    redis_client = get_redis_client()
    await redis_client.connect()
    logger.info("Redis client initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup services on application shutdown."""
    logger.info("Shutting down Azure DevOps PR Review Agent API")
    
    # Close repository config service
    from app.services.repository_config import get_repository_config_service
    repo_service = get_repository_config_service()
    await repo_service.close()
    logger.info("Repository config service closed")
    
    # Close Redis client
    from app.services.redis_client import get_redis_client
    redis_client = get_redis_client()
    await redis_client.close()
    logger.info("Redis client closed")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
