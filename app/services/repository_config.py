"""
Repository configuration service for managing monitored repositories.

This service handles CRUD operations for repository configuration in MySQL,
including URL validation and parsing of Azure DevOps repository identifiers.
"""

import re
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
import aiomysql
from contextlib import asynccontextmanager

from app.models.repository import Repository, RepositoryCreate


logger = logging.getLogger(__name__)


class RepositoryValidationError(Exception):
    """Raised when repository URL validation fails."""
    pass


class RepositoryConfigService:
    """
    Service for managing repository configuration in MySQL.
    
    Provides CRUD operations for repository monitoring configuration,
    including URL validation and Azure DevOps repository parsing.
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize the repository configuration service.
        
        Args:
            database_url: Database connection URL. If None, will load from settings.
        """
        self._pool: Optional[aiomysql.Pool] = None
        self._database_url = database_url
        self._azure_devops_url_pattern = re.compile(
            r'^https://dev\.azure\.com/(?P<org>[^/]+)/(?P<project>[^/]+)/_git/(?P<repo>[^/]+)/?$'
        )
    
    async def initialize(self) -> None:
        """
        Initialize the MySQL connection pool.
        
        Should be called during application startup.
        """
        try:
            # Get database URL from settings if not provided
            if not self._database_url:
                from app.config import settings
                self._database_url = settings.database_url
            
            # Parse database URL
            db_config = self._parse_database_url(self._database_url)
            
            # Create connection pool
            self._pool = await aiomysql.create_pool(
                host=db_config['host'],
                port=db_config['port'],
                user=db_config['user'],
                password=db_config['password'],
                db=db_config['database'],
                minsize=1,
                maxsize=10,
                autocommit=False,
                charset='utf8mb4'
            )
            
            logger.info("MySQL connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MySQL connection pool: {e}")
            raise
    
    async def close(self) -> None:
        """
        Close the MySQL connection pool.
        
        Should be called during application shutdown.
        """
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            logger.info("MySQL connection pool closed")
    
    @asynccontextmanager
    async def _get_connection(self):
        """
        Get a database connection from the pool.
        
        Yields:
            aiomysql.Connection: Database connection
        """
        if not self._pool:
            raise RuntimeError("Database pool not initialized. Call initialize() first.")
        
        async with self._pool.acquire() as conn:
            yield conn
    
    def _parse_database_url(self, url: str) -> Dict[str, Any]:
        """
        Parse database URL into connection parameters.
        
        Args:
            url: Database URL in format: mysql+aiomysql://user:pass@host:port/database
        
        Returns:
            Dictionary with connection parameters
        """
        parsed = urlparse(url)
        
        return {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 3306,
            'user': parsed.username or 'root',
            'password': parsed.password or '',
            'database': parsed.path.lstrip('/') if parsed.path else 'pr_review'
        }
    
    def validate_repository_url(self, repo_url: str) -> Dict[str, str]:
        """
        Validate and parse Azure DevOps repository URL.
        
        Expected format: https://dev.azure.com/{org}/{project}/_git/{repo}
        
        Args:
            repo_url: Repository URL to validate
        
        Returns:
            Dictionary with parsed components: organization, project, repository_name
        
        Raises:
            RepositoryValidationError: If URL format is invalid
        """
        match = self._azure_devops_url_pattern.match(repo_url)
        
        if not match:
            raise RepositoryValidationError(
                f"Invalid Azure DevOps repository URL format. "
                f"Expected: https://dev.azure.com/{{org}}/{{project}}/_git/{{repo}}, "
                f"Got: {repo_url}"
            )
        
        return {
            'organization': match.group('org'),
            'project': match.group('project'),
            'repository_name': match.group('repo')
        }
    
    async def add_repository(self, repo_create: RepositoryCreate) -> Repository:
        """
        Add a repository to the monitoring configuration.
        
        Args:
            repo_create: Repository creation request with URL
        
        Returns:
            Created Repository object
        
        Raises:
            RepositoryValidationError: If URL format is invalid
            Exception: If database operation fails
        """
        # Validate and parse URL
        repo_url = str(repo_create.repository_url)
        parsed = self.validate_repository_url(repo_url)
        
        try:
            async with self._get_connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # Check if repository already exists
                    await cursor.execute(
                        "SELECT id FROM repositories WHERE repository_url = %s",
                        (repo_url,)
                    )
                    existing = await cursor.fetchone()
                    
                    if existing:
                        raise ValueError(f"Repository already exists with URL: {repo_url}")
                    
                    # Insert new repository
                    await cursor.execute(
                        """
                        INSERT INTO repositories 
                        (organization, project, repository_name, repository_url)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            parsed['organization'],
                            parsed['project'],
                            parsed['repository_name'],
                            repo_url
                        )
                    )
                    
                    # Get the inserted repository
                    repo_id = cursor.lastrowid
                    await cursor.execute(
                        "SELECT * FROM repositories WHERE id = LAST_INSERT_ID()"
                    )
                    row = await cursor.fetchone()
                    
                    await conn.commit()
                    
                    logger.info(
                        f"Added repository: {parsed['organization']}/{parsed['project']}/{parsed['repository_name']}"
                    )
                    
                    return self._row_to_repository(row)
        
        except ValueError as e:
            logger.warning(f"Repository already exists: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to add repository: {e}")
            raise
    
    async def remove_repository(self, repo_id: str) -> None:
        """
        Remove a repository from the monitoring configuration.
        
        Args:
            repo_id: Repository ID to remove
        
        Raises:
            ValueError: If repository not found
            Exception: If database operation fails
        """
        try:
            async with self._get_connection() as conn:
                async with conn.cursor() as cursor:
                    # Check if repository exists
                    await cursor.execute(
                        "SELECT id FROM repositories WHERE id = %s",
                        (repo_id,)
                    )
                    existing = await cursor.fetchone()
                    
                    if not existing:
                        raise ValueError(f"Repository not found with ID: {repo_id}")
                    
                    # Delete repository (cascade will delete related service_hooks)
                    await cursor.execute(
                        "DELETE FROM repositories WHERE id = %s",
                        (repo_id,)
                    )
                    
                    await conn.commit()
                    
                    logger.info(f"Removed repository with ID: {repo_id}")
        
        except ValueError as e:
            logger.warning(f"Repository not found: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to remove repository: {e}")
            raise
    
    async def list_repositories(self) -> List[Repository]:
        """
        List all monitored repositories.
        
        Returns:
            List of Repository objects
        
        Raises:
            Exception: If database operation fails
        """
        try:
            async with self._get_connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        """
                        SELECT * FROM repositories 
                        ORDER BY created_at DESC
                        """
                    )
                    rows = await cursor.fetchall()
                    
                    repositories = [self._row_to_repository(row) for row in rows]
                    
                    logger.debug(f"Retrieved {len(repositories)} repositories")
                    
                    return repositories
        
        except Exception as e:
            logger.error(f"Failed to list repositories: {e}")
            raise
    
    async def is_monitored(self, repo_id: str) -> bool:
        """
        Check if a repository is being monitored.
        
        Args:
            repo_id: Repository ID to check
        
        Returns:
            True if repository is monitored, False otherwise
        
        Raises:
            Exception: If database operation fails
        """
        try:
            async with self._get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT id FROM repositories WHERE id = %s",
                        (repo_id,)
                    )
                    result = await cursor.fetchone()
                    
                    return result is not None
        
        except Exception as e:
            logger.error(f"Failed to check if repository is monitored: {e}")
            raise
    
    async def get_repository_by_url(self, repo_url: str) -> Optional[Repository]:
        """
        Get repository by URL.
        
        Args:
            repo_url: Repository URL
        
        Returns:
            Repository object if found, None otherwise
        
        Raises:
            Exception: If database operation fails
        """
        try:
            async with self._get_connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        "SELECT * FROM repositories WHERE repository_url = %s",
                        (repo_url,)
                    )
                    row = await cursor.fetchone()
                    
                    if row:
                        return self._row_to_repository(row)
                    return None
        
        except Exception as e:
            logger.error(f"Failed to get repository by URL: {e}")
            raise
    
    async def get_repository_by_id(self, repo_id: str) -> Optional[Repository]:
        """
        Get repository by ID.
        
        Args:
            repo_id: Repository ID
        
        Returns:
            Repository object if found, None otherwise
        
        Raises:
            Exception: If database operation fails
        """
        try:
            async with self._get_connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        "SELECT * FROM repositories WHERE id = %s",
                        (repo_id,)
                    )
                    row = await cursor.fetchone()
                    
                    if row:
                        return self._row_to_repository(row)
                    return None
        
        except Exception as e:
            logger.error(f"Failed to get repository by ID: {e}")
            raise
    
    def _row_to_repository(self, row: Dict[str, Any]) -> Repository:
        """
        Convert database row to Repository model.
        
        Args:
            row: Database row as dictionary
        
        Returns:
            Repository object
        """
        return Repository(
            id=str(row['id']),
            organization=row['organization'],
            project=row['project'],
            repository_name=row['repository_name'],
            repository_url=row['repository_url'],
            service_hook_id=row.get('service_hook_id'),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

# Global service instance factory
def get_repository_config_service() -> RepositoryConfigService:
    """
    Get or create the global repository config service instance.
    
    Returns:
        RepositoryConfigService instance
    """
    return RepositoryConfigService()
