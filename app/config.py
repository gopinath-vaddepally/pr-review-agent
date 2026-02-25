"""
Application configuration management.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str
    
    # Redis
    redis_url: str
    
    # Azure DevOps
    azure_devops_pat: str
    azure_devops_org: str
    
    # OpenAI
    openai_api_key: str
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    azure_openai_deployment: Optional[str] = None
    
    # Webhook
    webhook_secret: str
    
    # Admin API
    admin_api_key: Optional[str] = None  # Falls back to webhook_secret if not set
    
    # Application
    log_level: str = "INFO"
    agent_timeout_seconds: int = 600
    max_workers: int = 3
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
