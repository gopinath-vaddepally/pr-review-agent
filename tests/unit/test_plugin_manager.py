"""Unit tests for PluginManager."""

import pytest
from pathlib import Path
from typing import List

from plugins import PluginManager, LanguagePlugin
from app.models.analysis import ASTNode, CodeContext, AnalysisRule, CodeIssue, DesignPattern
from app.models.comment import CommentSeverity, CommentCategory


class MockJavaPlugin(LanguagePlugin):
    """Mock Java plugin for testing."""
    
    @property
    def language_name(self) -> str:
        return "java"
    
    @property
    def file_extensions(self) -> List[str]:
        return [".java"]
    
    async def parse_file(self, file_path: str, content: str) -> ASTNode:
        return ASTNode(
            node_type="compilation_unit",
            start_line=1,
            end_line=10,
            start_column=0,
            end_column=0,
            children=[],
            text=content
        )
    
    async def extract_context(
        self, 
        line_number: int, 
        ast: ASTNode, 
        file_content: str
    ) -> CodeContext:
        return CodeContext(
            language="java",
            file_path="test.java",
            line_number=line_number,
            enclosing_class="TestClass",
            enclosing_method="testMethod()",
            imports=["java.util.List"],
            surrounding_lines=[]
        )
    
    async def get_analysis_rules(self) -> List[AnalysisRule]:
        return [
            AnalysisRule(
                name="test_rule",
                category=CommentCategory.BUG,
                severity=CommentSeverity.ERROR,
                pattern="Test pattern",
                llm_prompt="Test prompt"
            )
        ]
    
    async def format_suggestion(
        self, 
        issue: CodeIssue, 
        context: CodeContext
    ) -> str:
        return "Test suggestion"
    
    async def detect_patterns(self, ast: ASTNode) -> List[DesignPattern]:
        return []


class MockTypeScriptPlugin(LanguagePlugin):
    """Mock TypeScript plugin for testing."""
    
    @property
    def language_name(self) -> str:
        return "typescript"
    
    @property
    def file_extensions(self) -> List[str]:
        return [".ts", ".tsx"]
    
    async def parse_file(self, file_path: str, content: str) -> ASTNode:
        return ASTNode(
            node_type="program",
            start_line=1,
            end_line=10,
            start_column=0,
            end_column=0,
            children=[],
            text=content
        )
    
    async def extract_context(
        self, 
        line_number: int, 
        ast: ASTNode, 
        file_content: str
    ) -> CodeContext:
        return CodeContext(
            language="typescript",
            file_path="test.ts",
            line_number=line_number,
            surrounding_lines=[]
        )
    
    async def get_analysis_rules(self) -> List[AnalysisRule]:
        return []
    
    async def format_suggestion(
        self, 
        issue: CodeIssue, 
        context: CodeContext
    ) -> str:
        return "Test suggestion"
    
    async def detect_patterns(self, ast: ASTNode) -> List[DesignPattern]:
        return []


class TestPluginManager:
    """Test cases for PluginManager."""
    
    def test_register_plugin(self):
        """Test plugin registration."""
        manager = PluginManager()
        plugin = MockJavaPlugin()
        
        manager.register_plugin(plugin)
        
        assert "java" in manager.list_supported_languages()
        assert ".java" in manager.list_supported_extensions()
    
    def test_get_plugin_for_file(self):
        """Test getting plugin by file extension."""
        manager = PluginManager()
        java_plugin = MockJavaPlugin()
        ts_plugin = MockTypeScriptPlugin()
        
        manager.register_plugin(java_plugin)
        manager.register_plugin(ts_plugin)
        
        # Test Java file
        plugin = manager.get_plugin_for_file("src/Main.java")
        assert plugin is not None
        assert plugin.language_name == "java"
        
        # Test TypeScript file
        plugin = manager.get_plugin_for_file("src/app.ts")
        assert plugin is not None
        assert plugin.language_name == "typescript"
        
        # Test TSX file
        plugin = manager.get_plugin_for_file("src/Component.tsx")
        assert plugin is not None
        assert plugin.language_name == "typescript"
        
        # Test unsupported file
        plugin = manager.get_plugin_for_file("src/script.py")
        assert plugin is None
    
    def test_get_plugin_by_name(self):
        """Test getting plugin by language name."""
        manager = PluginManager()
        plugin = MockJavaPlugin()
        
        manager.register_plugin(plugin)
        
        retrieved = manager.get_plugin("java")
        assert retrieved is not None
        assert retrieved.language_name == "java"
        
        not_found = manager.get_plugin("python")
        assert not_found is None
    
    def test_unregister_plugin(self):
        """Test plugin unregistration."""
        manager = PluginManager()
        plugin = MockJavaPlugin()
        
        manager.register_plugin(plugin)
        assert "java" in manager.list_supported_languages()
        
        result = manager.unregister_plugin("java")
        assert result is True
        assert "java" not in manager.list_supported_languages()
        assert ".java" not in manager.list_supported_extensions()
        
        # Try to unregister again
        result = manager.unregister_plugin("java")
        assert result is False
    
    def test_multiple_extensions_same_language(self):
        """Test plugin with multiple file extensions."""
        manager = PluginManager()
        plugin = MockTypeScriptPlugin()
        
        manager.register_plugin(plugin)
        
        # Both extensions should map to the same plugin
        plugin_ts = manager.get_plugin_for_file("file.ts")
        plugin_tsx = manager.get_plugin_for_file("file.tsx")
        
        assert plugin_ts is plugin_tsx
        assert plugin_ts.language_name == "typescript"
    
    def test_plugin_override_warning(self):
        """Test that registering a plugin twice logs a warning."""
        manager = PluginManager()
        plugin1 = MockJavaPlugin()
        plugin2 = MockJavaPlugin()
        
        manager.register_plugin(plugin1)
        manager.register_plugin(plugin2)  # Should log warning
        
        # Second plugin should override first
        assert manager.get_plugin("java") is plugin2
    
    def test_get_statistics(self):
        """Test getting plugin manager statistics."""
        manager = PluginManager()
        
        stats = manager.get_statistics()
        assert stats["total_plugins"] == 0
        assert stats["total_extensions"] == 0
        assert stats["languages"] == []
        
        manager.register_plugin(MockJavaPlugin())
        manager.register_plugin(MockTypeScriptPlugin())
        
        stats = manager.get_statistics()
        assert stats["total_plugins"] == 2
        assert stats["total_extensions"] == 3  # .java, .ts, .tsx
        assert "java" in stats["languages"]
        assert "typescript" in stats["languages"]
    
    def test_load_plugin_config(self, tmp_path):
        """Test loading plugin configuration from YAML."""
        manager = PluginManager()
        
        # Create a temporary plugin directory with config
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        
        config_content = """
name: test
version: 1.0.0
file_extensions:
  - .test
tree_sitter_grammar: tree-sitter-test
analysis_rules:
  - rule1
  - rule2
"""
        config_file = plugin_dir / "config.yaml"
        config_file.write_text(config_content)
        
        config = manager.load_plugin_config(plugin_dir)
        
        assert config["name"] == "test"
        assert config["version"] == "1.0.0"
        assert ".test" in config["file_extensions"]
        assert "rule1" in config["analysis_rules"]
    
    def test_load_plugin_config_missing_file(self, tmp_path):
        """Test loading config from directory without config.yaml."""
        manager = PluginManager()
        plugin_dir = tmp_path / "no_config"
        plugin_dir.mkdir()
        
        with pytest.raises(FileNotFoundError):
            manager.load_plugin_config(plugin_dir)
    
    def test_load_plugin_config_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML configuration."""
        manager = PluginManager()
        plugin_dir = tmp_path / "bad_config"
        plugin_dir.mkdir()
        
        config_file = plugin_dir / "config.yaml"
        config_file.write_text("invalid: yaml: content: [")
        
        with pytest.raises(Exception):  # yaml.YAMLError
            manager.load_plugin_config(plugin_dir)
    
    def test_load_plugin_config_missing_required_fields(self, tmp_path):
        """Test loading config with missing required fields."""
        manager = PluginManager()
        plugin_dir = tmp_path / "incomplete_config"
        plugin_dir.mkdir()
        
        config_content = """
name: test
# Missing version and file_extensions
"""
        config_file = plugin_dir / "config.yaml"
        config_file.write_text(config_content)
        
        with pytest.raises(ValueError):
            manager.load_plugin_config(plugin_dir)
    
    @pytest.mark.asyncio
    async def test_initialize_plugins(self, tmp_path):
        """Test plugin initialization from directory."""
        manager = PluginManager()
        
        # Create plugin directories with configs
        java_dir = tmp_path / "java"
        java_dir.mkdir()
        (java_dir / "config.yaml").write_text("""
name: java
version: 1.0.0
file_extensions:
  - .java
""")
        
        ts_dir = tmp_path / "typescript"
        ts_dir.mkdir()
        (ts_dir / "config.yaml").write_text("""
name: typescript
version: 1.0.0
file_extensions:
  - .ts
""")
        
        # Initialize plugins
        await manager.initialize_plugins(tmp_path)
        
        # Configs should be loaded (but plugins not instantiated yet)
        # This just validates the discovery mechanism works
