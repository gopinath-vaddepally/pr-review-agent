"""
Plugin Manager for language-specific analysis plugins.

This module manages plugin registration, discovery, and selection based on file extensions.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional
import yaml

from plugins.base import LanguagePlugin

logger = logging.getLogger(__name__)


class PluginManager:
    """Manages language plugin registration and selection."""
    
    def __init__(self):
        """Initialize the plugin manager."""
        self._plugins: Dict[str, LanguagePlugin] = {}
        self._extension_map: Dict[str, str] = {}
        self._config_cache: Dict[str, Dict] = {}
    
    def register_plugin(self, plugin: LanguagePlugin) -> None:
        """
        Register a language plugin.
        
        Args:
            plugin: LanguagePlugin instance to register
        """
        language_name = plugin.language_name
        
        if language_name in self._plugins:
            logger.warning(f"Plugin for language '{language_name}' already registered, overwriting")
        
        self._plugins[language_name] = plugin
        
        # Map file extensions to language
        for ext in plugin.file_extensions:
            if ext in self._extension_map:
                logger.warning(
                    f"Extension '{ext}' already mapped to '{self._extension_map[ext]}', "
                    f"overwriting with '{language_name}'"
                )
            self._extension_map[ext] = language_name
        
        logger.info(
            f"Registered plugin for language '{language_name}' "
            f"with extensions: {plugin.file_extensions}"
        )
    
    def get_plugin_for_file(self, file_path: str) -> Optional[LanguagePlugin]:
        """
        Get appropriate plugin based on file extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            LanguagePlugin instance if found, None otherwise
        """
        ext = Path(file_path).suffix
        language = self._extension_map.get(ext)
        
        if language:
            return self._plugins.get(language)
        
        logger.debug(f"No plugin found for file extension '{ext}' (file: {file_path})")
        return None
    
    def get_plugin(self, language_name: str) -> Optional[LanguagePlugin]:
        """
        Get plugin by language name.
        
        Args:
            language_name: Name of the language
            
        Returns:
            LanguagePlugin instance if found, None otherwise
        """
        return self._plugins.get(language_name)
    
    def list_supported_languages(self) -> List[str]:
        """
        List all registered language plugins.
        
        Returns:
            List of language names
        """
        return list(self._plugins.keys())
    
    def list_supported_extensions(self) -> List[str]:
        """
        List all supported file extensions.
        
        Returns:
            List of file extensions
        """
        return list(self._extension_map.keys())
    
    def load_plugin_config(self, plugin_dir: Path) -> Dict:
        """
        Load plugin configuration from YAML file.
        
        Args:
            plugin_dir: Directory containing the plugin and config.yaml
            
        Returns:
            Dictionary containing plugin configuration
            
        Raises:
            FileNotFoundError: If config.yaml is not found
            yaml.YAMLError: If config.yaml is malformed
        """
        config_path = plugin_dir / "config.yaml"
        
        # Check cache first
        cache_key = str(config_path)
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]
        
        if not config_path.exists():
            raise FileNotFoundError(f"Plugin configuration not found: {config_path}")
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Validate required fields
            required_fields = ['name', 'version', 'file_extensions']
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"Missing required field '{field}' in {config_path}")
            
            # Cache the configuration
            self._config_cache[cache_key] = config
            
            logger.info(f"Loaded plugin configuration from {config_path}")
            return config
            
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse plugin configuration {config_path}: {e}")
            raise
    
    async def initialize_plugins(self, plugins_dir: Path) -> None:
        """
        Initialize all plugins from the plugins directory.
        
        This method auto-discovers plugins by scanning subdirectories
        for config.yaml files and loading plugin configurations.
        
        Args:
            plugins_dir: Path to the plugins directory
        """
        if not plugins_dir.exists():
            logger.warning(f"Plugins directory not found: {plugins_dir}")
            return
        
        logger.info(f"Initializing plugins from {plugins_dir}")
        
        # Scan for plugin directories
        for plugin_dir in plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            
            config_path = plugin_dir / "config.yaml"
            if not config_path.exists():
                logger.debug(f"Skipping {plugin_dir.name}: no config.yaml found")
                continue
            
            try:
                config = self.load_plugin_config(plugin_dir)
                logger.info(
                    f"Found plugin configuration: {config['name']} v{config['version']}"
                )
                # Note: Actual plugin instantiation will be done by specific plugin modules
                # This method just discovers and validates configurations
                
            except Exception as e:
                logger.error(f"Failed to load plugin from {plugin_dir}: {e}")
                continue
    
    def unregister_plugin(self, language_name: str) -> bool:
        """
        Unregister a plugin.
        
        Args:
            language_name: Name of the language plugin to unregister
            
        Returns:
            True if plugin was unregistered, False if not found
        """
        if language_name not in self._plugins:
            return False
        
        plugin = self._plugins[language_name]
        
        # Remove extension mappings
        for ext in plugin.file_extensions:
            if self._extension_map.get(ext) == language_name:
                del self._extension_map[ext]
        
        # Remove plugin
        del self._plugins[language_name]
        
        logger.info(f"Unregistered plugin for language '{language_name}'")
        return True
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Get plugin manager statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "total_plugins": len(self._plugins),
            "total_extensions": len(self._extension_map),
            "languages": list(self._plugins.keys())
        }
