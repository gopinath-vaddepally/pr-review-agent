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
    
    This now does REAL PR review:
    1. Receive webhook
    2. Fetch PR code from Azure DevOps
    3. Analyze with OpenAI
    4. Post comments back to PR
    """
    try:
        # Get payload
        payload = await request.json()
        
        event_type = payload.get('eventType', 'unknown')
        logger.info(f"========================================")
        logger.info(f"📥 Received webhook: {event_type}")
        logger.info(f"========================================")
        
        # Extract PR info
        resource = payload.get("resource", {})
        pr_id = resource.get("pullRequestId")
        repository = resource.get("repository", {})
        repository_id = repository.get("id")
        project = repository.get("project", {})
        project_id = project.get("id")
        
        pr_title = resource.get("title", "")
        author = resource.get("createdBy", {}).get("displayName", "unknown")
        source_branch = resource.get("sourceRefName", "").replace("refs/heads/", "")
        target_branch = resource.get("targetRefName", "").replace("refs/heads/", "")
        
        logger.info(f"PR ID: {pr_id}")
        logger.info(f"Title: {pr_title}")
        logger.info(f"Author: {author}")
        logger.info(f"Branch: {source_branch} -> {target_branch}")
        logger.info(f"Repository ID: {repository_id}")
        logger.info(f"Project ID: {project_id}")
        
        if not pr_id or not repository_id:
            logger.error("Missing PR ID or repository ID in webhook payload")
            raise HTTPException(status_code=400, detail="Invalid webhook payload")
        
        # Start real review in background
        logger.info(f"🚀 Starting PR review in background...")
        background_tasks.add_task(
            review_pr_background,
            repository_id,
            pr_id,
            project_id,
            pr_title
        )
        
        return {
            "status": "accepted",
            "message": f"PR {pr_id} accepted for review",
            "pr_id": pr_id,
            "title": pr_title,
            "note": "Review is running in background. Check logs for progress."
        }
        
    except Exception as e:
        logger.error(f"❌ Error handling webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def review_pr_background(repository_id: str, pr_id: int, project_id: str, pr_title: str):
    """Background task to review PR."""
    try:
        logger.info(f"")
        logger.info(f"========================================")
        logger.info(f"🔍 Starting PR Review")
        logger.info(f"========================================")
        logger.info(f"PR ID: {pr_id}")
        logger.info(f"Title: {pr_title}")
        logger.info(f"")
        
        from app.real_review import PRReviewer
        
        reviewer = PRReviewer()
        await reviewer.review_pr(repository_id, pr_id, project_id)
        
        logger.info(f"")
        logger.info(f"========================================")
        logger.info(f"✅ PR Review Complete!")
        logger.info(f"========================================")
        logger.info(f"")
        
    except Exception as e:
        logger.error(f"")
        logger.error(f"========================================")
        logger.error(f"❌ PR Review Failed")
        logger.error(f"========================================")
        logger.error(f"Error: {e}", exc_info=True)
        logger.error(f"")


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
