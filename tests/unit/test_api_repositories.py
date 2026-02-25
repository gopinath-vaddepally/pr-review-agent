"""
Unit tests for repository management API endpoints.
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

# Skip tests if fastapi is not installed
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.models.repository import Repository


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_repo_service():
    """Mock repository config service."""
    with patch('app.api.repositories.repo_config_service') as mock:
        yield mock


@pytest.fixture
def api_headers():
    """API headers with valid API key."""
    api_key = getattr(settings, 'admin_api_key', settings.webhook_secret)
    return {"X-API-Key": api_key}


def test_list_repositories_requires_auth(client):
    """Test that listing repositories requires authentication."""
    response = client.get("/api/repositories")
    assert response.status_code == 401


def test_list_repositories_success(client, mock_repo_service, api_headers):
    """Test successful repository listing."""
    # Mock repository data
    mock_repos = [
        Repository(
            id="repo-1",
            organization="org",
            project="project",
            repository_name="repo1",
            repository_url="https://dev.azure.com/org/project/_git/repo1",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    ]
    
    mock_repo_service.list_repositories = AsyncMock(return_value=mock_repos)
    
    response = client.get("/api/repositories", headers=api_headers)
    
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["repository_name"] == "repo1"


def test_add_repository_requires_auth(client):
    """Test that adding repository requires authentication."""
    response = client.post(
        "/api/repositories",
        json={"repository_url": "https://dev.azure.com/org/project/_git/repo"}
    )
    assert response.status_code == 401


def test_add_repository_success(client, mock_repo_service, api_headers):
    """Test successful repository addition."""
    mock_repo = Repository(
        id="repo-1",
        organization="org",
        project="project",
        repository_name="repo",
        repository_url="https://dev.azure.com/org/project/_git/repo",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    mock_repo_service.add_repository = AsyncMock(return_value=mock_repo)
    
    response = client.post(
        "/api/repositories",
        json={"repository_url": "https://dev.azure.com/org/project/_git/repo"},
        headers=api_headers
    )
    
    assert response.status_code == 200
    assert response.json()["repository_name"] == "repo"


def test_remove_repository_requires_auth(client):
    """Test that removing repository requires authentication."""
    response = client.delete("/api/repositories/repo-1")
    assert response.status_code == 401


def test_remove_repository_success(client, mock_repo_service, api_headers):
    """Test successful repository removal."""
    mock_repo_service.remove_repository = AsyncMock()
    
    response = client.delete("/api/repositories/repo-1", headers=api_headers)
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_remove_repository_not_found(client, mock_repo_service, api_headers):
    """Test removing non-existent repository."""
    mock_repo_service.remove_repository = AsyncMock(
        side_effect=ValueError("Repository not found")
    )
    
    response = client.delete("/api/repositories/repo-999", headers=api_headers)
    
    assert response.status_code == 404
