"""
Agent monitoring REST API endpoints.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Header

from app.config import settings
from app.models.agent import AgentInfo, AgentStatus
from app.services.agent_orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])

# Initialize agent orchestrator
agent_orchestrator = AgentOrchestrator()


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


@router.get("", response_model=List[AgentInfo], dependencies=[Depends(verify_api_key)])
async def list_active_agents() -> List[AgentInfo]:
    """
    List all currently active review agents.
    
    Returns:
        List of active agent information
        
    Raises:
        HTTPException: If error occurs retrieving agents
    """
    try:
        logger.info("Listing active agents")
        
        agents = await agent_orchestrator.list_active_agents()
        
        logger.info(f"Found {len(agents)} active agents")
        return agents
        
    except Exception as e:
        logger.error(f"Error listing active agents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{agent_id}", response_model=AgentInfo, dependencies=[Depends(verify_api_key)])
async def get_agent_status(agent_id: str) -> AgentInfo:
    """
    Get detailed status of specific agent.
    
    Args:
        agent_id: Agent identifier
        
    Returns:
        Agent information and status
        
    Raises:
        HTTPException: If agent not found
    """
    try:
        logger.info(f"Getting status for agent: {agent_id}")
        
        agent_info = await agent_orchestrator.get_agent_info(agent_id)
        
        if not agent_info:
            logger.warning(f"Agent not found: {agent_id}")
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        
        logger.info(f"Agent {agent_id} status: {agent_info.status}")
        return agent_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
