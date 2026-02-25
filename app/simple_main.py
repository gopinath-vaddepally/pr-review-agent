"""
Simplified FastAPI application for local testing without Docker.
This version works without MySQL and Redis for quick testing.
"""

import logging
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Azure DevOps PR Review Agent (Local)",
    description="Simplified version for local testing",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory storage
repositories = []
active_agents = []


class Repository(BaseModel):
    repository_url: str
    webhook_url: Optional[str] = None


class PREvent(BaseModel):
    pr_id: str
    repository_id: str
    source_branch: str
    target_branch: str
    author: str
    title: str


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Azure DevOps PR Review Agent API (Local Mode)",
        "version": "0.1.0",
        "mode": "local",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "mode": "local",
        "database": "in-memory",
        "redis": "disabled"
    }


@app.post("/api/repositories")
async def add_repository(repo: Repository):
    """Add repository to monitoring."""
    logger.info(f"Adding repository: {repo.repository_url}")
    
    # Simple validation
    if not repo.repository_url.startswith("https://dev.azure.com/"):
        raise HTTPException(status_code=400, detail="Invalid Azure DevOps URL")
    
    # Store in memory
    repo_dict = repo.dict()
    repo_dict["id"] = f"repo-{len(repositories) + 1}"
    repositories.append(repo_dict)
    
    logger.info(f"Repository added: {repo_dict['id']}")
    
    return {
        "id": repo_dict["id"],
        "repository_url": repo.repository_url,
        "webhook_url": repo.webhook_url,
        "status": "registered",
        "message": "Repository registered successfully. In local mode, webhook registration is simulated."
    }


@app.get("/api/repositories")
async def list_repositories():
    """List all monitored repositories."""
    return repositories


@app.get("/api/agents")
async def list_agents():
    """List active agents."""
    return active_agents


@app.post("/webhooks/azure-devops/pr")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle Azure DevOps PR webhook.
    
    In local mode, this simulates the full workflow:
    1. Receive webhook
    2. Parse PR event
    3. Simulate agent execution
    4. Return success
    """
    try:
        # Get payload
        payload = await request.json()
        
        logger.info(f"Received webhook: {payload.get('eventType', 'unknown')}")
        
        # Extract PR info
        resource = payload.get("resource", {})
        pr_id = str(resource.get("pullRequestId", "unknown"))
        repository = resource.get("repository", {})
        
        # Create PR event
        pr_event = {
            "pr_id": pr_id,
            "repository_id": repository.get("id", "unknown"),
            "source_branch": resource.get("sourceRefName", "").replace("refs/heads/", ""),
            "target_branch": resource.get("targetRefName", "").replace("refs/heads/", ""),
            "author": resource.get("createdBy", {}).get("displayName", "unknown"),
            "title": resource.get("title", ""),
        }
        
        logger.info(f"Processing PR {pr_id}: {pr_event['title']}")
        
        # Simulate agent execution in background
        background_tasks.add_task(simulate_agent_execution, pr_event)
        
        return {
            "status": "accepted",
            "message": f"PR event for {pr_id} accepted for processing",
            "pr_id": pr_id,
            "mode": "local",
            "note": "In local mode, agent execution is simulated. Check logs for details."
        }
        
    except Exception as e:
        logger.error(f"Error handling webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def simulate_agent_execution(pr_event: dict):
    """
    Simulate agent execution for local testing.
    
    In a real deployment, this would:
    1. Retrieve code from Azure DevOps
    2. Parse files with language plugins
    3. Analyze code with LLM
    4. Post comments back to PR
    """
    pr_id = pr_event["pr_id"]
    
    logger.info(f"[Agent] Starting analysis for PR {pr_id}")
    
    # Simulate phases
    phases = [
        "initialize",
        "retrieve_code",
        "parse_files",
        "line_analysis",
        "architecture_analysis",
        "generate_comments",
        "publish_comments"
    ]
    
    for phase in phases:
        logger.info(f"[Agent] PR {pr_id} - Phase: {phase}")
        # In real implementation, each phase would do actual work
    
    logger.info(f"[Agent] PR {pr_id} - Analysis complete")
    logger.info(f"[Agent] PR {pr_id} - In local mode, comments are not posted to Azure DevOps")
    logger.info(f"[Agent] PR {pr_id} - To enable full functionality, use Docker deployment with MySQL and Redis")


@app.post("/test/simulate-pr")
async def simulate_pr(pr_id: str = "12345", title: str = "Test PR"):
    """
    Test endpoint to simulate a PR webhook without Azure DevOps.
    
    Usage:
    curl -X POST "http://localhost:8000/test/simulate-pr?pr_id=123&title=My+Test+PR"
    """
    logger.info(f"Simulating PR webhook for PR {pr_id}")
    
    # Process like a real webhook
    pr_event = {
        "pr_id": pr_id,
        "repository_id": "test-repo-123",
        "source_branch": "feature/test",
        "target_branch": "main",
        "author": "Test User",
        "title": title,
    }
    
    await simulate_agent_execution(pr_event)
    
    return {
        "status": "success",
        "message": f"Simulated PR {pr_id} processing complete",
        "note": "Check logs to see the simulated agent execution"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
