# kintsugi_ava/core/managers/event_coordinator.py
# Centralized event subscription management
# V2: Added plugin system event wiring

import asyncio
from core.event_bus import EventBus


class EventCoordinator:
    """
    Centralized event subscription coordinator.
    Single responsibility: Wire up all event subscriptions between components.
    V2: Now includes plugin system event wiring.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        # Manager references (set by Application)
        self.service_manager = None
        self.window_manager = None
        self.workflow_manager = None
        self.task_manager = None

        print("[EventCoordinator] Initialized")

    def set_managers(self, service_manager, window_manager, workflow_manager, task_manager):
        """
        Set references to other managers for event coordination.

        Args:
            service_manager: ServiceManager instance
            window_manager: WindowManager instance
            workflow_manager: WorkflowManager instance
            task_manager: TaskManager instance
        """
        self.service_manager = service_manager
        self.window_manager = window_manager
        self.workflow_manager = workflow_manager
        self.task_manager = task_manager

    def wire_all_events(self):
        """Wire up all event subscriptions."""
        print("[EventCoordinator] Wiring event subscriptions...")

        self._wire_project_and_session_events()
        self._wire_workflow_events()
        self._wire_ui_and_window_events()
        self._wire_code_generation_events()
        self._wire_execution_events()
        self._wire_tool_events()
        self._wire_plugin_events()

        print("[EventCoordinator] Event wiring complete")

    def _wire_project_and_session_events(self):
        """Wire project and session management events."""
        self.event_bus.subscribe("new_project_requested", self.workflow_manager.handle_new_project)
        self.event_bus.subscribe("load_project_requested", self.workflow_manager.handle_load_project)
        self.event_bus.subscribe("new_session_requested", self.workflow_manager.handle_new_session)

    def _wire_workflow_events(self):
        """Wire AI workflow and user request events."""
        self.event_bus.subscribe("user_request_submitted", self.workflow_manager.handle_user_request)
        self.event_bus.subscribe("review_and_fix_requested", self.workflow_manager.handle_review_and_fix)

    def _wire_ui_and_window_events(self):
        """Wire UI updates and window visibility events."""
        # Window visibility
        self.event_bus.subscribe("show_code_viewer_requested", self.window_manager.show_code_viewer)
        self.event_bus.subscribe("show_workflow_monitor_requested", self.window_manager.show_workflow_monitor)
        self.event_bus.subscribe("show_terminals_requested", self.window_manager.show_terminals)

        # UI updates
        main_window = self.window_manager.get_main_window()
        terminals = self.window_manager.get_terminals()
        workflow_monitor = self.window_manager.get_workflow_monitor()
        code_viewer = self.window_manager.get_code_viewer()

        if main_window and hasattr(main_window, 'chat_interface'):
            self.event_bus.subscribe("ai_response_ready", main_window.chat_interface._add_ai_response)

        if terminals:
            self.event_bus.subscribe("log_message_received", terminals.add_log_message)

        if workflow_monitor and hasattr(workflow_monitor, 'scene'):
            self.event_bus.subscribe("node_status_changed", workflow_monitor.scene.update_node_status)

        if code_viewer and hasattr(code_viewer, 'statusBar'):
            self.event_bus.subscribe("branch_updated", code_viewer.statusBar().on_branch_updated)

    def _wire_code_generation_events(self):
        """Wire code generation and streaming events."""
        code_viewer = self.window_manager.get_code_viewer()

        if code_viewer:
            self.event_bus.subscribe("prepare_for_generation", code_viewer.prepare_for_generation)
            self.event_bus.subscribe("stream_code_chunk", code_viewer.stream_code_chunk)
            self.event_bus.subscribe("code_generation_complete", code_viewer.display_code)
            self.event_bus.subscribe("error_highlight_requested", code_viewer.highlight_error_in_editor)

    def _wire_execution_events(self):
        """Wire execution and terminal events."""
        terminal_service = self.service_manager.get_terminal_service()
        code_viewer = self.window_manager.get_code_viewer()

        if terminal_service:
            self.event_bus.subscribe("terminal_command_entered", self.task_manager.handle_terminal_command)

        if code_viewer and hasattr(code_viewer, 'terminal'):
            self.event_bus.subscribe("terminal_output_received", code_viewer.terminal.append_output)

        # Execution failure handling
        self.event_bus.subscribe("execution_failed", self.workflow_manager.handle_execution_failed)

    def _wire_tool_events(self):
        """Wire tool and configuration events."""
        model_config_dialog = self.window_manager.get_model_config_dialog()
        rag_manager = self.service_manager.get_rag_manager()

        if model_config_dialog:
            self.event_bus.subscribe("configure_models_requested", model_config_dialog.exec)

        if rag_manager:
            main_window = self.window_manager.get_main_window()
            self.event_bus.subscribe("launch_rag_server_requested",
                                     lambda: rag_manager.launch_rag_server(main_window))

    def _wire_plugin_events(self):
        """Wire plugin system events."""
        plugin_manager = self.service_manager.get_plugin_manager()
        terminals = self.window_manager.get_terminals()
        main_window = self.window_manager.get_main_window()

        if not plugin_manager:
            print("[EventCoordinator] Plugin manager not available, skipping plugin event wiring")
            return

        # Plugin management events
        self.event_bus.subscribe("plugin_management_requested", self.window_manager.show_plugin_management_dialog)

        # --- THIS IS THE FIX ---
        # The event bus is sync, but the handlers are async. We use a lambda to schedule the
        # async handler as a task on the event loop, preventing the "never awaited" warning.
        self.event_bus.subscribe("plugin_enable_requested",
                                 lambda name: asyncio.create_task(self._handle_plugin_enable_request(name)))
        self.event_bus.subscribe("plugin_disable_requested",
                                 lambda name: asyncio.create_task(self._handle_plugin_disable_request(name)))
        self.event_bus.subscribe("plugin_reload_requested",
                                 lambda name: asyncio.create_task(self._handle_plugin_reload_request(name)))
        # ----------------------

        self.event_bus.subscribe("plugin_settings_requested", self._handle_plugin_settings_request)

        # Plugin status and logging
        if terminals:
            # Route plugin log messages to the terminals window
            self.event_bus.subscribe("plugin_log_message",
                                     lambda plugin_name, level, message:
                                     terminals.add_log_message(f"Plugin:{plugin_name}", level, message))

        # Plugin state change notifications
        self.event_bus.subscribe("plugin_state_changed", self._handle_plugin_state_changed)

        # UI refresh events for plugin status updates
        self.event_bus.subscribe("plugin_status_refresh_requested", self._handle_plugin_status_refresh)

        print("[EventCoordinator] Plugin events wired")

    async def _handle_plugin_enable_request(self, plugin_name: str):
        """Handle plugin enable request."""
        plugin_manager = self.service_manager.get_plugin_manager()
        if plugin_manager:
            success = await plugin_manager.enable_plugin(plugin_name)
            if success:
                self.event_bus.emit("log_message_received", "PluginSystem", "success",
                                    f"Plugin '{plugin_name}' enabled successfully")
                self.event_bus.emit("plugin_status_refresh_requested")
            else:
                self.event_bus.emit("log_message_received", "PluginSystem", "error",
                                    f"Failed to enable plugin '{plugin_name}'")

    async def _handle_plugin_disable_request(self, plugin_name: str):
        """Handle plugin disable request."""
        plugin_manager = self.service_manager.get_plugin_manager()
        if plugin_manager:
            success = await plugin_manager.disable_plugin(plugin_name)
            if success:
                self.event_bus.emit("log_message_received", "PluginSystem", "success",
                                    f"Plugin '{plugin_name}' disabled successfully")
                self.event_bus.emit("plugin_status_refresh_requested")
            else:
                self.event_bus.emit("log_message_received", "PluginSystem", "error",
                                    f"Failed to disable plugin '{plugin_name}'")

    async def _handle_plugin_reload_request(self, plugin_name: str):
        """Handle plugin reload request."""
        plugin_manager = self.service_manager.get_plugin_manager()
        if plugin_manager:
            # Disable then re-enable to reload
            self.event_bus.emit("log_message_received", "PluginSystem", "info",
                                f"Reloading plugin '{plugin_name}'...")
            disable_success = await plugin_manager.disable_plugin(plugin_name)
            if disable_success:
                enable_success = await plugin_manager.enable_plugin(plugin_name)
                if enable_success:
                    self.event_bus.emit("log_message_received", "PluginSystem", "success",
                                        f"Plugin '{plugin_name}' reloaded successfully")
                else:
                    self.event_bus.emit("log_message_received", "PluginSystem", "error",
                                        f"Failed to reload plugin '{plugin_name}' - enable failed")
            else:
                self.event_bus.emit("log_message_received", "PluginSystem", "error",
                                    f"Failed to reload plugin '{plugin_name}' - disable failed")

            self.event_bus.emit("plugin_status_refresh_requested")

    def _handle_plugin_settings_request(self, plugin_name: str):
        """Handle plugin settings request."""
        # This would open a plugin settings dialog
        # For now, just log that settings were requested
        self.event_bus.emit("log_message_received", "PluginSystem", "info",
                            f"Settings requested for plugin '{plugin_name}' (not yet implemented)")

    def _handle_plugin_state_changed(self, plugin_name: str, old_state, new_state):
        """Handle plugin state change."""
        self.event_bus.emit("log_message_received", "PluginSystem", "info",
                            f"Plugin '{plugin_name}' state changed: {old_state.value} -> {new_state.value}")

    def _handle_plugin_status_refresh(self):
        """Handle plugin status refresh request."""
        # This would refresh any plugin status displays in the UI
        # For now, just log that a refresh was requested
        self.event_bus.emit("log_message_received", "PluginSystem", "info",
                            "Plugin status refresh requested")

    def get_subscription_status(self) -> dict:
        """Get status of event subscriptions for debugging."""
        plugin_events_count = 0
        if self.service_manager and self.service_manager.get_plugin_manager():
            # Count plugin-related events
            plugin_events = [
                "plugin_enable_requested", "plugin_disable_requested", "plugin_reload_requested",
                "plugin_settings_requested", "plugin_log_message", "plugin_state_changed",
                "plugin_status_refresh_requested"
            ]
            plugin_events_count = len(plugin_events)

        return {
            "managers_set": all([
                self.service_manager,
                self.window_manager,
                self.workflow_manager,
                self.task_manager
            ]),
            "event_bus_available": self.event_bus is not None,
            "subscription_count": len(self.event_bus._subscribers) if hasattr(self.event_bus, '_subscribers') else 0,
            "plugin_events_wired": plugin_events_count > 0,
            "plugin_events_count": plugin_events_count
        }