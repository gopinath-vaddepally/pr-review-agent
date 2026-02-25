"""
Comment Publisher component.

Posts review comments to Azure DevOps pull requests using the Azure DevOps SDK.
Handles line-level comments and summary comments with batching and retry logic.
"""

import asyncio
import time
from typing import List
from azure.devops.connection import Connection
from azure.devops.v7_0.git.models import (
    Comment,
    CommentThread,
    CommentThreadContext,
    CommentPosition
)
from msrest.authentication import BasicAuthentication

from app.models.comment import LineComment, SummaryComment
from app.models.api_response import PublishResult
from app.config import settings
from app.utils.logging import get_logger, log_api_call
from app.utils.resilience import retry_with_backoff

logger = get_logger(__name__)


class CommentPublisher:
    """Publishes review comments to Azure DevOps pull requests."""
    
    def __init__(self):
        """Initialize the Comment Publisher with Azure DevOps client."""
        credentials = BasicAuthentication('', settings.azure_devops_pat)
        self._connection = Connection(
            base_url=f'https://dev.azure.com/{settings.azure_devops_org}',
            creds=credentials
        )
        self._git_client = self._connection.clients.get_git_client()
    
    async def publish_line_comments(
        self,
        pr_id: str,
        repository_id: str,
        comments: List[LineComment]
    ) -> PublishResult:
        """
        Publish line-level comments to PR.
        
        Args:
            pr_id: Pull request ID
            repository_id: Repository ID
            comments: List of line comments to publish
            
        Returns:
            PublishResult with success status and counts
        """
        logger.info(f"Publishing {len(comments)} line comments to PR {pr_id}")
        
        published_count = 0
        failed_count = 0
        errors = []
        
        for comment in comments:
            try:
                await self._publish_single_line_comment(
                    pr_id,
                    repository_id,
                    comment
                )
                published_count += 1
                
            except Exception as e:
                logger.error(f"Failed to publish comment for {comment.file_path}:{comment.line_number}: {e}")
                failed_count += 1
                errors.append(f"{comment.file_path}:{comment.line_number} - {str(e)}")
        
        success = failed_count == 0
        logger.info(f"Published {published_count}/{len(comments)} line comments successfully")
        
        return PublishResult(
            success=success,
            published_count=published_count,
            failed_count=failed_count,
            errors=errors
        )
    
    async def publish_summary_comment(
        self,
        pr_id: str,
        repository_id: str,
        comment: SummaryComment
    ) -> PublishResult:
        """
        Publish summary comment to PR overview.
        
        Args:
            pr_id: Pull request ID
            repository_id: Repository ID
            comment: Summary comment to publish
            
        Returns:
            PublishResult with success status
        """
        logger.info(f"Publishing summary comment to PR {pr_id}")
        
        try:
            await self._publish_summary_with_retry(
                pr_id,
                repository_id,
                comment
            )
            
            logger.info("Summary comment published successfully")
            return PublishResult(
                success=True,
                published_count=1,
                failed_count=0,
                errors=[]
            )
            
        except Exception as e:
            logger.error(f"Failed to publish summary comment: {e}", exc_info=True)
            return PublishResult(
                success=False,
                published_count=0,
                failed_count=1,
                errors=[str(e)]
            )
    
    async def batch_publish(
        self,
        pr_id: str,
        repository_id: str,
        line_comments: List[LineComment],
        summary_comment: SummaryComment
    ) -> PublishResult:
        """
        Publish all comments in optimized batches.
        
        Args:
            pr_id: Pull request ID
            repository_id: Repository ID
            line_comments: List of line comments
            summary_comment: Summary comment
            
        Returns:
            Combined PublishResult
        """
        logger.info(f"Batch publishing {len(line_comments)} line comments and 1 summary comment to PR {pr_id}")
        
        # Publish line comments
        line_result = await self.publish_line_comments(pr_id, repository_id, line_comments)
        
        # Publish summary comment
        summary_result = await self.publish_summary_comment(pr_id, repository_id, summary_comment)
        
        # Combine results
        total_published = line_result.published_count + summary_result.published_count
        total_failed = line_result.failed_count + summary_result.failed_count
        all_errors = line_result.errors + summary_result.errors
        
        return PublishResult(
            success=line_result.success and summary_result.success,
            published_count=total_published,
            failed_count=total_failed,
            errors=all_errors
        )
    
    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=60.0)
    async def _publish_single_line_comment(
        self,
        pr_id: str,
        repository_id: str,
        comment: LineComment
    ) -> None:
        """
        Publish a single line comment with retry logic.
        
        Args:
            pr_id: Pull request ID
            repository_id: Repository ID
            comment: Line comment to publish
        """
        # Create comment thread context for line-level comment
        thread_context = CommentThreadContext(
            file_path=comment.file_path,
            right_file_start=CommentPosition(line=comment.line_number, offset=1),
            right_file_end=CommentPosition(line=comment.line_number, offset=1)
        )
        
        # Format comment content
        comment_content = self._format_line_comment(comment)
        
        # Create comment thread
        thread = CommentThread(
            comments=[Comment(content=comment_content)],
            status=1,  # Active
            thread_context=thread_context
        )
        
        # Publish to Azure DevOps
        await asyncio.to_thread(
            self._git_client.create_thread,
            thread,
            repository_id,
            int(pr_id),
            None  # project (optional)
        )
        
        logger.debug(f"Published comment for {comment.file_path}:{comment.line_number}")
    
    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=60.0)
    async def _publish_summary_with_retry(
        self,
        pr_id: str,
        repository_id: str,
        comment: SummaryComment
    ) -> None:
        """
        Publish summary comment with retry logic.
        
        Args:
            pr_id: Pull request ID
            repository_id: Repository ID
            comment: Summary comment to publish
        """
        # Create comment thread without file context (PR-level comment)
        thread = CommentThread(
            comments=[Comment(content=comment.message)],
            status=1  # Active
        )
        
        # Publish to Azure DevOps
        await asyncio.to_thread(
            self._git_client.create_thread,
            thread,
            repository_id,
            int(pr_id),
            None  # project (optional)
        )
        
        logger.debug("Published summary comment")
    
    def _format_line_comment(self, comment: LineComment) -> str:
        """
        Format a line comment for display in Azure DevOps.
        
        Args:
            comment: Line comment to format
            
        Returns:
            Formatted comment string
        """
        severity_emoji = {
            "error": "🔴",
            "warning": "⚠️",
            "info": "ℹ️"
        }
        
        category_label = {
            "code_smell": "Code Smell",
            "bug": "Potential Bug",
            "security": "Security Issue",
            "best_practice": "Best Practice",
            "architecture": "Architecture"
        }
        
        parts = [
            f"{severity_emoji.get(comment.severity, '•')} **{category_label.get(comment.category, 'Issue')}**",
            "",
            comment.message
        ]
        
        if comment.suggestion:
            parts.extend([
                "",
                "**Suggestion:**",
                comment.suggestion
            ])
        
        if comment.code_example:
            parts.extend([
                "",
                "**Example:**",
                "```",
                comment.code_example,
                "```"
            ])
        
        return "\n".join(parts)
