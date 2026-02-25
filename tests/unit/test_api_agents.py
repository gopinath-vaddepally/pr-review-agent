"""
Unit tests for agent monitoring API endpoints.
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

# Skip tests if fastapi is not installed
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.models.agent import AgentInfo, AgentStatus


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_orchestrator():
    """Mock agent orchestrator."""
    with patch('app.api.agents.agent_orchestrator') as mock:
        yield mock


@pytest.fixture
def api_headers():
    """API headers with valid API key."""
    api_key = getattr(settings, 'admin_api_key', settings.webhook_secret)
    return {"X-API-Key": api_key}


def test_list_agents_requires_auth(client):
    """Test that listing agents requires authentication."""
    response = client.get("/api/agents")
    assert response.status_code == 401


def test_list_agents_success(client, mock_orchestrator, api_headers):
    """Test successful agent listing."""
    mock_agents = [
        AgentInfo(
            agent_id="agent-1",
            pr_id="123",
            status=AgentStatus.RUNNING,
            phase="line_analysis",
            start_time=datetime.now(),
            elapsed_seconds=45.5
        )
    ]
    
    mock_orchestrator.list_active_agents = AsyncMock(return_value=mock_agents)
    
    response = client.get("/api/agents", headers=api_headers)
    
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["agent_id"] == "agent-1"
    assert response.json()[0]["status"] == "running"


def test_get_agent_status_requires_auth(client):
    """Test that getting agent status requires authentication."""
    response = client.get("/api/agents/agent-1")
    assert response.status_code == 401


def test_get_agent_status_success(client, mock_orchestrator, api_headers):
    """Test successful agent status retrieval."""
    mock_agent = AgentInfo(
        agent_id="agent-1",
        pr_id="123",
        status=AgentStatus.RUNNING,
        phase="line_analysis",
        start_time=datetime.now(),
        elapsed_seconds=45.5
    )
    
    mock_orchestrator.get_agent_info = AsyncMock(return_value=mock_agent)
    
    response = client.get("/api/agents/agent-1", headers=api_headers)
    
    assert response.status_code == 200
    assert response.json()["agent_id"] == "agent-1"
    assert response.json()["pr_id"] == "123"


def test_get_agent_status_not_found(client, mock_orchestrator, api_headers):
    """Test getting status of non-existent agent."""
    mock_orchestrator.get_agent_info = AsyncMock(return_value=None)
    
    response = client.get("/api/agents/agent-999", headers=api_headers)
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
