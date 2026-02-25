"""
Unit tests for FastAPI application.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import os


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    with patch.dict(os.environ, {
        'DATABASE_URL': 'mysql+aiomysql://test:test@localhost:3306/test',
        'REDIS_URL': 'redis://localhost:6379/0',
        'AZURE_DEVOPS_PAT': 'test_pat',
        'AZURE_DEVOPS_ORG': 'test_org',
        'OPENAI_API_KEY': 'test_key',
        'WEBHOOK_SECRET': 'test_secret',
    }):
        from app.main import app
        return TestClient(app)


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert data["docs"] == "/docs"
