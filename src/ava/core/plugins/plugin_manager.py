# src/ava/core/plugins/plugin_manager.py
# Plugin lifecycle management and coordination

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from collections import defaultdict

from src.ava.core.plugins.plugin_system import PluginBase, PluginState, PluginError
from src.ava.core.plugins.plugin_registry import PluginRegistry
from src.ava.core.plugins.plugin_config import PluginConfig


class PluginManager:
    """
    Central coordinator for the plugin system.
    Single responsibility: Manage plugin lifecycle and dependencies.
    """

    def __init__(self, event_bus, project_root: Path):
        self.event_bus = event_bus
        self.registry = PluginRegistry()
        self.config = PluginConfig(project_root)
        self.service_manager = None  # Will be set by Application

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

    def set_service_manager(self, service_manager: Any):
        """Receives the ServiceManager to inject into plugins."""
        self.service_manager = service_manager

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
            plugin_names: Set of plugin names to load

        Returns:
            Ordered list of plugin names to load
        """
        # Topological sort
        visited = set()
        order = []

        def visit(name: str):
            if name in visited:
                return
            visited.add(name)

            # Visit dependencies first
            for dep in self._dependency_graph.get(name, []):
                if dep in plugin_names:  # Only visit if it's in our load set
                    visit(dep)

            order.append(name)

        for plugin_name in plugin_names:
            visit(plugin_name)

        return order

    async def load_plugin(self, plugin_name: str) -> bool:
        """
        Load a plugin (create instance, call load()).

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

            # --- NEW: Service Manager Injection ---
            if self.service_manager and hasattr(plugin_instance, 'set_service_manager'):
                plugin_instance.set_service_manager(self.service_manager)
                print(f"[PluginManager] Injected ServiceManager into '{plugin_name}'.")
            # --- END NEW ---

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
        if plugin_name not in self._active_plugins:
            print(f"[PluginManager] Cannot start unloaded plugin: {plugin_name}")
            return False

        plugin = self._active_plugins[plugin_name]

        if plugin.state == PluginState.STARTED:
            print(f"[PluginManager] Plugin '{plugin_name}' is already started")
            return True

        try:
            if await plugin.start():
                self._plugin_states[plugin_name] = PluginState.STARTED
                self.config.enable_plugin(plugin_name)
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
        if plugin_name not in self._active_plugins:
            print(f"[PluginManager] Cannot stop unloaded plugin: {plugin_name}")
            return False

        plugin = self._active_plugins[plugin_name]

        if plugin.state != PluginState.STARTED:
            print(f"[PluginManager] Plugin '{plugin_name}' is not running")
            return True

        try:
            # Check if any active plugins depend on this one
            active_dependents = [
                dep for dep in self._reverse_dependencies.get(plugin_name, [])
                if dep in self._active_plugins and
                self._plugin_states.get(dep) == PluginState.STARTED
            ]

            if active_dependents:
                print(f"[PluginManager] Cannot stop '{plugin_name}': active dependents {active_dependents}")
                return False

            if await plugin.stop():
                self._plugin_states[plugin_name] = PluginState.STOPPED
                self.config.disable_plugin(plugin_name)
                print(f"[PluginManager] Stopped plugin: {plugin_name}")
                return True
            else:
                print(f"[PluginManager] Failed to stop plugin: {plugin_name}")
                return False

        except Exception as e:
            print(f"[PluginManager] Error stopping plugin '{plugin_name}': {e}")
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a plugin completely.

        Args:
            plugin_name: Name of the plugin to unload

        Returns:
            True if unloading succeeded, False otherwise
        """
        if plugin_name not in self._active_plugins:
            print(f"[PluginManager] Plugin '{plugin_name}' is not loaded")
            return True

        # Stop first if running
        if self._plugin_states.get(plugin_name) == PluginState.STARTED:
            if not await self.stop_plugin(plugin_name):
                return False

        plugin = self._active_plugins[plugin_name]

        try:
            if await plugin.unload():
                del self._active_plugins[plugin_name]
                del self._plugin_states[plugin_name]
                print(f"[PluginManager] Unloaded plugin: {plugin_name}")
                return True
            else:
                print(f"[PluginManager] Failed to unload plugin: {plugin_name}")
                return False

        except Exception as e:
            print(f"[PluginManager] Error unloading plugin '{plugin_name}': {e}")
            return False

    async def reload_plugin(self, plugin_name: str) -> bool:
        """
        Reload a plugin (unload then load again).

        Args:
            plugin_name: Name of the plugin to reload

        Returns:
            True if reloading succeeded, False otherwise
        """
        was_started = self._plugin_states.get(plugin_name) == PluginState.STARTED

        # Unload first
        if not await self.unload_plugin(plugin_name):
            return False

        # Then load again
        if not await self.load_plugin(plugin_name):
            return False

        # Restart if it was running before
        if was_started:
            return await self.start_plugin(plugin_name)

        return True

    async def shutdown(self):
        """Shutdown all plugins in reverse dependency order."""
        print("[PluginManager] Starting plugin system shutdown...")

        # Get all active plugins in reverse load order
        active_names = list(self._active_plugins.keys())
        shutdown_order = list(reversed(self._calculate_load_order(set(active_names))))

        # Stop and unload each plugin
        for plugin_name in shutdown_order:
            try:
                await self.unload_plugin(plugin_name)
            except Exception as e:
                print(f"[PluginManager] Error shutting down plugin '{plugin_name}': {e}")

        # Save configuration
        self.config.save_config()

        print("[PluginManager] Plugin system shutdown complete")

    def get_plugin_info(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Dictionary with plugin info or None if not found
        """
        metadata = self.registry.get_plugin_metadata(plugin_name)
        if not metadata:
            return None

        return {
            "name": plugin_name,
            "version": metadata.version,
            "description": metadata.description,
            "author": metadata.author,
            "state": self._plugin_states.get(plugin_name, PluginState.UNLOADED).value,
            "enabled": self.config.is_plugin_enabled(plugin_name),
            "dependencies": metadata.dependencies,
            "dependents": list(self._reverse_dependencies.get(plugin_name, [])),
        }

    def get_all_plugins_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all registered plugins.

        Returns:
            List of plugin info dictionaries
        """
        all_metadata = self.registry.get_all_metadata()
        return [
            self.get_plugin_info(plugin_name)
            for plugin_name in all_metadata.keys()
        ]

    def _on_plugin_state_changed(self, plugin_name: str, old_state: PluginState, new_state: PluginState):
        """Handle plugin state change events."""
        print(f"[PluginManager] Plugin '{plugin_name}' state changed from {old_state.value} to: {new_state.value}")
        self._plugin_states[plugin_name] = new_state