"""
Unit tests for Redis client wrapper.

Tests Redis operations using fakeredis for isolated testing.
"""

import pytest
import time
from datetime import datetime
from typing import AsyncGenerator

import fakeredis

from app.services.redis_client import RedisClient, RedisConnectionError
from app.models.agent import AgentState
from app.models.pr_event import PREvent, PRMetadata


@pytest.fixture
async def redis_client() -> AsyncGenerator[RedisClient, None]:
    """Create Redis client with fakeredis for testing."""
    client = RedisClient(redis_url="redis://localhost:6379/0")
    
    # Replace the real Redis client with fakeredis
    fake_redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    client._client = fake_redis
    
    yield client
    
    # Cleanup
    await fake_redis.flushdb()
    await fake_redis.aclose()


@pytest.fixture
def sample_agent_state() -> AgentState:
    """Create sample agent state for testing."""
    return AgentState(
        agent_id="agent_123",
        pr_id="pr_456",
        pr_metadata=PRMetadata(
            pr_id="pr_456",
            repository_id="repo_789",
            source_branch="feature/test",
            target_branch="main",
            author="test_user",
            title="Test PR",
            description="Test description",
            source_commit_id="abc123",
            target_commit_id="def456"
        ),
        phase="initialize",
        start_time=time.time()
    )


@pytest.fixture
def sample_pr_event() -> PREvent:
    """Create sample PR event for testing."""
    return PREvent(
        event_type="git.pullrequest.created",
        pr_id="pr_456",
        repository_id="repo_789",
        source_branch="feature/test",
        target_branch="main",
        author="test_user",
        title="Test PR",
        description="Test description",
        timestamp=datetime.now()
    )


class TestAgentStateOperations:
    """Test agent state storage operations."""
    
    @pytest.mark.asyncio
    async def test_save_and_get_agent_state(
        self,
        redis_client: RedisClient,
        sample_agent_state: AgentState
    ):
        """Test saving and retrieving agent state."""
        # Save state
        await redis_client.save_agent_state(sample_agent_state)
        
        # Retrieve state
        retrieved_state = await redis_client.get_agent_state(sample_agent_state.agent_id)
        
        # Verify
        assert retrieved_state is not None
        assert retrieved_state.agent_id == sample_agent_state.agent_id
        assert retrieved_state.pr_id == sample_agent_state.pr_id
        assert retrieved_state.phase == sample_agent_state.phase
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_agent_state(self, redis_client: RedisClient):
        """Test retrieving non-existent agent state returns None."""
        state = await redis_client.get_agent_state("nonexistent_agent")
        assert state is None
    
    @pytest.mark.asyncio
    async def test_delete_agent_state(
        self,
        redis_client: RedisClient,
        sample_agent_state: AgentState
    ):
        """Test deleting agent state."""
        # Save state
        await redis_client.save_agent_state(sample_agent_state)
        
        # Verify it exists
        state = await redis_client.get_agent_state(sample_agent_state.agent_id)
        assert state is not None
        
        # Delete state
        await redis_client.delete_agent_state(sample_agent_state.agent_id)
        
        # Verify it's gone
        state = await redis_client.get_agent_state(sample_agent_state.agent_id)
        assert state is None
    
    @pytest.mark.asyncio
    async def test_update_agent_phase(
        self,
        redis_client: RedisClient,
        sample_agent_state: AgentState
    ):
        """Test updating agent phase."""
        # Save initial state
        await redis_client.save_agent_state(sample_agent_state)
        
        # Update phase
        new_phase = "line_analysis"
        await redis_client.update_agent_phase(sample_agent_state.agent_id, new_phase)
        
        # Retrieve and verify
        state = await redis_client.get_agent_state(sample_agent_state.agent_id)
        assert state is not None
        assert state.phase == new_phase


class TestJobQueueOperations:
    """Test job queue operations."""
    
    @pytest.mark.asyncio
    async def test_enqueue_and_dequeue_pr_review(
        self,
        redis_client: RedisClient,
        sample_pr_event: PREvent
    ):
        """Test enqueuing and dequeuing PR review jobs."""
        # Enqueue job
        await redis_client.enqueue_pr_review(sample_pr_event)
        
        # Dequeue job
        dequeued_event = await redis_client.dequeue_pr_review()
        
        # Verify
        assert dequeued_event is not None
        assert dequeued_event.pr_id == sample_pr_event.pr_id
        assert dequeued_event.repository_id == sample_pr_event.repository_id
    
    @pytest.mark.asyncio
    async def test_dequeue_empty_queue(self, redis_client: RedisClient):
        """Test dequeuing from empty queue returns None."""
        event = await redis_client.dequeue_pr_review()
        assert event is None
    
    @pytest.mark.asyncio
    async def test_queue_fifo_order(
        self,
        redis_client: RedisClient,
        sample_pr_event: PREvent
    ):
        """Test queue maintains FIFO order."""
        # Create multiple events
        event1 = sample_pr_event.model_copy(update={"pr_id": "pr_1"})
        event2 = sample_pr_event.model_copy(update={"pr_id": "pr_2"})
        event3 = sample_pr_event.model_copy(update={"pr_id": "pr_3"})
        
        # Enqueue in order
        await redis_client.enqueue_pr_review(event1)
        await redis_client.enqueue_pr_review(event2)
        await redis_client.enqueue_pr_review(event3)
        
        # Dequeue and verify order
        dequeued1 = await redis_client.dequeue_pr_review()
        dequeued2 = await redis_client.dequeue_pr_review()
        dequeued3 = await redis_client.dequeue_pr_review()
        
        assert dequeued1.pr_id == "pr_1"
        assert dequeued2.pr_id == "pr_2"
        assert dequeued3.pr_id == "pr_3"
    
    @pytest.mark.asyncio
    async def test_get_queue_length(
        self,
        redis_client: RedisClient,
        sample_pr_event: PREvent
    ):
        """Test getting queue length."""
        # Initially empty
        length = await redis_client.get_queue_length()
        assert length == 0
        
        # Add jobs
        await redis_client.enqueue_pr_review(sample_pr_event)
        await redis_client.enqueue_pr_review(sample_pr_event)
        
        # Check length
        length = await redis_client.get_queue_length()
        assert length == 2
        
        # Dequeue one
        await redis_client.dequeue_pr_review()
        
        # Check length again
        length = await redis_client.get_queue_length()
        assert length == 1


class TestAgentTrackingOperations:
    """Test agent tracking set operations."""
    
    @pytest.mark.asyncio
    async def test_add_and_get_active_agents(self, redis_client: RedisClient):
        """Test adding and retrieving active agents."""
        pr_id = "pr_123"
        agent_id = "agent_456"
        
        # Add agent
        await redis_client.add_active_agent(pr_id, agent_id)
        
        # Get active agents
        agents = await redis_client.get_active_agents(pr_id)
        
        # Verify
        assert agent_id in agents
        assert len(agents) == 1
    
    @pytest.mark.asyncio
    async def test_remove_active_agent(self, redis_client: RedisClient):
        """Test removing active agent."""
        pr_id = "pr_123"
        agent_id = "agent_456"
        
        # Add agent
        await redis_client.add_active_agent(pr_id, agent_id)
        
        # Verify it exists
        agents = await redis_client.get_active_agents(pr_id)
        assert agent_id in agents
        
        # Remove agent
        await redis_client.remove_active_agent(pr_id, agent_id)
        
        # Verify it's gone
        agents = await redis_client.get_active_agents(pr_id)
        assert agent_id not in agents
    
    @pytest.mark.asyncio
    async def test_has_active_agent(self, redis_client: RedisClient):
        """Test checking if PR has active agents."""
        pr_id = "pr_123"
        agent_id = "agent_456"
        
        # Initially no agents
        has_agent = await redis_client.has_active_agent(pr_id)
        assert has_agent is False
        
        # Add agent
        await redis_client.add_active_agent(pr_id, agent_id)
        
        # Now has agent
        has_agent = await redis_client.has_active_agent(pr_id)
        assert has_agent is True
    
    @pytest.mark.asyncio
    async def test_multiple_agents_per_pr(self, redis_client: RedisClient):
        """Test tracking multiple agents for same PR."""
        pr_id = "pr_123"
        agent1 = "agent_1"
        agent2 = "agent_2"
        
        # Add multiple agents
        await redis_client.add_active_agent(pr_id, agent1)
        await redis_client.add_active_agent(pr_id, agent2)
        
        # Get all agents
        agents = await redis_client.get_active_agents(pr_id)
        
        # Verify both present
        assert agent1 in agents
        assert agent2 in agents
        assert len(agents) == 2


class TestAgentTimeoutTracking:
    """Test agent timeout tracking operations."""
    
    @pytest.mark.asyncio
    async def test_add_and_remove_agent_timeout(self, redis_client: RedisClient):
        """Test adding and removing agent timeout."""
        agent_id = "agent_123"
        expiration = time.time() + 600  # 10 minutes from now
        
        # Add timeout
        await redis_client.add_agent_timeout(agent_id, expiration)
        
        # Remove timeout
        await redis_client.remove_agent_timeout(agent_id)
        
        # Verify it's gone (no expired agents)
        expired = await redis_client.get_expired_agents(time.time() + 700)
        assert agent_id not in expired
    
    @pytest.mark.asyncio
    async def test_get_expired_agents(self, redis_client: RedisClient):
        """Test getting expired agents."""
        current_time = time.time()
        
        # Add agents with different expiration times
        agent1 = "agent_1"
        agent2 = "agent_2"
        agent3 = "agent_3"
        
        await redis_client.add_agent_timeout(agent1, current_time - 100)  # Expired
        await redis_client.add_agent_timeout(agent2, current_time + 100)  # Not expired
        await redis_client.add_agent_timeout(agent3, current_time - 50)   # Expired
        
        # Get expired agents
        expired = await redis_client.get_expired_agents(current_time)
        
        # Verify
        assert agent1 in expired
        assert agent3 in expired
        assert agent2 not in expired
        assert len(expired) == 2
    
    @pytest.mark.asyncio
    async def test_no_expired_agents(self, redis_client: RedisClient):
        """Test when no agents have expired."""
        current_time = time.time()
        
        # Add agent that hasn't expired
        await redis_client.add_agent_timeout("agent_1", current_time + 600)
        
        # Get expired agents
        expired = await redis_client.get_expired_agents(current_time)
        
        # Verify empty
        assert len(expired) == 0


class TestUtilityMethods:
    """Test utility methods."""
    
    @pytest.mark.asyncio
    async def test_ping(self, redis_client: RedisClient):
        """Test Redis connection ping."""
        result = await redis_client.ping()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_clear_all_data(
        self,
        redis_client: RedisClient,
        sample_agent_state: AgentState
    ):
        """Test clearing all data."""
        # Add some data
        await redis_client.save_agent_state(sample_agent_state)
        
        # Verify it exists
        state = await redis_client.get_agent_state(sample_agent_state.agent_id)
        assert state is not None
        
        # Clear all data
        await redis_client.clear_all_data()
        
        # Verify it's gone
        state = await redis_client.get_agent_state(sample_agent_state.agent_id)
        assert state is None
