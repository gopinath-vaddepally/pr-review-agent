"""
Redis client wrapper for agent state management and job queue.

This service provides Redis operations for:
- Agent state storage using hashes
- Job queue using lists
- Agent tracking using sets
- Agent timeout tracking using sorted sets

Includes connection pooling and retry logic for resilience.
"""

import json
import logging
import asyncio
from typing import Optional, List, Dict, Any, Set
from contextlib import asynccontextmanager
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from redis.exceptions import RedisError, ConnectionError, TimeoutError

from app.models.agent import AgentState
from app.models.pr_event import PREvent


logger = logging.getLogger(__name__)


class RedisConnectionError(Exception):
    """Raised when Redis connection fails after retries."""
    pass


class RedisClient:
    """
    Redis client wrapper with connection pooling and retry logic.
    
    Provides methods for:
    - Agent state storage (hash operations)
    - Job queue operations (list push/pop)
    - Agent tracking set operations
    - Agent timeout tracking (sorted sets)
    """
    
    # Redis key prefixes
    AGENT_STATE_PREFIX = "agent:{agent_id}:state"
    ACTIVE_AGENTS_PREFIX = "active_agents:{pr_id}"
    JOB_QUEUE_KEY = "job_queue:pr_reviews"
    AGENT_TIMEOUTS_KEY = "agent_timeouts"
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        connection_timeout: int = 5
    ):
        """
        Initialize Redis client.
        
        Args:
            redis_url: Redis connection URL. If None, will load from settings.
            max_retries: Maximum number of retry attempts for transient errors
            retry_delay: Base delay between retries (exponential backoff)
            connection_timeout: Connection timeout in seconds
        """
        self._redis_url = redis_url
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._connection_timeout = connection_timeout
    
    async def initialize(self) -> None:
        """
        Initialize Redis connection pool.
        
        Should be called during application startup.
        
        Raises:
            RedisConnectionError: If connection fails after retries
        """
        try:
            # Get Redis URL from settings if not provided
            if not self._redis_url:
                from app.config import settings
                self._redis_url = settings.redis_url
            
            # Create connection pool
            self._pool = ConnectionPool.from_url(
                self._redis_url,
                max_connections=10,
                decode_responses=True,
                socket_timeout=self._connection_timeout,
                socket_connect_timeout=self._connection_timeout
            )
            
            # Create Redis client
            self._client = redis.Redis(connection_pool=self._pool)
            
            # Test connection
            await self._client.ping()
            
            logger.info("Redis connection pool initialized successfully")
        
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection pool: {e}")
            raise RedisConnectionError(f"Failed to connect to Redis: {e}")
    
    async def close(self) -> None:
        """
        Close Redis connection pool.
        
        Should be called during application shutdown.
        """
        if self._client:
            await self._client.close()
        
        if self._pool:
            await self._pool.disconnect()
        
        logger.info("Redis connection pool closed")
    
    @asynccontextmanager
    async def _get_client(self):
        """
        Get Redis client with connection check.
        
        Yields:
            redis.Redis: Redis client instance
        
        Raises:
            RuntimeError: If client not initialized
        """
        if not self._client:
            raise RuntimeError("Redis client not initialized. Call initialize() first.")
        
        yield self._client
    
    async def _retry_operation(self, operation, *args, **kwargs):
        """
        Execute Redis operation with retry logic.
        
        Args:
            operation: Async function to execute
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation
        
        Returns:
            Operation result
        
        Raises:
            RedisConnectionError: If operation fails after all retries
        """
        last_error = None
        
        for attempt in range(self._max_retries):
            try:
                return await operation(*args, **kwargs)
            
            except (ConnectionError, TimeoutError) as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Redis operation failed (attempt {attempt + 1}/{self._max_retries}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Redis operation failed after {self._max_retries} attempts: {e}")
            
            except RedisError as e:
                # Non-transient errors, don't retry
                logger.error(f"Redis operation failed with non-transient error: {e}")
                raise
        
        raise RedisConnectionError(f"Redis operation failed after {self._max_retries} retries: {last_error}")
    
    # ========== Agent State Operations (Hash) ==========
    
    def _agent_state_key(self, agent_id: str) -> str:
        """Get Redis key for agent state."""
        return self.AGENT_STATE_PREFIX.format(agent_id=agent_id)
    
    async def save_agent_state(self, state: AgentState) -> None:
        """
        Save agent state to Redis.
        
        Args:
            state: AgentState object to save
        
        Raises:
            RedisConnectionError: If operation fails after retries
        """
        async def _save():
            async with self._get_client() as client:
                key = self._agent_state_key(state.agent_id)
                
                # Serialize state to JSON
                state_dict = state.model_dump(mode='json')
                state_json = json.dumps(state_dict)
                
                # Store as hash with single field for simplicity
                await client.hset(key, "data", state_json)
                
                logger.debug(f"Saved agent state for {state.agent_id}")
        
        await self._retry_operation(_save)
    
    async def get_agent_state(self, agent_id: str) -> Optional[AgentState]:
        """
        Retrieve agent state from Redis.
        
        Args:
            agent_id: Agent ID
        
        Returns:
            AgentState object if found, None otherwise
        
        Raises:
            RedisConnectionError: If operation fails after retries
        """
        async def _get():
            async with self._get_client() as client:
                key = self._agent_state_key(agent_id)
                
                # Get state data
                state_json = await client.hget(key, "data")
                
                if not state_json:
                    return None
                
                # Deserialize from JSON
                state_dict = json.loads(state_json)
                return AgentState(**state_dict)
        
        result = await self._retry_operation(_get)
        
        if result:
            logger.debug(f"Retrieved agent state for {agent_id}")
        
        return result
    
    async def delete_agent_state(self, agent_id: str) -> None:
        """
        Delete agent state from Redis.
        
        Args:
            agent_id: Agent ID
        
        Raises:
            RedisConnectionError: If operation fails after retries
        """
        async def _delete():
            async with self._get_client() as client:
                key = self._agent_state_key(agent_id)
                await client.delete(key)
                logger.debug(f"Deleted agent state for {agent_id}")
        
        await self._retry_operation(_delete)
    
    async def update_agent_phase(self, agent_id: str, phase: str) -> None:
        """
        Update agent phase in state.
        
        Args:
            agent_id: Agent ID
            phase: New phase name
        
        Raises:
            RedisConnectionError: If operation fails after retries
        """
        async def _update():
            # Get current state
            state = await self.get_agent_state(agent_id)
            if state:
                state.phase = phase
                await self.save_agent_state(state)
                logger.debug(f"Updated agent {agent_id} phase to {phase}")
        
        await self._retry_operation(_update)
    
    # ========== Job Queue Operations (List) ==========
    
    async def enqueue_pr_review(self, pr_event: PREvent) -> None:
        """
        Enqueue PR review job.
        
        Args:
            pr_event: PR event to enqueue
        
        Raises:
            RedisConnectionError: If operation fails after retries
        """
        async def _enqueue():
            async with self._get_client() as client:
                # Serialize event to JSON
                event_dict = pr_event.model_dump(mode='json')
                event_json = json.dumps(event_dict)
                
                # Push to list (right push for FIFO)
                await client.rpush(self.JOB_QUEUE_KEY, event_json)
                
                logger.info(f"Enqueued PR review job for PR {pr_event.pr_id}")
        
        await self._retry_operation(_enqueue)
    
    async def dequeue_pr_review(self, timeout: int = 0) -> Optional[PREvent]:
        """
        Dequeue PR review job.
        
        Args:
            timeout: Blocking timeout in seconds (0 for non-blocking)
        
        Returns:
            PREvent if available, None if queue is empty
        
        Raises:
            RedisConnectionError: If operation fails after retries
        """
        async def _dequeue():
            async with self._get_client() as client:
                # Pop from list (left pop for FIFO)
                if timeout > 0:
                    result = await client.blpop(self.JOB_QUEUE_KEY, timeout=timeout)
                    if result:
                        _, event_json = result
                    else:
                        return None
                else:
                    event_json = await client.lpop(self.JOB_QUEUE_KEY)
                
                if not event_json:
                    return None
                
                # Deserialize from JSON
                event_dict = json.loads(event_json)
                pr_event = PREvent(**event_dict)
                
                logger.info(f"Dequeued PR review job for PR {pr_event.pr_id}")
                return pr_event
        
        return await self._retry_operation(_dequeue)
    
    async def get_queue_length(self) -> int:
        """
        Get number of jobs in queue.
        
        Returns:
            Number of jobs in queue
        
        Raises:
            RedisConnectionError: If operation fails after retries
        """
        async def _get_length():
            async with self._get_client() as client:
                length = await client.llen(self.JOB_QUEUE_KEY)
                return length
        
        return await self._retry_operation(_get_length)
    
    # ========== Agent Tracking Operations (Set) ==========
    
    def _active_agents_key(self, pr_id: str) -> str:
        """Get Redis key for active agents set."""
        return self.ACTIVE_AGENTS_PREFIX.format(pr_id=pr_id)
    
    async def add_active_agent(self, pr_id: str, agent_id: str) -> None:
        """
        Add agent to active agents set for a PR.
        
        Args:
            pr_id: Pull request ID
            agent_id: Agent ID
        
        Raises:
            RedisConnectionError: If operation fails after retries
        """
        async def _add():
            async with self._get_client() as client:
                key = self._active_agents_key(pr_id)
                await client.sadd(key, agent_id)
                logger.debug(f"Added agent {agent_id} to active agents for PR {pr_id}")
        
        await self._retry_operation(_add)
    
    async def remove_active_agent(self, pr_id: str, agent_id: str) -> None:
        """
        Remove agent from active agents set for a PR.
        
        Args:
            pr_id: Pull request ID
            agent_id: Agent ID
        
        Raises:
            RedisConnectionError: If operation fails after retries
        """
        async def _remove():
            async with self._get_client() as client:
                key = self._active_agents_key(pr_id)
                await client.srem(key, agent_id)
                logger.debug(f"Removed agent {agent_id} from active agents for PR {pr_id}")
        
        await self._retry_operation(_remove)
    
    async def get_active_agents(self, pr_id: str) -> Set[str]:
        """
        Get all active agents for a PR.
        
        Args:
            pr_id: Pull request ID
        
        Returns:
            Set of agent IDs
        
        Raises:
            RedisConnectionError: If operation fails after retries
        """
        async def _get():
            async with self._get_client() as client:
                key = self._active_agents_key(pr_id)
                members = await client.smembers(key)
                return set(members)
        
        return await self._retry_operation(_get)
    
    async def has_active_agent(self, pr_id: str) -> bool:
        """
        Check if PR has any active agents.
        
        Args:
            pr_id: Pull request ID
        
        Returns:
            True if PR has active agents, False otherwise
        
        Raises:
            RedisConnectionError: If operation fails after retries
        """
        agents = await self.get_active_agents(pr_id)
        return len(agents) > 0
    
    # ========== Agent Timeout Tracking (Sorted Set) ==========
    
    async def add_agent_timeout(self, agent_id: str, expiration_timestamp: float) -> None:
        """
        Add agent to timeout tracking sorted set.
        
        Args:
            agent_id: Agent ID
            expiration_timestamp: Unix timestamp when agent should timeout
        
        Raises:
            RedisConnectionError: If operation fails after retries
        """
        async def _add():
            async with self._get_client() as client:
                await client.zadd(
                    self.AGENT_TIMEOUTS_KEY,
                    {agent_id: expiration_timestamp}
                )
                logger.debug(f"Added agent {agent_id} to timeout tracking (expires at {expiration_timestamp})")
        
        await self._retry_operation(_add)
    
    async def remove_agent_timeout(self, agent_id: str) -> None:
        """
        Remove agent from timeout tracking.
        
        Args:
            agent_id: Agent ID
        
        Raises:
            RedisConnectionError: If operation fails after retries
        """
        async def _remove():
            async with self._get_client() as client:
                await client.zrem(self.AGENT_TIMEOUTS_KEY, agent_id)
                logger.debug(f"Removed agent {agent_id} from timeout tracking")
        
        await self._retry_operation(_remove)
    
    async def get_expired_agents(self, current_timestamp: float) -> List[str]:
        """
        Get agents that have exceeded their timeout.
        
        Args:
            current_timestamp: Current Unix timestamp
        
        Returns:
            List of agent IDs that have timed out
        
        Raises:
            RedisConnectionError: If operation fails after retries
        """
        async def _get():
            async with self._get_client() as client:
                # Get all agents with score (expiration) <= current_timestamp
                expired = await client.zrangebyscore(
                    self.AGENT_TIMEOUTS_KEY,
                    min=0,
                    max=current_timestamp
                )
                return list(expired)
        
        result = await self._retry_operation(_get)
        
        if result:
            logger.info(f"Found {len(result)} expired agents")
        
        return result
    
    # ========== Additional Methods ==========
    
    async def enqueue_review_job(self, job_payload: Dict[str, Any]) -> None:
        """
        Enqueue review job with custom payload.
        
        Args:
            job_payload: Job payload dictionary
        
        Raises:
            RedisConnectionError: If operation fails after retries
        """
        async def _enqueue():
            async with self._get_client() as client:
                job_json = json.dumps(job_payload)
                await client.rpush(self.JOB_QUEUE_KEY, job_json)
                logger.info(f"Enqueued review job for PR {job_payload.get('pr_id')}")
        
        await self._retry_operation(_enqueue)
    
    async def get_active_agents_for_pr(self, pr_id: str) -> List[str]:
        """
        Get list of active agents for a PR.
        
        Args:
            pr_id: Pull request ID
        
        Returns:
            List of agent IDs
        """
        agents = await self.get_active_agents(pr_id)
        return list(agents)
    
    async def store_agent_metadata(self, agent_id: str, metadata: Dict[str, Any]) -> None:
        """
        Store agent metadata.
        
        Args:
            agent_id: Agent ID
            metadata: Metadata dictionary
        """
        async def _store():
            async with self._get_client() as client:
                key = f"agent:{agent_id}:metadata"
                metadata_json = json.dumps(metadata)
                await client.set(key, metadata_json)
                logger.debug(f"Stored metadata for agent {agent_id}")
        
        await self._retry_operation(_store)
    
    async def delete_agent_metadata(self, agent_id: str) -> None:
        """
        Delete agent metadata.
        
        Args:
            agent_id: Agent ID
        """
        async def _delete():
            async with self._get_client() as client:
                key = f"agent:{agent_id}:metadata"
                await client.delete(key)
                logger.debug(f"Deleted metadata for agent {agent_id}")
        
        await self._retry_operation(_delete)
    
    async def list_active_agents(self) -> List[str]:
        """
        List all active agent IDs across all PRs.
        
        Returns:
            List of agent IDs
        """
        async def _list():
            async with self._get_client() as client:
                # Get all keys matching active_agents pattern
                keys = await client.keys("active_agents:*")
                
                agent_ids = []
                for key in keys:
                    members = await client.smembers(key)
                    agent_ids.extend(members)
                
                return agent_ids
        
        return await self._retry_operation(_list)
    
    # ========== Utility Methods ==========
    
    async def ping(self) -> bool:
        """
        Test Redis connection.
        
        Returns:
            True if connection is healthy
        
        Raises:
            RedisConnectionError: If ping fails
        """
        async def _ping():
            async with self._get_client() as client:
                return await client.ping()
        
        return await self._retry_operation(_ping)
    
    async def clear_all_data(self) -> None:
        """
        Clear all data (for testing purposes only).
        
        WARNING: This will delete all keys in the Redis database.
        
        Raises:
            RedisConnectionError: If operation fails after retries
        """
        async def _clear():
            async with self._get_client() as client:
                await client.flushdb()
                logger.warning("Cleared all Redis data")
        
        await self._retry_operation(_clear)


# Global service instance factory
def get_redis_client() -> RedisClient:
    """
    Get or create the global Redis client instance.
    
    Returns:
        RedisClient instance
    """
    return RedisClient()
