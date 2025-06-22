import importlib
import inspect
import sys
from pathlib import Path
from typing import Dict, List, Type, Optional
import traceback

from .plugin_system import PluginBase, PluginMetadata


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
        This no longer modifies sys.path, as the application entry point
        is responsible for setting up the correct paths.

        Args:
            path: Directory path to search for plugin modules
        """
        resolved_path = path.resolve()
        if not resolved_path.exists() or not resolved_path.is_dir():
            print(f"[PluginRegistry] Warning: Discovery path does not exist: {resolved_path}")
            return

        if resolved_path not in self._discovery_paths:
            self._discovery_paths.append(resolved_path)
            print(f"[PluginRegistry] Added discovery path: {resolved_path}")

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
        if not directory.is_dir():
            print(f"[PluginRegistry] Error: Cannot scan non-existent directory {directory}")
            return 0

        # Find the correct package root from sys.path. An ancestor of the plugin directory
        # must be in sys.path for Python's import system to work. We find the longest
        # matching path to handle nested source structures correctly.
        package_root = None
        for p_str in sorted(sys.path, key=len, reverse=True):
            try:
                # Make sure the path entry is valid before creating a Path object
                if not p_str or not Path(p_str).is_dir():
                    continue
                p = Path(p_str).resolve()
                if p in directory.resolve().parents or p == directory.resolve():
                    package_root = p
                    break
            except (FileNotFoundError, OSError):
                continue

        if not package_root:
            print(
                f"[PluginRegistry] FATAL: Could not determine package root for discovery path {directory}. The parent directory or an ancestor must be in sys.path.")
            return 0

        try:
            # Look for Python packages (directories with __init__.py)
            for item in directory.iterdir():
                if item.is_dir() and (item / "__init__.py").exists():
                    try:
                        # Construct the module name relative to the found package root.
                        # e.g., 'ava.core.plugins.examples.x' from package_root '.../src'
                        # or 'my_plugin' from package_root '.../plugins'
                        module_path_str = ".".join(item.relative_to(package_root).parts)

                        if self._try_load_plugin_from_module(module_path_str):
                            count += 1
                    except Exception as e:
                        print(f"[PluginRegistry] Failed to process potential plugin at {item}: {e}")

        except Exception as e:
            print(f"[PluginRegistry] Error scanning directory {directory}: {e}")

        return count

    def _try_load_plugin_from_module(self, module_path: str) -> bool:
        """
        Attempt to load a plugin from a fully qualified module path.

        Args:
            module_path: The dot-separated path to the module (e.g., 'plugins.my_plugin')

        Returns:
            True if a plugin was successfully loaded, False otherwise
        """
        try:
            # Dynamically import the module
            module = importlib.import_module(module_path)
            print(f"[PluginRegistry] Inspecting module: {module_path}")

            # Look for plugin classes that inherit from PluginBase
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, PluginBase) and obj is not PluginBase and not inspect.isabstract(obj):
                    # Found a plugin class, now register it
                    return self._register_plugin_class(obj)

        except ImportError as e:
            print(f"[PluginRegistry] ImportError loading plugin from {module_path}: {e}")
        except Exception as e:
            # Catch other potential errors during import or inspection
            print(f"[PluginRegistry] Error loading plugin from {module_path}: {e}")
            traceback.print_exc()

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

    def _register_plugin_class(self, plugin_class: Type[PluginBase]) -> bool:
        """
        Internal method to register a plugin class.

        Args:
            plugin_class: Plugin class to register

        Returns:
            True if registration succeeded, False otherwise
        """
        try:
            # Create a temporary instance to get metadata
            # This is safe because plugins should not have side effects in __init__
            temp_instance = plugin_class(event_bus=None, plugin_config={})
            metadata = temp_instance.metadata
            plugin_name = metadata.name

            if not plugin_name:
                raise ValueError("Plugin metadata must have a 'name'.")

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
            class_name = plugin_class.__name__ if hasattr(plugin_class, '__name__') else "Unknown"
            print(f"[PluginRegistry] Error registering plugin class {class_name}: {e}")
            traceback.print_exc()
            return False

    def _validate_plugin_metadata(self, metadata: PluginMetadata) -> bool:
        """
        Validate plugin metadata for required fields and consistency.

        Args:
            metadata: Plugin metadata to validate

        Returns:
            True if metadata is valid, False otherwise
        """
        if not all([metadata.name, metadata.version, metadata.description, metadata.author]):
            print("[PluginRegistry] Validation failed: name, version, description, and author are required.")
            return False
        if not isinstance(metadata.name, str) or not metadata.name.strip():
            print("[PluginRegistry] Validation failed: name must be a non-empty string.")
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