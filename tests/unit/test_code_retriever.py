"""Unit tests for CodeRetriever component."""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from azure.devops.v7_1.git.models import (
    GitPullRequest,
    GitPullRequestChange,
    IdentityRef,
    GitCommitRef,
)

from app.services.code_retriever import (
    CodeRetriever,
    CodeRetrieverError,
    TransientError,
    PermanentError,
)
from app.models.file_change import ChangeType
from app.models.pr_event import PRMetadata


@pytest.fixture
def mock_git_client():
    """Create a mock GitClient."""
    client = Mock()
    return client


@pytest.fixture
def code_retriever(mock_git_client):
    """Create CodeRetriever instance with mocked client."""
    with patch('app.services.code_retriever.Connection') as mock_conn:
        mock_conn.return_value.clients.get_git_client.return_value = mock_git_client
        retriever = CodeRetriever(
            organization_url="https://dev.azure.com/test-org",
            personal_access_token="test-pat"
        )
        return retriever


@pytest.fixture
def mock_pr():
    """Create a mock GitPullRequest object."""
    pr = Mock(spec=GitPullRequest)
    pr.pull_request_id = 123
    pr.source_ref_name = "refs/heads/feature/test"
    pr.target_ref_name = "refs/heads/main"
    pr.title = "Test PR"
    pr.description = "Test description"
    
    # Mock author
    author = Mock(spec=IdentityRef)
    author.display_name = "Test User"
    pr.created_by = author
    
    # Mock commits
    source_commit = Mock(spec=GitCommitRef)
    source_commit.commit_id = "abc123"
    pr.last_merge_source_commit = source_commit
    
    target_commit = Mock(spec=GitCommitRef)
    target_commit.commit_id = "def456"
    pr.last_merge_target_commit = target_commit
    
    return pr


class TestCodeRetriever:
    """Test suite for CodeRetriever component."""

    def test_initialization(self):
        """Test CodeRetriever initialization."""
        with patch('app.services.code_retriever.Connection'):
            retriever = CodeRetriever(
                organization_url="https://dev.azure.com/test-org",
                personal_access_token="test-pat"
            )
            
            assert retriever.organization_url == "https://dev.azure.com/test-org"
            assert retriever.pat == "test-pat"
            assert retriever.max_retries == 3
            assert retriever.base_delay == 1.0
            assert retriever.max_delay == 60.0

    @pytest.mark.asyncio
    async def test_get_pr_metadata_success(self, code_retriever, mock_git_client, mock_pr):
        """Test successful PR metadata retrieval."""
        mock_git_client.get_pull_request.return_value = mock_pr
        
        metadata = await code_retriever.get_pr_metadata(
            repository_id="test-repo",
            pr_id=123
        )
        
        assert isinstance(metadata, PRMetadata)
        assert metadata.pr_id == "123"
        assert metadata.repository_id == "test-repo"
        assert metadata.source_branch == "feature/test"
        assert metadata.target_branch == "main"
        assert metadata.author == "Test User"
        assert metadata.title == "Test PR"
        assert metadata.description == "Test description"
        assert metadata.source_commit_id == "abc123"
        assert metadata.target_commit_id == "def456"

    @pytest.mark.asyncio
    async def test_get_pr_metadata_not_found(self, code_retriever, mock_git_client):
        """Test PR metadata retrieval with not found error."""
        mock_git_client.get_pull_request.side_effect = Exception("not found")
        
        with pytest.raises(PermanentError):
            await code_retriever.get_pr_metadata(
                repository_id="test-repo",
                pr_id=999
            )

    @pytest.mark.asyncio
    async def test_retry_with_backoff_success_on_retry(self, code_retriever):
        """Test retry logic succeeds on second attempt."""
        mock_func = Mock()
        mock_func.side_effect = [
            Exception("Temporary error"),
            "success"
        ]
        
        result = await code_retriever._retry_with_backoff(mock_func)
        
        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_with_backoff_permanent_error(self, code_retriever):
        """Test retry logic fails immediately on permanent error."""
        mock_func = Mock()
        mock_func.side_effect = Exception("unauthorized")
        
        with pytest.raises(PermanentError):
            await code_retriever._retry_with_backoff(mock_func)
        
        # Should only try once for permanent errors
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_with_backoff_exhausted(self, code_retriever):
        """Test retry logic exhausts all attempts."""
        mock_func = Mock()
        mock_func.side_effect = Exception("Temporary error")
        
        with pytest.raises(TransientError):
            await code_retriever._retry_with_backoff(mock_func)
        
        # Should try max_retries times
        assert mock_func.call_count == code_retriever.max_retries

    @pytest.mark.asyncio
    async def test_get_file_content_success(self, code_retriever, mock_git_client):
        """Test successful file content retrieval."""
        mock_git_client.get_item_content.return_value = [b"line 1\n", b"line 2\n"]
        
        content = await code_retriever.get_file_content(
            repository_id="test-repo",
            file_path="test.py",
            commit_id="abc123"
        )
        
        assert content == "line 1\nline 2\n"

    @pytest.mark.asyncio
    async def test_get_file_content_binary_file(self, code_retriever):
        """Test binary file is skipped."""
        content = await code_retriever.get_file_content(
            repository_id="test-repo",
            file_path="image.png",
            commit_id="abc123"
        )
        
        assert content is None

    @pytest.mark.asyncio
    async def test_get_file_content_not_found(self, code_retriever, mock_git_client):
        """Test file content retrieval when file doesn't exist."""
        mock_git_client.get_item_content.side_effect = Exception("File not found")
        
        content = await code_retriever.get_file_content(
            repository_id="test-repo",
            file_path="missing.py",
            commit_id="abc123"
        )
        
        # Should return None instead of raising exception
        assert content is None

    def test_is_binary_file(self, code_retriever):
        """Test binary file detection."""
        assert code_retriever._is_binary_file("image.png") is True
        assert code_retriever._is_binary_file("document.pdf") is True
        assert code_retriever._is_binary_file("archive.zip") is True
        assert code_retriever._is_binary_file("library.jar") is True
        assert code_retriever._is_binary_file("font.woff") is True
        
        assert code_retriever._is_binary_file("script.py") is False
        assert code_retriever._is_binary_file("style.css") is False
        assert code_retriever._is_binary_file("code.java") is False
        assert code_retriever._is_binary_file("config.json") is False

    def test_map_change_type(self, code_retriever):
        """Test Azure DevOps change type mapping."""
        assert code_retriever._map_change_type("add") == ChangeType.ADD
        assert code_retriever._map_change_type("Add") == ChangeType.ADD
        assert code_retriever._map_change_type("delete") == ChangeType.DELETE
        assert code_retriever._map_change_type("Delete") == ChangeType.DELETE
        assert code_retriever._map_change_type("edit") == ChangeType.EDIT
        assert code_retriever._map_change_type("Edit") == ChangeType.EDIT
        assert code_retriever._map_change_type("rename") == ChangeType.EDIT

    def test_parse_line_changes_add(self, code_retriever):
        """Test line change parsing for file addition."""
        target_content = "line 1\nline 2\nline 3"
        
        added, modified, deleted = code_retriever._parse_line_changes(
            source_content=None,
            target_content=target_content,
            change_type=ChangeType.ADD
        )
        
        assert len(added) == 3
        assert len(modified) == 0
        assert len(deleted) == 0
        assert added[0].line_number == 1
        assert added[0].content == "line 1"
        assert added[0].change_type == ChangeType.ADD

    def test_parse_line_changes_delete(self, code_retriever):
        """Test line change parsing for file deletion."""
        source_content = "line 1\nline 2\nline 3"
        
        added, modified, deleted = code_retriever._parse_line_changes(
            source_content=source_content,
            target_content=None,
            change_type=ChangeType.DELETE
        )
        
        assert len(added) == 0
        assert len(modified) == 0
        assert len(deleted) == 3
        assert deleted[0].line_number == 1
        assert deleted[0].content == "line 1"
        assert deleted[0].change_type == ChangeType.DELETE

    def test_parse_line_changes_edit(self, code_retriever):
        """Test line change parsing for file modification."""
        source_content = "line 1\nline 2\nline 3"
        target_content = "line 1\nmodified line 2\nline 3\nline 4"
        
        added, modified, deleted = code_retriever._parse_line_changes(
            source_content=source_content,
            target_content=target_content,
            change_type=ChangeType.EDIT
        )
        
        # Line 2 modified, line 4 added
        assert len(modified) == 1
        assert len(added) == 1
        assert len(deleted) == 0
        
        assert modified[0].line_number == 2
        assert modified[0].content == "modified line 2"
        assert modified[0].change_type == ChangeType.EDIT
        
        assert added[0].line_number == 4
        assert added[0].content == "line 4"
        assert added[0].change_type == ChangeType.ADD
