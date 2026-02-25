"""
Worker process for job queue.

Polls Redis job queue for PR review jobs and spawns Review Agents
via AgentOrchestrator. Supports multiple worker instances for parallel
processing and implements graceful shutdown on SIGTERM.
"""

import asyncio
import json
import signal
import sys
from typing import Optional, Dict, Any

from app.services.redis_client import RedisClient
from app.services.agent_orchestrator import AgentOrchestrator
from app.models.pr_event import PRMetadata
from app.config import settings
from app.utils.logging import setup_logging, get_logger

# Configure structured logging
setup_logging(settings.log_level.upper())
logger = get_logger(__name__)


class Worker:
    """Worker process that polls Redis job queue and spawns Review Agents."""
    
    def __init__(self):
        """Initialize the worker."""
        self.redis_client = RedisClient()
        self.orchestrator = AgentOrchestrator()
        self.running = False
        self.current_job: Optional[Dict[str, Any]] = None
        self._shutdown_event = asyncio.Event()
    
    async def start(self) -> None:
        """
        Start the worker process.
        
        Initializes connections and begins polling the job queue.
        """
        logger.info("Starting worker process...")
        
        try:
            # Initialize Redis connection
            await self.redis_client.initialize()
            logger.info("Redis connection initialized")
            
            # Set running flag
            self.running = True
            
            # Register signal handlers for graceful shutdown
            self._register_signal_handlers()
            
            logger.info("Worker process started successfully")
            
            # Start processing jobs
            await self._process_jobs()
            
        except Exception as e:
            logger.error(f"Failed to start worker: {e}", exc_info=True)
            raise
    
    async def stop(self) -> None:
        """
        Stop the worker process gracefully.
        
        Finishes current job before exiting.
        """
        logger.info("Stopping worker process...")
        
        # Set running flag to False
        self.running = False
        
        # Wait for current job to complete
        if self.current_job:
            pr_id = self.current_job.get('pr_id', 'unknown')
            logger.info(f"Waiting for current job (PR {pr_id}) to complete...")
            # Give it some time to finish
            await asyncio.sleep(2)
        
        # Close Redis connection
        await self.redis_client.close()
        
        logger.info("Worker process stopped")
    
    async def _process_jobs(self) -> None:
        """
        Main job processing loop.
        
        Continuously polls Redis job queue and processes PR review jobs.
        """
        logger.info("Starting job processing loop...")
        
        while self.running:
            try:
                # Dequeue job with blocking timeout (5 seconds)
                # This allows checking the running flag periodically
                # Using blocking pop for efficient multi-worker support
                async with self.redis_client._get_client() as client:
                    result = await client.blpop(
                        self.redis_client.JOB_QUEUE_KEY,
                        timeout=5
                    )
                    
                    if result:
                        _, job_json = result
                        job_payload = json.loads(job_json)
                        
                        self.current_job = job_payload
                        await self._process_job(job_payload)
                        self.current_job = None
                
            except asyncio.CancelledError:
                logger.info("Job processing cancelled")
                break
            
            except Exception as e:
                logger.error(f"Error processing job: {e}", exc_info=True)
                # Continue processing other jobs
                await asyncio.sleep(1)
        
        logger.info("Job processing loop stopped")
    
    async def _process_job(self, job_payload: Dict[str, Any]) -> None:
        """
        Process a job by spawning a Review Agent.
        
        Args:
            job_payload: Job payload from Redis queue
        """
        pr_id = job_payload.get('pr_id')
        repository_id = job_payload.get('repository_id')
        pr_metadata_dict = job_payload.get('pr_metadata')
        
        logger.info(f"Processing job for PR {pr_id}")
        
        try:
            # Validate job payload
            if not pr_id or not repository_id or not pr_metadata_dict:
                logger.error(f"Invalid job payload: {job_payload}")
                return
            
            # Parse PR metadata
            pr_metadata = PRMetadata(**pr_metadata_dict)
            
            # Check for existing agents
            existing_agents = await self.redis_client.get_active_agents(pr_id)
            
            if existing_agents:
                logger.info(
                    f"Found {len(existing_agents)} existing agent(s) for PR {pr_id}, "
                    "terminating before spawning new agent"
                )
                
                # Terminate existing agents
                for agent_id in existing_agents:
                    try:
                        await self.orchestrator.terminate_agent(
                            agent_id,
                            "New PR update received"
                        )
                    except Exception as e:
                        logger.error(f"Failed to terminate agent {agent_id}: {e}")
            
            # Spawn new Review Agent
            agent_id = await self.orchestrator.spawn_agent(
                pr_id=pr_id,
                pr_metadata=pr_metadata,
                repository_id=repository_id
            )
            
            logger.info(
                f"Successfully spawned Review Agent {agent_id} for PR {pr_id}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to process job for PR {pr_id}: {e}",
                exc_info=True
            )
    
    def _register_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
        
        def signal_handler(signum, frame):
            """Handle shutdown signals."""
            signal_name = signal.Signals(signum).name
            logger.info(f"Received signal {signal_name}, initiating graceful shutdown...")
            
            # Set shutdown event
            asyncio.create_task(self._handle_shutdown())
        
        # Register handlers for SIGTERM and SIGINT
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        logger.info("Signal handlers registered (SIGTERM, SIGINT)")
    
    async def _handle_shutdown(self) -> None:
        """Handle graceful shutdown."""
        await self.stop()
        self._shutdown_event.set()


async def main():
    """Main entry point for worker process."""
    logger.info("Worker process starting...")
    
    worker = Worker()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Worker process failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())

