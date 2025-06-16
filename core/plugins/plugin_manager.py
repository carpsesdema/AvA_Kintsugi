# kintsugi_ava/core/plugins/plugin_manager.py
# Plugin lifecycle management and coordination

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Set
from collections import defaultdict

from .plugin_system import PluginBase, PluginState, PluginError
from .plugin_registry import PluginRegistry
from .plugin_config import PluginConfig


class PluginManager:
    """
    Central coordinator for the plugin system.
    Single responsibility: Manage plugin lifecycle and dependencies.
    """

    def __init__(self, event_bus, config_file_path: str = "config/plugins.json"):
        self.event_bus = event_bus
        self.registry = PluginRegistry()
        self.config = PluginConfig(config_file_path)

        # Active plugin instances
        self._active_plugins: Dict[str, PluginBase] = {}

        # Dependency tracking
        self._dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self._reverse_dependencies: Dict[str, Set[str]] = defaultdict(set)

        # State tracking
        self._plugin_states: Dict[str, PluginState] = {}

        # Event subscriptions
        self._connect_events()

        print("[PluginManager] Initialized")

    def _connect_events(self):
        """Connect to event bus for plugin-related events."""
        self.event_bus.subscribe("plugin_state_changed", self._on_plugin_state_changed)

        # Wrap the async handler in asyncio.create_task to prevent the "never awaited" warning.
        # This correctly fires the async shutdown sequence from a sync event call.
        self.event_bus.subscribe("application_shutdown",
                                 lambda: asyncio.create_task(self.shutdown()))

    def add_discovery_path(self, path: Path):
        """
        Add a path for plugin discovery.

        Args:
            path: Directory path to search for plugins
        """
        self.registry.add_discovery_path(path)

    async def initialize(self) -> bool:
        """
        Initialize the plugin system - discover plugins and load enabled ones.

        Returns:
            True if initialization succeeded, False otherwise
        """
        try:
            # Discover plugins
            discovered_count = self.registry.discover_plugins()

            if discovered_count == 0:
                print("[PluginManager] No plugins discovered")
                return True

            # Apply default settings for newly discovered plugins
            all_metadata = self.registry.get_all_metadata()
            for plugin_name, metadata in all_metadata.items():
                self.config.apply_defaults_for_plugin(plugin_name, metadata)

            # Enable plugins that should be enabled by default
            self.config.enable_plugins_by_default(all_metadata)

            # Build dependency graph
            self._build_dependency_graph()

            # Load enabled plugins in dependency order
            enabled_plugins = self.config.get_enabled_plugins()
            load_order = self._calculate_load_order(enabled_plugins)

            success_count = 0
            for plugin_name in load_order:
                if await self.load_plugin(plugin_name):
                    success_count += 1

            print(f"[PluginManager] Initialization complete. {success_count}/{len(load_order)} plugins loaded.")

            # Save any configuration changes
            self.config.save_config()

            return True

        except Exception as e:
            print(f"[PluginManager] Error during initialization: {e}")
            return False

    def _build_dependency_graph(self):
        """Build internal dependency tracking structures."""
        self._dependency_graph.clear()
        self._reverse_dependencies.clear()

        all_metadata = self.registry.get_all_metadata()

        for plugin_name, metadata in all_metadata.items():
            # Direct dependencies
            for dependency in metadata.dependencies:
                self._dependency_graph[plugin_name].add(dependency)
                self._reverse_dependencies[dependency].add(plugin_name)

    def _calculate_load_order(self, plugin_names: Set[str]) -> List[str]:
        """
        Calculate the order to load plugins based on dependencies.

        Args:
            plugin_names: Set of plugin names to order

        Returns:
            List of plugin names in load order
        """
        # Topological sort implementation
        visited = set()
        temp_visited = set()
        load_order = []

        def visit(plugin_name: str):
            if plugin_name in temp_visited:
                # Circular dependency detected
                print(f"[PluginManager] Warning: Circular dependency involving {plugin_name}")
                return

            if plugin_name in visited:
                return

            temp_visited.add(plugin_name)

            # Visit dependencies first
            for dependency in self._dependency_graph.get(plugin_name, set()):
                if dependency in plugin_names:  # Only consider enabled plugins
                    visit(dependency)

            temp_visited.remove(plugin_name)
            visited.add(plugin_name)
            load_order.append(plugin_name)

        # Visit all plugins
        for plugin_name in plugin_names:
            if plugin_name not in visited:
                visit(plugin_name)

        return load_order

    async def load_plugin(self, plugin_name: str) -> bool:
        """
        Load a specific plugin.

        Args:
            plugin_name: Name of the plugin to load

        Returns:
            True if loading succeeded, False otherwise
        """
        if plugin_name in self._active_plugins:
            print(f"[PluginManager] Plugin '{plugin_name}' is already loaded")
            return True

        # Check if plugin is registered
        plugin_class = self.registry.get_plugin_class(plugin_name)
        if not plugin_class:
            print(f"[PluginManager] Plugin '{plugin_name}' not found in registry")
            return False

        # Check dependencies
        missing_deps = self.registry.check_dependencies(plugin_name)
        if missing_deps:
            print(f"[PluginManager] Cannot load '{plugin_name}': missing dependencies {missing_deps}")
            return False

        try:
            # Get plugin metadata and settings
            metadata = self.registry.get_plugin_metadata(plugin_name)
            settings = self.config.validate_plugin_settings(plugin_name, metadata)

            # Create plugin instance
            plugin_instance = plugin_class(self.event_bus, settings)

            # Load the plugin
            if await plugin_instance.load():
                self._active_plugins[plugin_name] = plugin_instance
                self._plugin_states[plugin_name] = PluginState.LOADED

                print(f"[PluginManager] Loaded plugin: {plugin_name}")

                # Auto-start if plugin was enabled
                if self.config.is_plugin_enabled(plugin_name):
                    return await self.start_plugin(plugin_name)

                return True
            else:
                print(f"[PluginManager] Failed to load plugin: {plugin_name}")
                return False

        except Exception as e:
            print(f"[PluginManager] Error loading plugin '{plugin_name}': {e}")
            return False

    async def start_plugin(self, plugin_name: str) -> bool:
        """
        Start a loaded plugin.

        Args:
            plugin_name: Name of the plugin to start

        Returns:
            True if starting succeeded, False otherwise
        """
        plugin = self._active_plugins.get(plugin_name)
        if not plugin:
            print(f"[PluginManager] Cannot start '{plugin_name}': not loaded")
            return False

        if plugin.state == PluginState.STARTED:
            print(f"[PluginManager] Plugin '{plugin_name}' is already started")
            return True

        try:
            if await plugin.start():
                self._plugin_states[plugin_name] = PluginState.STARTED
                print(f"[PluginManager] Started plugin: {plugin_name}")
                return True
            else:
                print(f"[PluginManager] Failed to start plugin: {plugin_name}")
                return False

        except Exception as e:
            print(f"[PluginManager] Error starting plugin '{plugin_name}': {e}")
            self._plugin_states[plugin_name] = PluginState.ERROR
            return False

    async def stop_plugin(self, plugin_name: str) -> bool:
        """
        Stop a running plugin.

        Args:
            plugin_name: Name of the plugin to stop

        Returns:
            True if stopping succeeded, False otherwise
        """
        plugin = self._active_plugins.get(plugin_name)
        if not plugin:
            print(f"[PluginManager] Cannot stop '{plugin_name}': not loaded")
            return False

        if plugin.state != PluginState.STARTED:
            print(f"[PluginManager] Plugin '{plugin_name}' is not running")
            return True

        # Check if other plugins depend on this one
        dependents = self._reverse_dependencies.get(plugin_name, set())
        running_dependents = [dep for dep in dependents
                              if dep in self._active_plugins and
                              self._active_plugins[dep].state == PluginState.STARTED]

        if running_dependents:
            print(f"[PluginManager] Cannot stop '{plugin_name}': required by {running_dependents}")
            return False

        try:
            if await plugin.stop():
                self._plugin_states[plugin_name] = PluginState.STOPPED
                print(f"[PluginManager] Stopped plugin: {plugin_name}")
                return True
            else:
                print(f"[PluginManager] Failed to stop plugin: {plugin_name}")
                return False

        except Exception as e:
            print(f"[PluginManager] Error stopping plugin '{plugin_name}': {e}")
            self._plugin_states[plugin_name] = PluginState.ERROR
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a plugin.

        Args:
            plugin_name: Name of the plugin to unload

        Returns:
            True if unloading succeeded, False otherwise
        """
        plugin = self._active_plugins.get(plugin_name)
        if not plugin:
            print(f"[PluginManager] Plugin '{plugin_name}' is not loaded")
            return True

        # Stop plugin first if it's running
        if plugin.state == PluginState.STARTED:
            if not await self.stop_plugin(plugin_name):
                return False

        try:
            if await plugin.unload():
                del self._active_plugins[plugin_name]
                self._plugin_states[plugin_name] = PluginState.UNLOADED
                print(f"[PluginManager] Unloaded plugin: {plugin_name}")
                return True
            else:
                print(f"[PluginManager] Failed to unload plugin: {plugin_name}")
                return False

        except Exception as e:
            print(f"[PluginManager] Error unloading plugin '{plugin_name}': {e}")
            self._plugin_states[plugin_name] = PluginState.ERROR
            return False

    async def enable_plugin(self, plugin_name: str) -> bool:
        """
        Enable and start a plugin.

        Args:
            plugin_name: Name of the plugin to enable

        Returns:
            True if enabling succeeded, False otherwise
        """
        if not self.registry.is_plugin_registered(plugin_name):
            print(f"[PluginManager] Cannot enable '{plugin_name}': not registered")
            return False

        # Enable in configuration
        self.config.enable_plugin(plugin_name)

        # Load and start if not already loaded
        if plugin_name not in self._active_plugins:
            if not await self.load_plugin(plugin_name):
                self.config.disable_plugin(plugin_name)  # Rollback
                return False

        if self._active_plugins[plugin_name].state != PluginState.STARTED:
            if not await self.start_plugin(plugin_name):
                self.config.disable_plugin(plugin_name)  # Rollback
                return False

        self.config.save_config()
        return True

    async def disable_plugin(self, plugin_name: str) -> bool:
        """
        Disable and stop a plugin.

        Args:
            plugin_name: Name of the plugin to disable

        Returns:
            True if disabling succeeded, False otherwise
        """
        # Disable in configuration
        self.config.disable_plugin(plugin_name)

        # Stop plugin if it's running
        if plugin_name in self._active_plugins:
            await self.stop_plugin(plugin_name)

        self.config.save_config()
        return True

    def get_active_plugin_instance(self, plugin_name: str) -> Optional[PluginBase]:
        """
        Retrieves an active plugin instance if it's loaded or started.

        Args:
            plugin_name: The name of the plugin.

        Returns:
            The plugin instance, or None if not active.
        """
        plugin = self._active_plugins.get(plugin_name)
        if plugin and plugin.state in [PluginState.LOADED, PluginState.STARTED]:
            return plugin
        return None

    def get_plugin_status(self, plugin_name: str) -> Dict[str, any]:
        """
        Get status information for a plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Dictionary containing plugin status
        """
        metadata = self.registry.get_plugin_metadata(plugin_name)
        plugin = self._active_plugins.get(plugin_name)

        return {
            "name": plugin_name,
            "registered": metadata is not None,
            "enabled": self.config.is_plugin_enabled(plugin_name),
            "loaded": plugin is not None,
            "state": plugin.state.value if plugin else PluginState.UNLOADED.value,
            "metadata": metadata,
            "dependencies": metadata.dependencies if metadata else [],
            "missing_dependencies": self.registry.check_dependencies(plugin_name) if metadata else []
        }

    def get_all_plugin_status(self) -> Dict[str, Dict[str, any]]:
        """
        Get status for all registered plugins.

        Returns:
            Dictionary mapping plugin names to their status
        """
        all_status = {}
        for plugin_name in self.registry.get_registered_plugins():
            all_status[plugin_name] = self.get_plugin_status(plugin_name)
        return all_status

    async def shutdown(self):
        """Shutdown all plugins in reverse dependency order."""
        print("[PluginManager] Shutting down plugins...")

        # Get all active plugins in reverse dependency order
        active_plugin_names = set(self._active_plugins.keys())
        unload_order = list(reversed(self._calculate_load_order(active_plugin_names)))

        for plugin_name in unload_order:
            await self.unload_plugin(plugin_name)

        print("[PluginManager] Plugin shutdown complete")

    def _on_plugin_state_changed(self, plugin_name: str, old_state: PluginState, new_state: PluginState):
        """Handle plugin state change events."""
        self._plugin_states[plugin_name] = new_state
        print(f"[PluginManager] Plugin '{plugin_name}' state: {old_state.value} -> {new_state.value}")