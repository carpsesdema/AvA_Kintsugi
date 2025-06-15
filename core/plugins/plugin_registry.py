# kintsugi_ava/core/plugins/plugin_registry.py
# Plugin discovery and metadata management

import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Type, Optional
import sys

from .plugin_system import PluginBase, PluginMetadata, PluginError


class PluginRegistry:
    """
    Handles plugin discovery, registration, and metadata management.
    Single responsibility: Know what plugins exist and their metadata.
    """

    def __init__(self):
        self._registered_plugins: Dict[str, Type[PluginBase]] = {}
        self._plugin_metadata: Dict[str, PluginMetadata] = {}
        self._discovery_paths: List[Path] = []
        print("[PluginRegistry] Initialized")

    def add_discovery_path(self, path: Path):
        """
        Add a directory path to search for plugins.

        Args:
            path: Directory path to search for plugin modules
        """
        if not path.exists() or not path.is_dir():
            print(f"[PluginRegistry] Warning: Discovery path does not exist: {path}")
            return

        self._discovery_paths.append(path)
        print(f"[PluginRegistry] Added discovery path: {path}")

    def discover_plugins(self) -> int:
        """
        Scan discovery paths for plugin modules and register them.

        Returns:
            Number of plugins discovered and registered
        """
        discovered_count = 0

        for discovery_path in self._discovery_paths:
            discovered_count += self._scan_directory(discovery_path)

        print(f"[PluginRegistry] Discovery complete. Found {discovered_count} plugins.")
        return discovered_count

    def _scan_directory(self, directory: Path) -> int:
        """
        Scan a directory for plugin modules.

        Args:
            directory: Directory to scan

        Returns:
            Number of plugins found in this directory
        """
        count = 0

        try:
            # Add the parent directory to Python path if needed
            parent_path = str(directory.parent)
            if parent_path not in sys.path:
                sys.path.append(parent_path)

            # Look for Python packages (directories with __init__.py)
            for item in directory.iterdir():
                if item.is_dir() and (item / "__init__.py").exists():
                    if self._try_load_plugin_from_package(item):
                        count += 1

        except Exception as e:
            print(f"[PluginRegistry] Error scanning directory {directory}: {e}")

        return count

    def _try_load_plugin_from_package(self, package_path: Path) -> bool:
        """
        Attempt to load a plugin from a package directory.

        Args:
            package_path: Path to the plugin package directory

        Returns:
            True if plugin was successfully loaded, False otherwise
        """
        try:
            package_name = package_path.name

            # Import the package
            spec = importlib.util.spec_from_file_location(
                package_name,
                package_path / "__init__.py"
            )
            if not spec or not spec.loader:
                return False

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Look for plugin classes that inherit from PluginBase
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, PluginBase) and
                        obj is not PluginBase and
                        not inspect.isabstract(obj)):
                    return self._register_plugin_class(obj, package_name)

        except Exception as e:
            print(f"[PluginRegistry] Error loading plugin from {package_path}: {e}")

        return False

    def register_plugin_class(self, plugin_class: Type[PluginBase]) -> bool:
        """
        Manually register a plugin class.

        Args:
            plugin_class: Plugin class that inherits from PluginBase

        Returns:
            True if registration succeeded, False otherwise
        """
        return self._register_plugin_class(plugin_class)

    def _register_plugin_class(self, plugin_class: Type[PluginBase], package_name: str = None) -> bool:
        """
        Internal method to register a plugin class.

        Args:
            plugin_class: Plugin class to register
            package_name: Optional package name override

        Returns:
            True if registration succeeded, False otherwise
        """
        try:
            # Create a temporary instance to get metadata
            # This is safe because plugins should not have side effects in __init__
            temp_instance = plugin_class(None, {})
            metadata = temp_instance.metadata

            plugin_name = metadata.name

            # Check for name conflicts
            if plugin_name in self._registered_plugins:
                print(f"[PluginRegistry] Warning: Plugin '{plugin_name}' already registered. Skipping.")
                return False

            # Validate metadata
            if not self._validate_plugin_metadata(metadata):
                print(f"[PluginRegistry] Invalid metadata for plugin '{plugin_name}'. Skipping.")
                return False

            # Register the plugin
            self._registered_plugins[plugin_name] = plugin_class
            self._plugin_metadata[plugin_name] = metadata

            print(f"[PluginRegistry] Registered plugin: {plugin_name} v{metadata.version}")
            return True

        except Exception as e:
            class_name = plugin_class.__name__ if plugin_class else "Unknown"
            print(f"[PluginRegistry] Error registering plugin class {class_name}: {e}")
            return False

    def _validate_plugin_metadata(self, metadata: PluginMetadata) -> bool:
        """
        Validate plugin metadata for required fields and consistency.

        Args:
            metadata: Plugin metadata to validate

        Returns:
            True if metadata is valid, False otherwise
        """
        if not metadata.name or not isinstance(metadata.name, str):
            return False

        if not metadata.version or not isinstance(metadata.version, str):
            return False

        if not metadata.description or not isinstance(metadata.description, str):
            return False

        if not metadata.author or not isinstance(metadata.author, str):
            return False

        return True

    def get_registered_plugins(self) -> Dict[str, Type[PluginBase]]:
        """
        Get all registered plugin classes.

        Returns:
            Dictionary mapping plugin names to plugin classes
        """
        return self._registered_plugins.copy()

    def get_plugin_metadata(self, plugin_name: str) -> Optional[PluginMetadata]:
        """
        Get metadata for a specific plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin metadata or None if plugin not found
        """
        return self._plugin_metadata.get(plugin_name)

    def get_all_metadata(self) -> Dict[str, PluginMetadata]:
        """
        Get metadata for all registered plugins.

        Returns:
            Dictionary mapping plugin names to their metadata
        """
        return self._plugin_metadata.copy()

    def get_plugin_class(self, plugin_name: str) -> Optional[Type[PluginBase]]:
        """
        Get the class for a specific plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin class or None if plugin not found
        """
        return self._registered_plugins.get(plugin_name)

    def is_plugin_registered(self, plugin_name: str) -> bool:
        """
        Check if a plugin is registered.

        Args:
            plugin_name: Name of the plugin to check

        Returns:
            True if plugin is registered, False otherwise
        """
        return plugin_name in self._registered_plugins

    def unregister_plugin(self, plugin_name: str) -> bool:
        """
        Unregister a plugin.

        Args:
            plugin_name: Name of the plugin to unregister

        Returns:
            True if plugin was unregistered, False if not found
        """
        if plugin_name not in self._registered_plugins:
            return False

        del self._registered_plugins[plugin_name]
        del self._plugin_metadata[plugin_name]

        print(f"[PluginRegistry] Unregistered plugin: {plugin_name}")
        return True

    def get_plugins_by_dependency(self, dependency: str) -> List[str]:
        """
        Get all plugins that depend on a specific plugin.

        Args:
            dependency: Name of the dependency plugin

        Returns:
            List of plugin names that depend on the given plugin
        """
        dependent_plugins = []

        for plugin_name, metadata in self._plugin_metadata.items():
            if dependency in metadata.dependencies:
                dependent_plugins.append(plugin_name)

        return dependent_plugins

    def check_dependencies(self, plugin_name: str) -> List[str]:
        """
        Check if all dependencies for a plugin are available.

        Args:
            plugin_name: Name of the plugin to check

        Returns:
            List of missing dependency names (empty if all dependencies are met)
        """
        metadata = self.get_plugin_metadata(plugin_name)
        if not metadata:
            return [f"Plugin '{plugin_name}' not found"]

        missing_deps = []
        for dependency in metadata.dependencies:
            if not self.is_plugin_registered(dependency):
                missing_deps.append(dependency)

        return missing_deps