"""
Unit tests for Code Analyzer component.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.analyzers.code_analyzer import CodeAnalyzer, LLMClient
from app.models import (
    FileChange,
    LineChange,
    ChangeType,
    LineComment,
    CommentSeverity,
    CommentCategory,
    ASTNode,
    CodeContext,
    AnalysisRule,
)
from plugins.manager import PluginManager


@pytest.fixture
def mock_plugin_manager():
    """Create a mock plugin manager."""
    manager = MagicMock(spec=PluginManager)
    return manager


@pytest.fixture
def mock_plugin():
    """Create a mock language plugin."""
    plugin = AsyncMock()
    plugin.language_name = "java"
    plugin.file_extensions = [".java"]
    
    # Mock parse_file to return a simple AST
    plugin.parse_file = AsyncMock(return_value=ASTNode(
        node_type="program",
        start_line=1,
        end_line=10,
        start_column=0,
        end_column=0,
        children=[],
    ))
    
    # Mock extract_context
    plugin.extract_context = AsyncMock(return_value=CodeContext(
        language="java",
        file_path="Test.java",
        line_number=5,
        enclosing_class="TestClass",
        enclosing_method="testMethod()",
        imports=["java.util.List"],
        surrounding_lines=["line 4", "line 5", "line 6"],
    ))
    
    # Mock get_analysis_rules
    plugin.get_analysis_rules = AsyncMock(return_value=[
        AnalysisRule(
            name="test_rule",
            category=CommentCategory.BUG,
            severity=CommentSeverity.WARNING,
            pattern="Test pattern",
            llm_prompt="Check for test issues",
        )
    ])
    
    return plugin


@pytest.fixture
def code_analyzer(mock_plugin_manager):
    """Create a CodeAnalyzer instance with mock LLM client."""
    mock_llm_client = AsyncMock(spec=LLMClient)
    return CodeAnalyzer(mock_plugin_manager, llm_client=mock_llm_client)


@pytest.fixture
def sample_file_change():
    """Create a sample FileChange object."""
    return FileChange(
        file_path="Test.java",
        change_type=ChangeType.EDIT,
        added_lines=[],
        modified_lines=[
            LineChange(
                line_number=5,
                change_type=ChangeType.EDIT,
                content="String name = null;",
            )
        ],
        deleted_lines=[],
        source_content="class Test { }",
        target_content="class Test { String name = null; }",
    )


class TestLLMClient:
    """Tests for LLMClient."""
    
    def test_init_openai(self):
        """Test LLMClient initialization with OpenAI."""
        mock_settings = MagicMock()
        mock_settings.azure_openai_endpoint = None
        mock_settings.azure_openai_api_key = None
        mock_settings.openai_api_key = "test-key"
        
        with patch('app.analyzers.code_analyzer.AsyncOpenAI'):
            client = LLMClient(settings=mock_settings)
            assert not client.is_azure
            assert client.deployment == "gpt-4"
    
    def test_init_azure_openai(self):
        """Test LLMClient initialization with Azure OpenAI."""
        mock_settings = MagicMock()
        mock_settings.azure_openai_endpoint = "https://test.openai.azure.com/"
        mock_settings.azure_openai_api_key = "test-key"
        mock_settings.azure_openai_deployment = "gpt-4-deployment"
        
        with patch('app.analyzers.code_analyzer.AsyncAzureOpenAI'):
            client = LLMClient(settings=mock_settings)
            assert client.is_azure
            assert client.deployment == "gpt-4-deployment"
    
    @pytest.mark.asyncio
    async def test_analyze_code_no_issue(self):
        """Test analyze_code when no issue is found."""
        mock_settings = MagicMock()
        mock_settings.azure_openai_endpoint = None
        mock_settings.azure_openai_api_key = None
        mock_settings.openai_api_key = "test-key"
        
        with patch('app.analyzers.code_analyzer.AsyncOpenAI'):
            client = LLMClient(settings=mock_settings)
            
            # Mock the API response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "No issue found."
            
            client.client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            context = CodeContext(
                language="java",
                file_path="Test.java",
                line_number=5,
            )
            rule = AnalysisRule(
                name="test_rule",
                category=CommentCategory.BUG,
                severity=CommentSeverity.WARNING,
                pattern="Test pattern",
                llm_prompt="Check for issues",
            )
            
            result = await client.analyze_code("String name = null;", context, rule)
            assert result is None
    
    @pytest.mark.asyncio
    async def test_analyze_code_with_issue(self):
        """Test analyze_code when an issue is found."""
        mock_settings = MagicMock()
        mock_settings.azure_openai_endpoint = None
        mock_settings.azure_openai_api_key = None
        mock_settings.openai_api_key = "test-key"
        
        with patch('app.analyzers.code_analyzer.AsyncOpenAI'):
            client = LLMClient(settings=mock_settings)
            
            # Mock the API response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Potential null pointer issue detected."
            
            client.client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            context = CodeContext(
                language="java",
                file_path="Test.java",
                line_number=5,
            )
            rule = AnalysisRule(
                name="test_rule",
                category=CommentCategory.BUG,
                severity=CommentSeverity.WARNING,
                pattern="Test pattern",
                llm_prompt="Check for issues",
            )
            
            result = await client.analyze_code("String name = null;", context, rule)
            assert result == "Potential null pointer issue detected."


class TestCodeAnalyzer:
    """Tests for CodeAnalyzer."""
    
    @pytest.mark.asyncio
    async def test_analyze_file_no_plugin(self, code_analyzer, sample_file_change):
        """Test analyze_file when no plugin is found."""
        code_analyzer.plugin_manager.get_plugin_for_file = MagicMock(return_value=None)
        
        comments = await code_analyzer.analyze_file(sample_file_change)
        assert comments == []
    
    @pytest.mark.asyncio
    async def test_analyze_file_deleted_file(self, code_analyzer, mock_plugin):
        """Test analyze_file skips deleted files."""
        code_analyzer.plugin_manager.get_plugin_for_file = MagicMock(return_value=mock_plugin)
        
        deleted_file = FileChange(
            file_path="Test.java",
            change_type=ChangeType.DELETE,
            added_lines=[],
            modified_lines=[],
            deleted_lines=[],
        )
        
        comments = await code_analyzer.analyze_file(deleted_file)
        assert comments == []
    
    @pytest.mark.asyncio
    async def test_analyze_file_parse_failure(self, code_analyzer, mock_plugin, sample_file_change):
        """Test analyze_file handles parse failures gracefully."""
        code_analyzer.plugin_manager.get_plugin_for_file = MagicMock(return_value=mock_plugin)
        mock_plugin.parse_file = AsyncMock(side_effect=Exception("Parse error"))
        
        comments = await code_analyzer.analyze_file(sample_file_change)
        assert comments == []
    
    @pytest.mark.asyncio
    async def test_analyze_file_success(self, code_analyzer, mock_plugin, sample_file_change):
        """Test successful file analysis."""
        code_analyzer.plugin_manager.get_plugin_for_file = MagicMock(return_value=mock_plugin)
        
        # Mock LLM client to return an issue
        code_analyzer.llm_client.analyze_code = AsyncMock(
            return_value="Potential null pointer issue. Suggestion: Initialize with a default value."
        )
        
        comments = await code_analyzer.analyze_file(sample_file_change)
        
        # Should have 1 comment (1 line * 1 rule)
        assert len(comments) == 1
        assert comments[0].file_path == "Test.java"
        assert comments[0].line_number == 5
        assert comments[0].severity == CommentSeverity.WARNING
        assert comments[0].category == CommentCategory.BUG
    
    @pytest.mark.asyncio
    async def test_parse_file_no_plugin(self, code_analyzer):
        """Test parse_file raises error when no plugin found."""
        code_analyzer.plugin_manager.get_plugin_for_file = MagicMock(return_value=None)
        
        with pytest.raises(ValueError, match="No plugin found"):
            await code_analyzer.parse_file("Test.java", "content")
    
    @pytest.mark.asyncio
    async def test_parse_file_success(self, code_analyzer, mock_plugin):
        """Test successful file parsing."""
        ast = await code_analyzer.parse_file("Test.java", "content", mock_plugin)
        
        assert ast is not None
        assert ast.node_type == "program"
    
    @pytest.mark.asyncio
    async def test_analyze_line_no_issue(self, code_analyzer, mock_plugin, sample_file_change):
        """Test analyze_line when no issue is found."""
        ast = ASTNode(
            node_type="program",
            start_line=1,
            end_line=10,
            start_column=0,
            end_column=0,
        )
        rule = AnalysisRule(
            name="test_rule",
            category=CommentCategory.BUG,
            severity=CommentSeverity.WARNING,
            pattern="Test pattern",
            llm_prompt="Check for issues",
        )
        
        code_analyzer.llm_client.analyze_code = AsyncMock(return_value=None)
        
        comment = await code_analyzer.analyze_line(
            "String name = 'test';",
            5,
            sample_file_change,
            ast,
            rule,
            mock_plugin,
        )
        
        assert comment is None
    
    @pytest.mark.asyncio
    async def test_analyze_line_with_issue(self, code_analyzer, mock_plugin, sample_file_change):
        """Test analyze_line when an issue is found."""
        ast = ASTNode(
            node_type="program",
            start_line=1,
            end_line=10,
            start_column=0,
            end_column=0,
        )
        rule = AnalysisRule(
            name="test_rule",
            category=CommentCategory.BUG,
            severity=CommentSeverity.WARNING,
            pattern="Test pattern",
            llm_prompt="Check for issues",
        )
        
        code_analyzer.llm_client.analyze_code = AsyncMock(
            return_value="Null pointer risk detected. Suggestion: Add null check."
        )
        
        comment = await code_analyzer.analyze_line(
            "String name = null;",
            5,
            sample_file_change,
            ast,
            rule,
            mock_plugin,
        )
        
        assert comment is not None
        assert comment.file_path == "Test.java"
        assert comment.line_number == 5
        assert comment.severity == CommentSeverity.WARNING
        assert comment.category == CommentCategory.BUG
        assert "Null pointer risk" in comment.message
        assert comment.suggestion == "Add null check."
    
    @pytest.mark.asyncio
    async def test_analyze_line_handles_exceptions(self, code_analyzer, mock_plugin, sample_file_change):
        """Test analyze_line handles exceptions gracefully."""
        ast = ASTNode(
            node_type="program",
            start_line=1,
            end_line=10,
            start_column=0,
            end_column=0,
        )
        rule = AnalysisRule(
            name="test_rule",
            category=CommentCategory.BUG,
            severity=CommentSeverity.WARNING,
            pattern="Test pattern",
            llm_prompt="Check for issues",
        )
        
        # Mock extract_context to raise an exception
        mock_plugin.extract_context = AsyncMock(side_effect=Exception("Context error"))
        
        comment = await code_analyzer.analyze_line(
            "String name = null;",
            5,
            sample_file_change,
            ast,
            rule,
            mock_plugin,
        )
        
        assert comment is None
