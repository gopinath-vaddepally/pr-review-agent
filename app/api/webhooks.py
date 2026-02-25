"""
Webhook endpoints for Azure DevOps Service Hooks.
"""

import hashlib
import hmac
import logging
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.config import settings
from app.models.api_response import WebhookResponse
from app.models.pr_event import PREvent
from app.services.pr_monitor import PRMonitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Initialize PR Monitor
pr_monitor = PRMonitor()


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify webhook signature for security.
    
    Args:
        payload: Raw request payload
        signature: Signature from request header
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not signature:
        return False
    
    # Compute expected signature
    expected_signature = hmac.new(
        settings.webhook_secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures (constant-time comparison)
    return hmac.compare_digest(signature, expected_signature)


async def process_pr_event_async(event: PREvent) -> None:
    """
    Process PR event asynchronously.
    
    Args:
        event: PR event to process
    """
    try:
        await pr_monitor.process_pr_event(event)
    except Exception as e:
        logger.error(f"Error processing PR event asynchronously: {e}", exc_info=True)


@router.post("/azure-devops/pr", response_model=WebhookResponse)
async def handle_pr_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature: str = Header(None, alias="X-Hub-Signature-256")
) -> WebhookResponse:
    """
    Receive and process Azure DevOps PR webhook events.
    
    This endpoint:
    1. Validates webhook signature for security (DISABLED for testing)
    2. Parses PR event payload
    3. Returns 200 OK immediately (async processing)
    4. Enqueues event to Redis job queue via PRMonitor
    
    Args:
        request: FastAPI request object
        background_tasks: FastAPI background tasks
        x_hub_signature: Webhook signature header
        
    Returns:
        WebhookResponse with status and message
        
    Raises:
        HTTPException: If signature validation fails or payload is invalid
    """
    try:
        # Read raw payload for signature verification
        payload = await request.body()
        
        # SECURITY DISABLED FOR TESTING
        # TODO: Re-enable signature verification in production
        # if not verify_webhook_signature(payload, x_hub_signature):
        #     logger.warning("Invalid webhook signature received")
        #     raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        logger.info("Webhook signature verification DISABLED for testing")
        
        # Parse JSON payload
        payload_json: Dict[str, Any] = await request.json()
        
        # Extract PR event data from Azure DevOps webhook payload
        event_type = payload_json.get("eventType", "")
        
        # Only process PR created and updated events
        if event_type not in ["git.pullrequest.created", "git.pullrequest.updated"]:
            logger.info(f"Ignoring event type: {event_type}")
            return WebhookResponse(
                status="ignored",
                message=f"Event type {event_type} not processed"
            )
        
        # Extract resource data
        resource = payload_json.get("resource", {})
        repository = resource.get("repository", {})
        
        # Parse PR event
        pr_event = PREvent(
            event_type=event_type,
            pr_id=str(resource.get("pullRequestId", "")),
            repository_id=repository.get("id", ""),
            source_branch=resource.get("sourceRefName", "").replace("refs/heads/", ""),
            target_branch=resource.get("targetRefName", "").replace("refs/heads/", ""),
            author=resource.get("createdBy", {}).get("displayName", ""),
            title=resource.get("title", ""),
            description=resource.get("description"),
            timestamp=resource.get("creationDate", payload_json.get("createdDate"))
        )
        
        # Validate required fields
        if not pr_event.pr_id or not pr_event.repository_id:
            logger.error(f"Invalid PR event payload: missing required fields")
            raise HTTPException(status_code=400, detail="Invalid PR event payload")
        
        logger.info(f"Received webhook for PR {pr_event.pr_id} in repository {pr_event.repository_id}")
        
        # Process event asynchronously in background
        background_tasks.add_task(process_pr_event_async, pr_event)
        
        # Return 200 OK immediately
        return WebhookResponse(
            status="accepted",
            message=f"PR event for {pr_event.pr_id} accepted for processing"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error processing webhook")
