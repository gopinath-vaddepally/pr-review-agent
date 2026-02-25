"""
Repository management REST API endpoints.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Header

from app.config import settings
from app.models.repository import Repository, RepositoryCreate
from app.services.repository_config import RepositoryConfigService, RepositoryValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repositories", tags=["repositories"])

# Initialize repository config service
repo_config_service = RepositoryConfigService()


async def verify_api_key(x_api_key: str = Header(None)) -> None:
    """
    Verify API key for admin endpoints.
    
    Args:
        x_api_key: API key from request header
        
    Raises:
        HTTPException: If API key is invalid or missing
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    # For hackathon: simple API key check
    # In production: use proper authentication (OAuth, JWT, etc.)
    expected_key = getattr(settings, 'admin_api_key', settings.webhook_secret)
    
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


@router.post("", response_model=Repository, dependencies=[Depends(verify_api_key)])
async def add_repository(repo_create: RepositoryCreate) -> Repository:
    """
    Add repository to monitoring configuration.
    
    This endpoint:
    1. Validates repository URL format
    2. Adds repository to MySQL database
    3. Registers Azure DevOps Service Hook
    
    Args:
        repo_create: Repository creation request
        
    Returns:
        Created repository configuration
        
    Raises:
        HTTPException: If validation fails or repository already exists
    """
    try:
        logger.info(f"Adding repository: {repo_create.repository_url}")
        
        # Add repository (includes validation and service hook registration)
        repository = await repo_config_service.add_repository(repo_create)
        
        logger.info(f"Repository added successfully: {repository.id}")
        return repository
        
    except RepositoryValidationError as e:
        logger.warning(f"Repository validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        logger.warning(f"Repository already exists: {e}")
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding repository: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{repo_id}", dependencies=[Depends(verify_api_key)])
async def remove_repository(repo_id: str) -> dict:
    """
    Remove repository from monitoring configuration.
    
    This endpoint:
    1. Removes repository from MySQL database
    2. Unregisters Azure DevOps Service Hook
    
    Args:
        repo_id: Repository ID to remove
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If repository not found
    """
    try:
        logger.info(f"Removing repository: {repo_id}")
        
        # Remove repository (includes service hook unregistration)
        await repo_config_service.remove_repository(repo_id)
        
        logger.info(f"Repository removed successfully: {repo_id}")
        return {"status": "success", "message": f"Repository {repo_id} removed"}
        
    except ValueError as e:
        logger.warning(f"Repository not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error removing repository: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=List[Repository], dependencies=[Depends(verify_api_key)])
async def list_repositories() -> List[Repository]:
    """
    List all monitored repositories.
    
    Returns:
        List of repository configurations
        
    Raises:
        HTTPException: If database error occurs
    """
    try:
        logger.info("Listing all repositories")
        
        repositories = await repo_config_service.list_repositories()
        
        logger.info(f"Found {len(repositories)} repositories")
        return repositories
        
    except Exception as e:
        logger.error(f"Error listing repositories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
