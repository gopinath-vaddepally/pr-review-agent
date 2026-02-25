"""
Language plugin architecture for code analysis.

This package provides the plugin system for language-specific code analysis,
including the base plugin interface and plugin manager.
"""

from plugins.base import LanguagePlugin
from plugins.manager import PluginManager

__all__ = ['LanguagePlugin', 'PluginManager']
