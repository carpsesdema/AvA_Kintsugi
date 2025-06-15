# kintsugi_ava/core/plugins/examples/hello_world/__init__.py
# Example Hello World plugin demonstrating the plugin system

import asyncio
from typing import Dict, Any

from core.plugins import PluginBase, PluginMetadata, PluginState


class HelloWorldPlugin(PluginBase):
    """
    A simple example plugin that demonstrates the plugin system capabilities.

    This plugin:
    - Subscribes to session events
    - Logs messages when events occur
    - Has configurable greeting messages
    - Demonstrates async lifecycle methods
    """

    def __init__(self, event_bus, plugin_config: Dict[str, Any]):
        super().__init__(event_bus, plugin_config)

        # Plugin-specific state
        self.session_count = 0
        self.message_count = 0

    @property
    def metadata(self) -> PluginMetadata:
        """Plugin metadata defining its capabilities and configuration."""
        return PluginMetadata(
            name="hello_world",
            version="1.0.0",
            description="A simple example plugin that greets users and tracks sessions",
            author="Kintsugi AvA Team",
            dependencies=[],  # No dependencies on other plugins
            event_subscriptions=[
                "new_session_requested",
                "user_request_submitted",
                "ai_response_ready"
            ],
            event_emissions=[
                "plugin_log_message"
            ],
            config_schema={
                "greeting_message": {
                    "type": "str",
                    "default": "Hello from the plugin system!",
                    "description": "Message to display when greeting users"
                },
                "track_sessions": {
                    "type": "bool",
                    "default": True,
                    "description": "Whether to track and count user sessions"
                },
                "max_greetings": {
                    "type": "int",
                    "default": 5,
                    "description": "Maximum number of greetings to send per session"
                }
            },
            enabled_by_default=True
        )

    async def load(self) -> bool:
        """Load the plugin - prepare resources and validate configuration."""
        try:
            self.log("info", "Hello World plugin loading...")

            # Validate configuration
            greeting = self.get_config_value("greeting_message")
            if not greeting or not isinstance(greeting, str):
                self.log("warning", "Invalid greeting message, using default")

            # Initialize state
            self.session_count = 0
            self.message_count = 0

            self.set_state(PluginState.LOADED)
            self.log("success", "Hello World plugin loaded successfully")
            return True

        except Exception as e:
            self.log("error", f"Failed to load Hello World plugin: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def start(self) -> bool:
        """Start the plugin - begin active operation and subscribe to events."""
        try:
            self.log("info", "Starting Hello World plugin...")

            # Subscribe to events we're interested in
            self.subscribe_to_event("new_session_requested", self._on_new_session)
            self.subscribe_to_event("user_request_submitted", self._on_user_request)
            self.subscribe_to_event("ai_response_ready", self._on_ai_response)

            self.set_state(PluginState.STARTED)

            # Send initial greeting
            greeting = self.get_config_value("greeting_message", "Hello from the plugin system!")
            self.log("info", f"🎉 {greeting}")

            return True

        except Exception as e:
            self.log("error", f"Failed to start Hello World plugin: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def stop(self) -> bool:
        """Stop the plugin - cease active operation but keep loaded."""
        try:
            self.log("info", "Stopping Hello World plugin...")

            # Unsubscribe from events (this would be implemented when EventBus supports it)
            self.unsubscribe_all_events()

            # Send farewell message
            self.log("info", f"👋 Goodbye! Tracked {self.session_count} sessions and {self.message_count} messages.")

            self.set_state(PluginState.STOPPED)
            return True

        except Exception as e:
            self.log("error", f"Failed to stop Hello World plugin: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def unload(self) -> bool:
        """Unload the plugin - clean up all resources."""
        try:
            self.log("info", "Unloading Hello World plugin...")

            # Clean up any resources
            self.session_count = 0
            self.message_count = 0

            self.set_state(PluginState.UNLOADED)
            self.log("info", "Hello World plugin unloaded")
            return True

        except Exception as e:
            self.log("error", f"Failed to unload Hello World plugin: {e}")
            self.set_state(PluginState.ERROR)
            return False

    # Event handlers
    def _on_new_session(self):
        """Handle new session events."""
        if not self.get_config_value("track_sessions", True):
            return

        self.session_count += 1
        self.message_count = 0  # Reset message count for new session

        self.log("info", f"🆕 New session started! (Session #{self.session_count})")

        # Send a session-specific greeting
        greeting = self.get_config_value("greeting_message", "Hello from the plugin system!")
        session_greeting = f"{greeting} This is session #{self.session_count}."

        # Emit as a log message that will appear in the terminals
        self.emit_event("log_message_received", "HelloWorld", "info", session_greeting)

    def _on_user_request(self, prompt: str, conversation_history: list):
        """Handle user request events."""
        self.message_count += 1
        max_greetings = self.get_config_value("max_greetings", 5)

        if self.message_count <= max_greetings:
            self.log("info",
                     f"📝 User message #{self.message_count}: '{prompt[:50]}{'...' if len(prompt) > 50 else ''}'")
        elif self.message_count == max_greetings + 1:
            self.log("info", "🤫 (Reached max greetings, going quiet now...)")

    def _on_ai_response(self, response: str):
        """Handle AI response events."""
        max_greetings = self.get_config_value("max_greetings", 5)

        if self.message_count <= max_greetings:
            self.log("info", f"🤖 AI responded with {len(response)} characters")

    def get_status_info(self) -> Dict[str, Any]:
        """Get plugin status information for display."""
        return {
            "session_count": self.session_count,
            "message_count": self.message_count,
            "greeting_message": self.get_config_value("greeting_message"),
            "track_sessions": self.get_config_value("track_sessions"),
            "max_greetings": self.get_config_value("max_greetings")
        }