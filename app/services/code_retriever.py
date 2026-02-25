"""
Code Retriever component for Azure DevOps integration.

This module provides functionality to retrieve code changes and file content
from Azure DevOps pull requests using the Azure DevOps Python SDK.
"""

import asyncio
import time
from typing import List, Optional
from azure.devops.connection import Connection
from azure.devops.v7_1.git import GitClient
from azure.devops.v7_1.git.models import (
    GitPullRequest,
    GitPullRequestChange,
    GitVersionDescriptor,
)
from msrest.authentication import BasicAuthentication

from app.models.file_change import FileChange, LineChange, ChangeType
from app.models.pr_event import PRMetadata
from app.utils.logging import get_logger, log_api_call
from app.utils.resilience import CircuitBreaker, create_azure_devops_circuit_breaker


logger = get_logger(__name__)


class CodeRetrieverError(Exception):
    """Base exception for Code Retriever errors."""
    pass


class TransientError(CodeRetrieverError):
    """Transient error that may succeed on retry."""
    pass


class PermanentError(CodeRetrieverError):
    """Permanent error that won't succeed on retry."""
    pass


class CodeRetriever:
    """
    Retrieves code changes and file content from Azure DevOps.
    
    This component uses the Azure DevOps Python SDK to:
    - Retrieve complete PR diff with line-level change information
    - Fetch file content from both source and target branches
    - Get PR metadata (branches, author, title, description, commit IDs)
    - Handle binary files gracefully (skip analysis)
    - Implement retry logic for transient failures
    """

    def __init__(
        self,
        organization_url: str,
        personal_access_token: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        """
        Initialize Code Retriever with Azure DevOps connection.
        
        Args:
            organization_url: Azure DevOps organization URL
            personal_access_token: PAT for authentication
            max_retries: Maximum number of retry attempts for transient failures
            base_delay: Base delay in seconds for exponential backoff
            max_delay: Maximum delay in seconds between retries
            circuit_breaker: Optional CircuitBreaker instance for fault tolerance
        """
        self.organization_url = organization_url
        self.pat = personal_access_token
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        
        # Initialize circuit breaker
        self.circuit_breaker = circuit_breaker or create_azure_devops_circuit_breaker()
        
        # Initialize Azure DevOps connection
        credentials = BasicAuthentication('', self.pat)
        self.connection = Connection(base_url=self.organization_url, creds=credentials)
        self.git_client: GitClient = self.connection.clients.get_git_client()
        
        logger.info(f"CodeRetriever initialized for organization: {self.organization_url}")

    async def _retry_with_backoff(self, func, *args, **kwargs):
        """
        Execute function with exponential backoff retry logic and circuit breaker.
        
        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Function result
            
        Raises:
            TransientError: If all retries are exhausted
            PermanentError: If a permanent error occurs
        """
        async def _execute():
            # Run synchronous Azure DevOps SDK calls in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
        
        last_exception = None
        start_time = time.time()
        
        for attempt in range(self.max_retries):
            try:
                # Execute with circuit breaker protection
                result = await self.circuit_breaker.call(_execute)
                
                # Log successful API call
                duration_ms = (time.time() - start_time) * 1000
                log_api_call(
                    logger,
                    service="azure_devops",
                    endpoint=func.__name__,
                    method="GET",
                    status_code=200,
                    duration_ms=duration_ms
                )
                
                if attempt > 0:
                    logger.info(f"Retry succeeded on attempt {attempt + 1}")
                
                return result
                
            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()
                
                # Check if error is permanent
                if any(keyword in error_msg for keyword in ['unauthorized', 'forbidden', 'not found', 'invalid']):
                    duration_ms = (time.time() - start_time) * 1000
                    log_api_call(
                        logger,
                        service="azure_devops",
                        endpoint=func.__name__,
                        method="GET",
                        status_code=None,
                        duration_ms=duration_ms,
                        error=str(e)
                    )
                    logger.error(f"Permanent error: {e}")
                    raise PermanentError(f"Permanent error: {e}") from e
                
                # Transient error - retry with backoff
                if attempt < self.max_retries - 1:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    duration_ms = (time.time() - start_time) * 1000
                    log_api_call(
                        logger,
                        service="azure_devops",
                        endpoint=func.__name__,
                        method="GET",
                        status_code=None,
                        duration_ms=duration_ms,
                        error=str(e)
                    )
                    logger.error(f"All {self.max_retries} retry attempts exhausted")
        
        raise TransientError(f"Failed after {self.max_retries} attempts: {last_exception}") from last_exception

    async def get_pr_metadata(self, repository_id: str, pr_id: int) -> PRMetadata:
        """
        Retrieve PR metadata including branches, author, and commit IDs.
        
        Args:
            repository_id: Azure DevOps repository ID
            pr_id: Pull request ID
            
        Returns:
            PRMetadata object with complete PR information
            
        Raises:
            PermanentError: If PR not found or invalid parameters
            TransientError: If API call fails after retries
        """
        logger.info(f"Retrieving PR metadata for PR {pr_id} in repository {repository_id}")
        
        try:
            pr: GitPullRequest = await self._retry_with_backoff(
                self.git_client.get_pull_request,
                repository_id=repository_id,
                pull_request_id=pr_id
            )
            
            metadata = PRMetadata(
                pr_id=str(pr.pull_request_id),
                repository_id=repository_id,
                source_branch=pr.source_ref_name.replace('refs/heads/', ''),
                target_branch=pr.target_ref_name.replace('refs/heads/', ''),
                author=pr.created_by.display_name,
                title=pr.title,
                description=pr.description,
                source_commit_id=pr.last_merge_source_commit.commit_id,
                target_commit_id=pr.last_merge_target_commit.commit_id,
            )
            
            logger.info(
                f"Retrieved PR metadata: {metadata.title} "
                f"({metadata.source_branch} -> {metadata.target_branch})"
            )
            
            return metadata
            
        except (PermanentError, TransientError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error retrieving PR metadata: {e}")
            raise CodeRetrieverError(f"Failed to retrieve PR metadata: {e}") from e

    async def get_pr_diff(self, repository_id: str, pr_id: int) -> List[FileChange]:
        """
        Retrieve complete diff for all changed files with line-level information.
        
        Args:
            repository_id: Azure DevOps repository ID
            pr_id: Pull request ID
            
        Returns:
            List of FileChange objects with line-level diffs
            
        Raises:
            PermanentError: If PR not found or invalid parameters
            TransientError: If API call fails after retries
        """
        logger.info(f"Retrieving PR diff for PR {pr_id} in repository {repository_id}")
        
        try:
            # Get PR metadata first to get commit IDs
            pr_metadata = await self.get_pr_metadata(repository_id, pr_id)
            
            # Get PR changes (file-level)
            changes = await self._retry_with_backoff(
                self.git_client.get_pull_request_commits,
                repository_id=repository_id,
                pull_request_id=pr_id
            )
            
            # Get detailed changes with diffs
            pr_changes = await self._retry_with_backoff(
                self.git_client.get_pull_request_iteration_changes,
                repository_id=repository_id,
                pull_request_id=pr_id,
                iteration_id=1  # First iteration contains all changes
            )
            
            file_changes = []
            
            for change in pr_changes.change_entries:
                # Skip binary files
                if self._is_binary_file(change.item.path if change.item else ''):
                    logger.info(f"Skipping binary file: {change.item.path}")
                    continue
                
                # Determine change type
                change_type = self._map_change_type(change.change_type)
                
                # Get file content for source and target
                source_content = None
                target_content = None
                
                if change_type in [ChangeType.EDIT, ChangeType.DELETE]:
                    source_content = await self.get_file_content(
                        repository_id=repository_id,
                        file_path=change.item.path,
                        commit_id=pr_metadata.target_commit_id
                    )
                
                if change_type in [ChangeType.ADD, ChangeType.EDIT]:
                    target_content = await self.get_file_content(
                        repository_id=repository_id,
                        file_path=change.item.path,
                        commit_id=pr_metadata.source_commit_id
                    )
                
                # Parse line-level changes
                added_lines, modified_lines, deleted_lines = self._parse_line_changes(
                    source_content=source_content,
                    target_content=target_content,
                    change_type=change_type
                )
                
                file_change = FileChange(
                    file_path=change.item.path if change.item else '',
                    change_type=change_type,
                    added_lines=added_lines,
                    modified_lines=modified_lines,
                    deleted_lines=deleted_lines,
                    source_content=source_content,
                    target_content=target_content,
                )
                
                file_changes.append(file_change)
                logger.debug(
                    f"Processed file: {file_change.file_path} "
                    f"(+{len(added_lines)} ~{len(modified_lines)} -{len(deleted_lines)})"
                )
            
            logger.info(f"Retrieved {len(file_changes)} file changes for PR {pr_id}")
            return file_changes
            
        except (PermanentError, TransientError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error retrieving PR diff: {e}")
            raise CodeRetrieverError(f"Failed to retrieve PR diff: {e}") from e

    async def get_file_content(
        self,
        repository_id: str,
        file_path: str,
        commit_id: str
    ) -> Optional[str]:
        """
        Retrieve file content at specific commit.
        
        Args:
            repository_id: Azure DevOps repository ID
            file_path: Path to file in repository
            commit_id: Commit ID to retrieve file from
            
        Returns:
            File content as string, or None if file doesn't exist or is binary
            
        Raises:
            TransientError: If API call fails after retries
        """
        logger.debug(f"Retrieving file content: {file_path} at commit {commit_id[:8]}")
        
        try:
            # Skip binary files
            if self._is_binary_file(file_path):
                logger.debug(f"Skipping binary file: {file_path}")
                return None
            
            # Get file content
            content_stream = await self._retry_with_backoff(
                self.git_client.get_item_content,
                repository_id=repository_id,
                path=file_path,
                version_descriptor=GitVersionDescriptor(
                    version=commit_id,
                    version_type="commit"
                )
            )
            
            # Read content from stream
            content = b''.join(content_stream).decode('utf-8', errors='ignore')
            
            logger.debug(f"Retrieved {len(content)} bytes for {file_path}")
            return content
            
        except Exception as e:
            # File might not exist in this commit (e.g., newly added or deleted)
            logger.warning(f"Could not retrieve file content for {file_path}: {e}")
            return None

    def _is_binary_file(self, file_path: str) -> bool:
        """
        Check if file is binary based on extension.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if file is binary, False otherwise
        """
        binary_extensions = {
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg',
            '.pdf', '.zip', '.tar', '.gz', '.rar', '.7z',
            '.exe', '.dll', '.so', '.dylib',
            '.class', '.jar', '.war',
            '.woff', '.woff2', '.ttf', '.eot',
        }
        
        return any(file_path.lower().endswith(ext) for ext in binary_extensions)

    def _map_change_type(self, azure_change_type: str) -> ChangeType:
        """
        Map Azure DevOps change type to internal ChangeType enum.
        
        Args:
            azure_change_type: Azure DevOps change type string
            
        Returns:
            ChangeType enum value
        """
        # Azure DevOps change types: add, edit, delete, rename, etc.
        change_type_str = str(azure_change_type).lower()
        
        if 'add' in change_type_str:
            return ChangeType.ADD
        elif 'delete' in change_type_str:
            return ChangeType.DELETE
        else:
            return ChangeType.EDIT

    def _parse_line_changes(
        self,
        source_content: Optional[str],
        target_content: Optional[str],
        change_type: ChangeType
    ) -> tuple[List[LineChange], List[LineChange], List[LineChange]]:
        """
        Parse line-level changes between source and target content.
        
        This is a simplified implementation that identifies added, modified,
        and deleted lines by comparing source and target content line by line.
        
        Args:
            source_content: Original file content (before changes)
            target_content: Modified file content (after changes)
            change_type: Type of file change
            
        Returns:
            Tuple of (added_lines, modified_lines, deleted_lines)
        """
        added_lines = []
        modified_lines = []
        deleted_lines = []
        
        # Handle file addition
        if change_type == ChangeType.ADD and target_content:
            for line_num, line in enumerate(target_content.splitlines(), start=1):
                added_lines.append(LineChange(
                    line_number=line_num,
                    change_type=ChangeType.ADD,
                    content=line
                ))
            return added_lines, modified_lines, deleted_lines
        
        # Handle file deletion
        if change_type == ChangeType.DELETE and source_content:
            for line_num, line in enumerate(source_content.splitlines(), start=1):
                deleted_lines.append(LineChange(
                    line_number=line_num,
                    change_type=ChangeType.DELETE,
                    content=line
                ))
            return added_lines, modified_lines, deleted_lines
        
        # Handle file modification
        if change_type == ChangeType.EDIT and source_content and target_content:
            source_lines = source_content.splitlines()
            target_lines = target_content.splitlines()
            
            # Simple line-by-line comparison
            # In production, use a proper diff algorithm (e.g., difflib)
            max_lines = max(len(source_lines), len(target_lines))
            
            for i in range(max_lines):
                source_line = source_lines[i] if i < len(source_lines) else None
                target_line = target_lines[i] if i < len(target_lines) else None
                
                if source_line is None and target_line is not None:
                    # Line added
                    added_lines.append(LineChange(
                        line_number=i + 1,
                        change_type=ChangeType.ADD,
                        content=target_line
                    ))
                elif source_line is not None and target_line is None:
                    # Line deleted
                    deleted_lines.append(LineChange(
                        line_number=i + 1,
                        change_type=ChangeType.DELETE,
                        content=source_line
                    ))
                elif source_line != target_line:
                    # Line modified
                    modified_lines.append(LineChange(
                        line_number=i + 1,
                        change_type=ChangeType.EDIT,
                        content=target_line
                    ))
        
        return added_lines, modified_lines, deleted_lines



def get_code_retriever() -> CodeRetriever:
    """
    Factory function to create CodeRetriever with settings from config.
    
    Returns:
        CodeRetriever instance configured with application settings
    """
    from app.config import settings
    
    return CodeRetriever(
        organization_url=f"https://dev.azure.com/{settings.azure_devops_org}",
        personal_access_token=settings.azure_devops_pat
    )
