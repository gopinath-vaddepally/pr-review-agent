"""
Agent Orchestrator component.

Spawns, monitors, and manages Review Agent instances.
Handles agent lifecycle including timeout monitoring and resource cleanup.
"""

import logging
import asyncio
import time
import uuid
from typing import Optional

from app.models.agent import AgentState, AgentStatus, AgentInfo
from app.models.pr_event import PRMetadata
from app.services.redis_client import RedisClient
from app.agents.review_agent import ReviewAgent
from app.config import settings

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrates Review Agent lifecycle and monitoring."""
    
    def __init__(self):
        """Initialize the Agent Orchestrator."""
        self.redis_client = RedisClient()
        self.timeout_seconds = settings.agent_timeout_seconds
    
    async def spawn_agent(
        self,
        pr_id: str,
        pr_metadata: PRMetadata,
        repository_id: str
    ) -> str:
        """
        Spawn new Review Agent instance and return agent ID.
        
        Args:
            pr_id: Pull request ID
            pr_metadata: Pull request metadata
            repository_id: Repository identifier
            
        Returns:
            Agent ID
        """
        # Generate unique agent ID
        agent_id = self._generate_agent_id(pr_id)
        
        logger.info(f"Spawning Review Agent {agent_id} for PR {pr_id}")
        
        try:
            # Store agent metadata in Redis
            await self._store_agent_metadata(agent_id, pr_id, repository_id)
            
            # Create and execute agent in background
            asyncio.create_task(self._execute_agent_with_monitoring(
                agent_id,
                pr_metadata,
                repository_id
            ))
            
            logger.info(f"Review Agent {agent_id} spawned successfully")
            return agent_id
            
        except Exception as e:
            logger.error(f"Failed to spawn agent {agent_id}: {e}", exc_info=True)
            raise
    
    async def monitor_agent(self, agent_id: str) -> AgentStatus:
        """
        Check agent execution status.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Current agent status
        """
        try:
            state = await self.redis_client.get_agent_state(agent_id)
            
            if not state:
                return AgentStatus.FAILED
            
            # Check phase to determine status
            if state.phase == "complete":
                return AgentStatus.COMPLETED
            elif state.phase == "error" or state.phase == "failed":
                return AgentStatus.FAILED
            elif state.end_time and state.end_time > 0:
                # Agent finished but not in complete phase
                return AgentStatus.FAILED
            else:
                # Check for timeout
                elapsed = time.time() - state.start_time
                if elapsed > self.timeout_seconds:
                    return AgentStatus.TIMEOUT
                return AgentStatus.RUNNING
                
        except Exception as e:
            logger.error(f"Error monitoring agent {agent_id}: {e}")
            return AgentStatus.FAILED
    
    async def terminate_agent(self, agent_id: str, reason: str) -> None:
        """
        Forcefully terminate agent instance.
        
        Args:
            agent_id: Agent identifier
            reason: Reason for termination
        """
        logger.warning(f"Terminating agent {agent_id}: {reason}")
        
        try:
            # Get current state
            state = await self.redis_client.get_agent_state(agent_id)
            
            if state:
                # Update state to mark as terminated
                state.phase = "terminated"
                state.end_time = time.time()
                state.errors.append(f"Agent terminated: {reason}")
                
                # Save updated state
                await self.redis_client.save_agent_state(agent_id, state)
            
            # Clean up resources
            await self._cleanup_agent_resources(agent_id)
            
            logger.info(f"Agent {agent_id} terminated successfully")
            
        except Exception as e:
            logger.error(f"Error terminating agent {agent_id}: {e}", exc_info=True)
    
    async def get_agent_state(self, agent_id: str) -> Optional[AgentState]:
        """
        Retrieve current agent state from Redis.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Agent state or None if not found
        """
        try:
            return await self.redis_client.get_agent_state(agent_id)
        except Exception as e:
            logger.error(f"Error retrieving agent state for {agent_id}: {e}")
            return None
    
    async def get_agent_info(self, agent_id: str) -> Optional[AgentInfo]:
        """
        Get agent information for monitoring.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Agent info or None if not found
        """
        try:
            state = await self.get_agent_state(agent_id)
            
            if not state:
                return None
            
            status = await self.monitor_agent(agent_id)
            elapsed = time.time() - state.start_time
            
            return AgentInfo(
                agent_id=agent_id,
                pr_id=state.pr_id,
                status=status,
                phase=state.phase,
                start_time=state.start_time,
                elapsed_seconds=elapsed
            )
            
        except Exception as e:
            logger.error(f"Error getting agent info for {agent_id}: {e}")
            return None
    
    async def list_active_agents(self) -> list[AgentInfo]:
        """
        List all active agents.
        
        Returns:
            List of active agent info
        """
        try:
            # Get all agent IDs from Redis
            agent_ids = await self.redis_client.list_active_agents()
            
            # Get info for each agent
            agents = []
            for agent_id in agent_ids:
                info = await self.get_agent_info(agent_id)
                if info and info.status == AgentStatus.RUNNING:
                    agents.append(info)
            
            return agents
            
        except Exception as e:
            logger.error(f"Error listing active agents: {e}")
            return []
    
    async def _execute_agent_with_monitoring(
        self,
        agent_id: str,
        pr_metadata: PRMetadata,
        repository_id: str
    ) -> None:
        """
        Execute agent with timeout monitoring.
        
        Args:
            agent_id: Agent identifier
            pr_metadata: Pull request metadata
            repository_id: Repository identifier
        """
        try:
            # Create agent
            agent = ReviewAgent(agent_id, pr_metadata, repository_id)
            
            # Execute with timeout
            try:
                await asyncio.wait_for(
                    agent.execute(),
                    timeout=self.timeout_seconds
                )
                logger.info(f"Agent {agent_id} completed successfully")
                
            except asyncio.TimeoutError:
                logger.error(f"Agent {agent_id} exceeded timeout of {self.timeout_seconds}s")
                await self.terminate_agent(agent_id, "timeout")
                
        except Exception as e:
            logger.error(f"Agent {agent_id} execution failed: {e}", exc_info=True)
            
            # Update state to failed
            try:
                state = await self.redis_client.get_agent_state(agent_id)
                if state:
                    state.phase = "failed"
                    state.end_time = time.time()
                    state.errors.append(f"Execution error: {str(e)}")
                    await self.redis_client.save_agent_state(agent_id, state)
            except Exception as save_error:
                logger.error(f"Failed to save error state for {agent_id}: {save_error}")
        
        finally:
            # Clean up resources
            await self._cleanup_agent_resources(agent_id)
    
    def _generate_agent_id(self, pr_id: str) -> str:
        """
        Generate unique agent ID.
        
        Args:
            pr_id: Pull request ID
            
        Returns:
            Unique agent ID
        """
        unique_id = str(uuid.uuid4())[:8]
        return f"agent_{pr_id}_{unique_id}"
    
    async def _store_agent_metadata(
        self,
        agent_id: str,
        pr_id: str,
        repository_id: str
    ) -> None:
        """
        Store agent metadata in Redis.
        
        Args:
            agent_id: Agent identifier
            pr_id: Pull request ID
            repository_id: Repository identifier
        """
        metadata = {
            "agent_id": agent_id,
            "pr_id": pr_id,
            "repository_id": repository_id,
            "start_time": time.time(),
            "status": "running"
        }
        
        await self.redis_client.store_agent_metadata(agent_id, metadata)
        
        # Add to active agents set
        await self.redis_client.add_active_agent(pr_id, agent_id)
    
    async def _cleanup_agent_resources(self, agent_id: str) -> None:
        """
        Clean up agent resources.
        
        Args:
            agent_id: Agent identifier
        """
        try:
            # Get agent state to find PR ID
            state = await self.redis_client.get_agent_state(agent_id)
            
            if state:
                # Remove from active agents set
                await self.redis_client.remove_active_agent(state.pr_id, agent_id)
            
            # Remove agent metadata
            await self.redis_client.delete_agent_metadata(agent_id)
            
            logger.debug(f"Cleaned up resources for agent {agent_id}")
            
        except Exception as e:
            logger.error(f"Error cleaning up agent {agent_id}: {e}")
