"""
PR Monitor component.

Processes PR events from webhooks, validates repository monitoring,
manages agent lifecycle, and handles service hook registration.
"""

import asyncio
from typing import Optional
from azure.devops.connection import Connection
from azure.devops.v7_0.service_hooks.models import Subscription, SubscriptionInputValues
from msrest.authentication import BasicAuthentication

from app.models.pr_event import PREvent, PRMetadata
from app.services.repository_config import RepositoryConfigService
from app.services.redis_client import RedisClient
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.code_retriever import CodeRetriever
from app.config import settings
from app.utils.logging import get_logger, log_pr_event

logger = get_logger(__name__)


class PRMonitor:
    """Monitors PR events and orchestrates review agent lifecycle."""
    
    def __init__(self):
        """Initialize the PR Monitor."""
        self.repo_config = RepositoryConfigService()
        self.redis_client = RedisClient()
        self.orchestrator = AgentOrchestrator()
        self.code_retriever = CodeRetriever()
        
        # Azure DevOps connection for service hooks
        credentials = BasicAuthentication('', settings.azure_devops_pat)
        self._connection = Connection(
            base_url=f'https://dev.azure.com/{settings.azure_devops_org}',
            creds=credentials
        )
        self._service_hooks_client = self._connection.clients.get_service_hooks_client()
    
    async def process_pr_event(self, event: PREvent) -> None:
        """
        Process incoming PR event and spawn review agent if needed.
        
        Args:
            event: PR event from webhook
        """
        # Log PR event detection with required fields
        log_pr_event(
            logger,
            pr_id=event.pr_id,
            repository_id=event.repository_id,
            event_type=event.event_type
        )
        
        try:
            # Validate PR belongs to monitored repository
            is_monitored = await self.repo_config.is_monitored(event.repository_id)
            
            if not is_monitored:
                logger.info(f"Repository {event.repository_id} is not monitored, skipping")
                return
            
            # Check for existing agent
            existing_agent_id = await self.check_existing_agent(event.pr_id)
            
            if existing_agent_id:
                logger.info(f"Found existing agent {existing_agent_id} for PR {event.pr_id}")
                # Terminate existing agent
                await self.terminate_agent(existing_agent_id)
            
            # Get full PR metadata
            pr_metadata = await self._get_pr_metadata(event)
            
            # Enqueue review job
            await self._enqueue_review_job(event, pr_metadata)
            
            logger.info(f"PR event processed successfully for PR {event.pr_id}")
            
        except Exception as e:
            logger.error(f"Error processing PR event for PR {event.pr_id}: {e}", exc_info=True)
            raise
    
    async def register_service_hook(
        self,
        repo_id: str,
        webhook_url: str
    ) -> str:
        """
        Register Azure DevOps Service Hook for repository.
        
        Args:
            repo_id: Repository identifier
            webhook_url: Webhook URL to receive events
            
        Returns:
            Service hook ID
        """
        logger.info(f"Registering service hook for repository {repo_id}")
        
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Create subscription for PR events
                subscription = Subscription(
                    publisher_id="tfs",
                    event_type="git.pullrequest.created",
                    resource_version="1.0",
                    consumer_id="webHooks",
                    consumer_action_id="httpRequest",
                    consumer_inputs=SubscriptionInputValues(
                        url=webhook_url
                    ),
                    publisher_inputs=SubscriptionInputValues(
                        repository=repo_id,
                        branch=""  # All branches
                    )
                )
                
                # Create subscription via Azure DevOps API
                created_subscription = await asyncio.to_thread(
                    self._service_hooks_client.create_subscription,
                    subscription
                )
                
                hook_id = created_subscription.id
                logger.info(f"Service hook registered successfully: {hook_id}")
                
                return hook_id
                
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to register service hook after {max_retries} attempts: {e}")
                    raise
                
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
    
    async def unregister_service_hook(self, hook_id: str) -> None:
        """
        Unregister Azure DevOps Service Hook.
        
        Args:
            hook_id: Service hook ID to unregister
        """
        logger.info(f"Unregistering service hook {hook_id}")
        
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Delete subscription via Azure DevOps API
                await asyncio.to_thread(
                    self._service_hooks_client.delete_subscription,
                    hook_id
                )
                
                logger.info(f"Service hook {hook_id} unregistered successfully")
                return
                
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to unregister service hook after {max_retries} attempts: {e}")
                    raise
                
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
    
    async def check_existing_agent(self, pr_id: str) -> Optional[str]:
        """
        Check if agent already exists for PR.
        
        Args:
            pr_id: Pull request ID
            
        Returns:
            Agent ID if exists, None otherwise
        """
        try:
            agent_ids = await self.redis_client.get_active_agents_for_pr(pr_id)
            
            if agent_ids:
                # Return the first active agent
                return agent_ids[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking existing agent for PR {pr_id}: {e}")
            return None
    
    async def terminate_agent(self, agent_id: str) -> None:
        """
        Terminate existing agent instance.
        
        Args:
            agent_id: Agent identifier
        """
        try:
            await self.orchestrator.terminate_agent(
                agent_id,
                reason="New PR update received"
            )
            logger.info(f"Terminated agent {agent_id}")
            
        except Exception as e:
            logger.error(f"Error terminating agent {agent_id}: {e}")
    
    async def _get_pr_metadata(self, event: PREvent) -> PRMetadata:
        """
        Get full PR metadata from Azure DevOps.
        
        Args:
            event: PR event
            
        Returns:
            Complete PR metadata
        """
        try:
            # Use code retriever to get PR metadata
            metadata = await self.code_retriever.get_pr_metadata(event.pr_id)
            return metadata
            
        except Exception as e:
            logger.error(f"Error retrieving PR metadata for {event.pr_id}: {e}")
            
            # Fallback to event data
            return PRMetadata(
                pr_id=event.pr_id,
                repository_id=event.repository_id,
                source_branch=event.source_branch,
                target_branch=event.target_branch,
                author=event.author,
                title=event.title,
                description=event.description,
                source_commit_id="",
                target_commit_id=""
            )
    
    async def _enqueue_review_job(
        self,
        event: PREvent,
        pr_metadata: PRMetadata
    ) -> None:
        """
        Enqueue review job to Redis job queue.
        
        Args:
            event: PR event
            pr_metadata: PR metadata
        """
        try:
            # Create job payload
            job_payload = {
                "pr_id": event.pr_id,
                "repository_id": event.repository_id,
                "pr_metadata": pr_metadata.model_dump(),
                "timestamp": event.timestamp.isoformat()
            }
            
            # Enqueue to Redis
            await self.redis_client.enqueue_review_job(job_payload)
            
            logger.info(f"Review job enqueued for PR {event.pr_id}")
            
        except Exception as e:
            logger.error(f"Error enqueuing review job for PR {event.pr_id}: {e}")
            raise
