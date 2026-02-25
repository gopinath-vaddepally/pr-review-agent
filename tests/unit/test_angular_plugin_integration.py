"""
Integration tests for Angular plugin with PluginManager.

Tests the integration of the Angular plugin with the plugin manager.
"""

import pytest
from pathlib import Path
from plugins.angular.plugin import AngularPlugin
from plugins.manager import PluginManager


@pytest.fixture
def plugin_manager():
    """Create a plugin manager instance."""
    return PluginManager()


@pytest.fixture
def angular_plugin():
    """Create an Angular plugin instance."""
    return AngularPlugin()


class TestAngularPluginIntegration:
    """Test Angular plugin integration with PluginManager."""
    
    def test_register_angular_plugin(self, plugin_manager, angular_plugin):
        """Test registering the Angular plugin with the manager."""
        plugin_manager.register_plugin(angular_plugin)
        
        # Verify plugin is registered
        assert "angular" in plugin_manager.list_supported_languages()
        
        # Verify file extensions are mapped
        supported_extensions = plugin_manager.list_supported_extensions()
        assert ".ts" in supported_extensions
        assert ".component.ts" in supported_extensions
        assert ".service.ts" in supported_extensions
    
    def test_get_plugin_for_typescript_file(self, plugin_manager, angular_plugin):
        """Test getting Angular plugin for .ts file."""
        plugin_manager.register_plugin(angular_plugin)
        
        plugin = plugin_manager.get_plugin_for_file("test.component.ts")
        
        assert plugin is not None
        assert plugin.language_name == "angular"
    
    def test_get_plugin_for_service_file(self, plugin_manager, angular_plugin):
        """Test getting Angular plugin for .service.ts file."""
        plugin_manager.register_plugin(angular_plugin)
        
        plugin = plugin_manager.get_plugin_for_file("data.service.ts")
        
        assert plugin is not None
        assert plugin.language_name == "angular"
    
    def test_get_plugin_by_name(self, plugin_manager, angular_plugin):
        """Test getting Angular plugin by language name."""
        plugin_manager.register_plugin(angular_plugin)
        
        plugin = plugin_manager.get_plugin("angular")
        
        assert plugin is not None
        assert plugin.language_name == "angular"
    
    def test_load_angular_config(self, plugin_manager):
        """Test loading Angular plugin configuration."""
        plugins_dir = Path("plugins")
        angular_dir = plugins_dir / "angular"
        
        config = plugin_manager.load_plugin_config(angular_dir)
        
        assert config is not None
        assert config["name"] == "angular"
        assert config["version"] == "1.0.0"
        assert ".ts" in config["file_extensions"]
        assert "analysis_rules" in config
        assert "unsubscribe_observables" in config["analysis_rules"]
