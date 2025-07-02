# src/ava/core/plugins/plugin_system.py
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


class PluginState(Enum):
    """Plugin lifecycle states."""
    UNLOADED = "unloaded"
    LOADED = "loaded"
    STARTED = "started"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class PluginMetadata:
    """Plugin metadata and configuration."""
    name: str
    version: str
    description: str
    author: str
    dependencies: List[str] = None
    event_subscriptions: List[str] = None
    event_emissions: List[str] = None
    config_schema: Dict[str, Any] = None
    enabled_by_default: bool = True

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.event_subscriptions is None:
            self.event_subscriptions = []
        if self.event_emissions is None:
            self.event_emissions = []
        if self.config_schema is None:
            self.config_schema = {}


class PluginError(Exception):
    """Base exception for plugin-related errors."""
    pass


class PluginBase(ABC):
    """
    Abstract base class for all plugins.
    Provides the contract that all plugins must implement.
    """

    def __init__(self, event_bus, plugin_config):
        """
        Initialize the plugin with event bus and configuration.

        Args:
            event_bus: The application's central EventBus instance
            plugin_config: Configuration dictionary for this plugin
        """
        self.event_bus = event_bus
        self.config = plugin_config
        self.state = PluginState.UNLOADED
        self._subscribed_events = []
        # This will be populated by the PluginManager after initialization
        self.service_manager = None

    def set_service_manager(self, service_manager: Any):
        """
        A dedicated method for the PluginManager to inject the ServiceManager.
        This ensures plugins have access to core services after they are initialized.
        """
        self.service_manager = service_manager


    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Returns plugin metadata. Must be implemented by each plugin."""
        pass

    @abstractmethod
    async def load(self) -> bool:
        """
        Load the plugin - prepare resources, validate dependencies.

        Returns:
            True if loading succeeded, False otherwise
        """
        pass

    @abstractmethod
    async def start(self) -> bool:
        """
        Start the plugin - begin active operation, subscribe to events.

        Returns:
            True if starting succeeded, False otherwise
        """
        pass

    @abstractmethod
    async def stop(self) -> bool:
        """
        Stop the plugin - cease active operation, but keep loaded.

        Returns:
            True if stopping succeeded, False otherwise
        """
        pass

    @abstractmethod
    async def unload(self) -> bool:
        """
        Unload the plugin - clean up all resources, unsubscribe from events.

        Returns:
            True if unloading succeeded, False otherwise
        """
        pass

    def subscribe_to_event(self, event_name: str, callback):
        """
        Helper method to subscribe to events and track subscriptions.

        Args:
            event_name: Name of the event to subscribe to
            callback: Function to call when event is emitted
        """
        if not self.event_bus: return
        self.event_bus.subscribe(event_name, callback)
        self._subscribed_events.append((event_name, callback))

    def unsubscribe_all_events(self):
        """Helper method to unsubscribe from all events."""
        # Note: The current EventBus doesn't have unsubscribe functionality
        # This is a placeholder for when that feature is added
        self._subscribed_events.clear()

    def emit_event(self, event_name: str, *args, **kwargs):
        """
        Helper method to emit events through the event bus.

        Args:
            event_name: Name of the event to emit
            *args, **kwargs: Arguments to pass with the event
        """
        if not self.event_bus: return
        self.event_bus.emit(event_name, *args, **kwargs)

    def log(self, level: str, message: str):
        """
        Helper method to emit log messages.

        Args:
            level: Log level (info, warning, error, success)
            message: Log message content
        """
        self.emit_event("log_message_received", self.metadata.name, level, message)

    def get_config_value(self, key: str, default=None):
        """
        Get a configuration value for this plugin.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)

    def set_state(self, new_state: PluginState):
        """
        Update the plugin's state and emit a state change event.

        Args:
            new_state: The new state to transition to
        """
        old_state = self.state
        self.state = new_state
        self.emit_event("plugin_state_changed", self.metadata.name, old_state, new_state)


class UIPluginMixin:
    """
    Mixin for plugins that need UI components.
    Provides common UI-related functionality.
    """

    def create_status_indicator(self, widget_parent=None):
        """Creates a status indicator widget for this plugin."""
        # This will be implemented when we have specific UI needs
        pass

    def create_settings_widget(self, parent=None):
        """Creates a settings widget for plugin configuration."""
        # This will be implemented when we have specific UI needs
        pass


class BackgroundPluginMixin:
    """
    Mixin for plugins that run background tasks.
    Provides task management functionality.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._background_tasks = []

    def add_background_task(self, task):
        """Add a background task to be managed by the plugin."""
        self._background_tasks.append(task)

    async def stop_all_background_tasks(self):
        """Stop all background tasks when plugin is stopped."""
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except:
                    pass  # Ignore cancellation errors
        self._background_tasks.clear()