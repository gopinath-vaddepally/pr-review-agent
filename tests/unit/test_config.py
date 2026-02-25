"""
Unit tests for configuration management.
"""

import pytest
from unittest.mock import patch
import os


def test_settings_loads_from_environment():
    """Test that settings can be loaded from environment variables."""
    with patch.dict(os.environ, {
        'DATABASE_URL': 'mysql+aiomysql://test:test@localhost:3306/test',
        'REDIS_URL': 'redis://localhost:6379/0',
        'AZURE_DEVOPS_PAT': 'test_pat',
        'AZURE_DEVOPS_ORG': 'test_org',
        'OPENAI_API_KEY': 'test_key',
        'WEBHOOK_SECRET': 'test_secret',
        'LOG_LEVEL': 'DEBUG',
        'AGENT_TIMEOUT_SECONDS': '300',
    }):
        from app.config import Settings
        settings = Settings()
        
        assert settings.database_url == 'mysql+aiomysql://test:test@localhost:3306/test'
        assert settings.redis_url == 'redis://localhost:6379/0'
        assert settings.azure_devops_pat == 'test_pat'
        assert settings.azure_devops_org == 'test_org'
        assert settings.openai_api_key == 'test_key'
        assert settings.webhook_secret == 'test_secret'
        assert settings.log_level == 'DEBUG'
        assert settings.agent_timeout_seconds == 300


def test_settings_has_default_values():
    """Test that settings have appropriate default values."""
    with patch.dict(os.environ, {
        'DATABASE_URL': 'mysql+aiomysql://test:test@localhost:3306/test',
        'REDIS_URL': 'redis://localhost:6379/0',
        'AZURE_DEVOPS_PAT': 'test_pat',
        'AZURE_DEVOPS_ORG': 'test_org',
        'OPENAI_API_KEY': 'test_key',
        'WEBHOOK_SECRET': 'test_secret',
    }):
        from app.config import Settings
        settings = Settings()
        
        assert settings.log_level == 'INFO'
        assert settings.agent_timeout_seconds == 600
        assert settings.max_workers == 3
