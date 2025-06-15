# kintsugi_ava/core/plugins/__init__.py
# Plugin framework exports

from .plugin_system import PluginBase, PluginMetadata, PluginState, PluginError
from .plugin_manager import PluginManager
from .plugin_registry import PluginRegistry
from .plugin_config import PluginConfig

__all__ = [
    'PluginBase',
    'PluginMetadata',
    'PluginState',
    'PluginError',
    'PluginManager',
    'PluginRegistry',
    'PluginConfig'
]