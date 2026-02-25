"""
Unit tests for RepositoryConfigService.

Tests repository CRUD operations, URL validation, and database interactions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.repository_config import (
    RepositoryConfigService,
    RepositoryValidationError
)
from app.models.repository import Repository, RepositoryCreate


class TestRepositoryURLValidation:
    """Test repository URL validation and parsing."""
    
    def test_validate_valid_url(self):
        """Test validation of valid Azure DevOps URL."""
        service = RepositoryConfigService()
        
        url = "https://dev.azure.com/myorg/myproject/_git/myrepo"
        result = service.validate_repository_url(url)
        
        assert result['organization'] == 'myorg'
        assert result['project'] == 'myproject'
        assert result['repository_name'] == 'myrepo'
    
    def test_validate_url_with_trailing_slash(self):
        """Test validation of URL with trailing slash."""
        service = RepositoryConfigService()
        
        url = "https://dev.azure.com/myorg/myproject/_git/myrepo/"
        result = service.validate_repository_url(url)
        
        assert result['organization'] == 'myorg'
        assert result['project'] == 'myproject'
        assert result['repository_name'] == 'myrepo'
    
    def test_validate_url_with_special_characters(self):
        """Test validation of URL with special characters in names."""
        service = RepositoryConfigService()
        
        url = "https://dev.azure.com/my-org/my.project/_git/my_repo"
        result = service.validate_repository_url(url)
        
        assert result['organization'] == 'my-org'
        assert result['project'] == 'my.project'
        assert result['repository_name'] == 'my_repo'
    
    def test_validate_invalid_url_wrong_domain(self):
        """Test validation fails for wrong domain."""
        service = RepositoryConfigService()
        
        url = "https://github.com/myorg/myrepo"
        
        with pytest.raises(RepositoryValidationError) as exc_info:
            service.validate_repository_url(url)
        
        assert "Invalid Azure DevOps repository URL format" in str(exc_info.value)
    
    def test_validate_invalid_url_missing_git(self):
        """Test validation fails for URL missing _git segment."""
        service = RepositoryConfigService()
        
        url = "https://dev.azure.com/myorg/myproject/myrepo"
        
        with pytest.raises(RepositoryValidationError) as exc_info:
            service.validate_repository_url(url)
        
        assert "Invalid Azure DevOps repository URL format" in str(exc_info.value)
    
    def test_validate_invalid_url_missing_parts(self):
        """Test validation fails for incomplete URL."""
        service = RepositoryConfigService()
        
        url = "https://dev.azure.com/myorg/_git/myrepo"
        
        with pytest.raises(RepositoryValidationError) as exc_info:
            service.validate_repository_url(url)
        
        assert "Invalid Azure DevOps repository URL format" in str(exc_info.value)
    
    def test_validate_invalid_url_http_instead_of_https(self):
        """Test validation fails for HTTP instead of HTTPS."""
        service = RepositoryConfigService()
        
        url = "http://dev.azure.com/myorg/myproject/_git/myrepo"
        
        with pytest.raises(RepositoryValidationError) as exc_info:
            service.validate_repository_url(url)
        
        assert "Invalid Azure DevOps repository URL format" in str(exc_info.value)


class TestRepositoryConfigService:
    """Test RepositoryConfigService CRUD operations."""
    
    @pytest.fixture
    def service(self):
        """Create a RepositoryConfigService instance."""
        return RepositoryConfigService()
    
    @pytest.fixture
    def mock_pool(self):
        """Create a mock connection pool."""
        pool = MagicMock()
        return pool
    
    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        conn = AsyncMock()
        cursor = AsyncMock()
        cursor.__aenter__ = AsyncMock(return_value=cursor)
        cursor.__aexit__ = AsyncMock(return_value=None)
        conn.cursor = MagicMock(return_value=cursor)
        return conn, cursor
    
    def test_parse_database_url(self, service):
        """Test parsing of database URL."""
        url = "mysql+aiomysql://user:pass@localhost:3306/testdb"
        result = service._parse_database_url(url)
        
        assert result['host'] == 'localhost'
        assert result['port'] == 3306
        assert result['user'] == 'user'
        assert result['password'] == 'pass'
        assert result['database'] == 'testdb'
    
    def test_parse_database_url_with_defaults(self, service):
        """Test parsing of database URL with missing components."""
        url = "mysql+aiomysql:///testdb"
        result = service._parse_database_url(url)
        
        assert result['host'] == 'localhost'
        assert result['port'] == 3306
        assert result['database'] == 'testdb'
    
    @pytest.mark.asyncio
    async def test_add_repository_success(self, service, mock_connection):
        """Test successful repository addition."""
        conn, cursor = mock_connection
        
        # Mock pool and connection
        service._pool = MagicMock()
        service._pool.acquire = MagicMock()
        service._pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        service._pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock cursor operations
        cursor.fetchone = AsyncMock(side_effect=[
            None,  # No existing repository
            {  # Inserted repository
                'id': '123',
                'organization': 'myorg',
                'project': 'myproject',
                'repository_name': 'myrepo',
                'repository_url': 'https://dev.azure.com/myorg/myproject/_git/myrepo',
                'service_hook_id': None,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
        ])
        cursor.lastrowid = 123
        
        # Test
        repo_create = RepositoryCreate(
            repository_url="https://dev.azure.com/myorg/myproject/_git/myrepo"
        )
        result = await service.add_repository(repo_create)
        
        # Assertions
        assert result.organization == 'myorg'
        assert result.project == 'myproject'
        assert result.repository_name == 'myrepo'
        assert cursor.execute.call_count == 3  # Check existing, insert, select inserted
        assert conn.commit.called
    
    @pytest.mark.asyncio
    async def test_add_repository_duplicate(self, service, mock_connection):
        """Test adding duplicate repository raises error."""
        conn, cursor = mock_connection
        
        # Mock pool and connection
        service._pool = MagicMock()
        service._pool.acquire = MagicMock()
        service._pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        service._pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock cursor to return existing repository
        cursor.fetchone = AsyncMock(return_value={'id': '123'})
        
        # Test
        repo_create = RepositoryCreate(
            repository_url="https://dev.azure.com/myorg/myproject/_git/myrepo"
        )
        
        with pytest.raises(ValueError) as exc_info:
            await service.add_repository(repo_create)
        
        assert "already exists" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_add_repository_invalid_url(self, service):
        """Test adding repository with invalid URL."""
        repo_create = RepositoryCreate(
            repository_url="https://github.com/myorg/myrepo"
        )
        
        with pytest.raises(RepositoryValidationError):
            await service.add_repository(repo_create)
    
    @pytest.mark.asyncio
    async def test_remove_repository_success(self, service, mock_connection):
        """Test successful repository removal."""
        conn, cursor = mock_connection
        
        # Mock pool and connection
        service._pool = MagicMock()
        service._pool.acquire = MagicMock()
        service._pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        service._pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock cursor to return existing repository
        cursor.fetchone = AsyncMock(return_value={'id': '123'})
        
        # Test
        await service.remove_repository('123')
        
        # Assertions
        assert cursor.execute.call_count == 2
        assert conn.commit.called
    
    @pytest.mark.asyncio
    async def test_remove_repository_not_found(self, service, mock_connection):
        """Test removing non-existent repository raises error."""
        conn, cursor = mock_connection
        
        # Mock pool and connection
        service._pool = MagicMock()
        service._pool.acquire = MagicMock()
        service._pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        service._pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock cursor to return no repository
        cursor.fetchone = AsyncMock(return_value=None)
        
        # Test
        with pytest.raises(ValueError) as exc_info:
            await service.remove_repository('999')
        
        assert "not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_list_repositories(self, service, mock_connection):
        """Test listing all repositories."""
        conn, cursor = mock_connection
        
        # Mock pool and connection
        service._pool = MagicMock()
        service._pool.acquire = MagicMock()
        service._pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        service._pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock cursor to return multiple repositories
        cursor.fetchall = AsyncMock(return_value=[
            {
                'id': '123',
                'organization': 'org1',
                'project': 'proj1',
                'repository_name': 'repo1',
                'repository_url': 'https://dev.azure.com/org1/proj1/_git/repo1',
                'service_hook_id': None,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            },
            {
                'id': '456',
                'organization': 'org2',
                'project': 'proj2',
                'repository_name': 'repo2',
                'repository_url': 'https://dev.azure.com/org2/proj2/_git/repo2',
                'service_hook_id': 'hook123',
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
        ])
        
        # Test
        result = await service.list_repositories()
        
        # Assertions
        assert len(result) == 2
        assert result[0].organization == 'org1'
        assert result[1].organization == 'org2'
        assert result[1].service_hook_id == 'hook123'
    
    @pytest.mark.asyncio
    async def test_is_monitored_true(self, service, mock_connection):
        """Test checking if repository is monitored returns True."""
        conn, cursor = mock_connection
        
        # Mock pool and connection
        service._pool = MagicMock()
        service._pool.acquire = MagicMock()
        service._pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        service._pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock cursor to return repository
        cursor.fetchone = AsyncMock(return_value={'id': '123'})
        
        # Test
        result = await service.is_monitored('123')
        
        # Assertions
        assert result is True
    
    @pytest.mark.asyncio
    async def test_is_monitored_false(self, service, mock_connection):
        """Test checking if repository is monitored returns False."""
        conn, cursor = mock_connection
        
        # Mock pool and connection
        service._pool = MagicMock()
        service._pool.acquire = MagicMock()
        service._pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        service._pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock cursor to return no repository
        cursor.fetchone = AsyncMock(return_value=None)
        
        # Test
        result = await service.is_monitored('999')
        
        # Assertions
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_repository_by_url(self, service, mock_connection):
        """Test getting repository by URL."""
        conn, cursor = mock_connection
        
        # Mock pool and connection
        service._pool = MagicMock()
        service._pool.acquire = MagicMock()
        service._pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        service._pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock cursor to return repository
        cursor.fetchone = AsyncMock(return_value={
            'id': '123',
            'organization': 'myorg',
            'project': 'myproject',
            'repository_name': 'myrepo',
            'repository_url': 'https://dev.azure.com/myorg/myproject/_git/myrepo',
            'service_hook_id': None,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        })
        
        # Test
        result = await service.get_repository_by_url(
            'https://dev.azure.com/myorg/myproject/_git/myrepo'
        )
        
        # Assertions
        assert result is not None
        assert result.organization == 'myorg'
        assert result.project == 'myproject'
    
    @pytest.mark.asyncio
    async def test_get_repository_by_id(self, service, mock_connection):
        """Test getting repository by ID."""
        conn, cursor = mock_connection
        
        # Mock pool and connection
        service._pool = MagicMock()
        service._pool.acquire = MagicMock()
        service._pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        service._pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock cursor to return repository
        cursor.fetchone = AsyncMock(return_value={
            'id': '123',
            'organization': 'myorg',
            'project': 'myproject',
            'repository_name': 'myrepo',
            'repository_url': 'https://dev.azure.com/myorg/myproject/_git/myrepo',
            'service_hook_id': None,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        })
        
        # Test
        result = await service.get_repository_by_id('123')
        
        # Assertions
        assert result is not None
        assert result.id == '123'
        assert result.organization == 'myorg'
