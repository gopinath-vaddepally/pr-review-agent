"""
Unit tests for webhook endpoints.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import hashlib
import hmac

# Skip tests if fastapi is not installed
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from app.main import app
from app.config import settings


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_pr_monitor():
    """Mock PR Monitor."""
    with patch('app.api.webhooks.pr_monitor') as mock:
        mock.process_pr_event = AsyncMock()
        yield mock


def generate_signature(payload: bytes, secret: str) -> str:
    """Generate webhook signature."""
    return hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()


def test_webhook_endpoint_exists(client):
    """Test that webhook endpoint exists."""
    # Send a request without signature (should fail)
    response = client.post("/webhooks/azure-devops/pr", json={})
    
    # Should return 401 (unauthorized) not 404 (not found)
    assert response.status_code == 401


def test_webhook_invalid_signature(client):
    """Test webhook with invalid signature."""
    payload = {
        "eventType": "git.pullrequest.created",
        "resource": {
            "pullRequestId": 123,
            "repository": {"id": "repo-123"},
            "sourceRefName": "refs/heads/feature",
            "targetRefName": "refs/heads/main",
            "createdBy": {"displayName": "Test User"},
            "title": "Test PR",
            "creationDate": "2024-01-01T00:00:00Z"
        }
    }
    
    response = client.post(
        "/webhooks/azure-devops/pr",
        json=payload,
        headers={"X-Hub-Signature-256": "invalid_signature"}
    )
    
    assert response.status_code == 401
    assert "Invalid webhook signature" in response.json()["detail"]


def test_webhook_valid_pr_created(client, mock_pr_monitor):
    """Test webhook with valid PR created event."""
    payload = {
        "eventType": "git.pullrequest.created",
        "resource": {
            "pullRequestId": 123,
            "repository": {"id": "repo-123"},
            "sourceRefName": "refs/heads/feature",
            "targetRefName": "refs/heads/main",
            "createdBy": {"displayName": "Test User"},
            "title": "Test PR",
            "description": "Test description",
            "creationDate": "2024-01-01T00:00:00Z"
        }
    }
    
    # Generate valid signature
    import json
    payload_bytes = json.dumps(payload).encode()
    signature = generate_signature(payload_bytes, settings.webhook_secret)
    
    response = client.post(
        "/webhooks/azure-devops/pr",
        json=payload,
        headers={"X-Hub-Signature-256": signature}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert "123" in response.json()["message"]


def test_webhook_ignores_non_pr_events(client):
    """Test webhook ignores non-PR events."""
    payload = {
        "eventType": "git.push",
        "resource": {}
    }
    
    # Generate valid signature
    import json
    payload_bytes = json.dumps(payload).encode()
    signature = generate_signature(payload_bytes, settings.webhook_secret)
    
    response = client.post(
        "/webhooks/azure-devops/pr",
        json=payload,
        headers={"X-Hub-Signature-256": signature}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_webhook_missing_required_fields(client):
    """Test webhook with missing required fields."""
    payload = {
        "eventType": "git.pullrequest.created",
        "resource": {
            # Missing pullRequestId and repository
            "sourceRefName": "refs/heads/feature",
            "targetRefName": "refs/heads/main"
        }
    }
    
    # Generate valid signature
    import json
    payload_bytes = json.dumps(payload).encode()
    signature = generate_signature(payload_bytes, settings.webhook_secret)
    
    response = client.post(
        "/webhooks/azure-devops/pr",
        json=payload,
        headers={"X-Hub-Signature-256": signature}
    )
    
    assert response.status_code == 400
    assert "Invalid PR event payload" in response.json()["detail"]
