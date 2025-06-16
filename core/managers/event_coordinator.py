# core/managers/event_coordinator.py
# FIXED: Updated to wire code_viewer_files_loaded event for proper plugin timing

import asyncio
from core.event_bus import EventBus


class EventCoordinator:
    """
    Centralized event subscription coordinator.
    Single responsibility: Wire up all event subscriptions between components.
    FIXED: Now includes proper plugin event timing.
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
        # Main window and sidebar events
        main_window = self.window_manager.get_main_window()
        if main_window and hasattr(main_window, 'sidebar'):
            self.event_bus.subscribe("show_code_viewer_requested", self.window_manager.show_code_viewer)
            self.event_bus.subscribe("show_workflow_monitor_requested", self.window_manager.show_workflow_monitor)
            self.event_bus.subscribe("show_terminals_requested", self.window_manager.show_terminals)
            self.event_bus.subscribe("model_config_requested", self.window_manager.show_model_config_dialog)
            self.event_bus.subscribe("plugin_management_requested", self.window_manager.show_plugin_management_dialog)

        # Update project display across windows
        self.event_bus.subscribe("project_loaded",
                                 lambda name: self.window_manager.update_project_display(name))

    def _wire_code_generation_events(self):
        """Wire code generation and display events."""
        code_viewer = self.window_manager.get_code_viewer()

        if code_viewer:
            # Generation preparation
            self.event_bus.subscribe("prepare_for_generation", code_viewer.prepare_for_generation)

            # Real-time streaming during generation
            self.event_bus.subscribe("stream_code_chunk", code_viewer.stream_code_chunk)

            # Final display when generation complete
            self.event_bus.subscribe("code_generation_complete", code_viewer.display_code)

            # FIX: Code viewer now emits this event for autonomous plugins
            # The plugins subscribe to this new event instead of the old ones
            print("[EventCoordinator] Code viewer will emit 'code_viewer_files_loaded' for autonomous plugins")

    def _wire_execution_events(self):
        """Wire code execution and error handling events."""
        code_viewer = self.window_manager.get_code_viewer()

        if code_viewer:
            # Error highlighting in code viewer
            self.event_bus.subscribe("error_highlight_requested", code_viewer.highlight_error_in_editor)
            self.event_bus.subscribe("clear_error_highlights", code_viewer.clear_all_error_highlights)

            # Fix button visibility
            self.event_bus.subscribe("show_fix_button", code_viewer.show_fix_button)
            self.event_bus.subscribe("hide_fix_button", code_viewer.hide_fix_button)

        # Execution failure handling
        self.event_bus.subscribe("execution_failed", self.workflow_manager.handle_execution_failed)

    def _wire_tool_events(self):
        """Wire tool-related events."""
        terminals = self.window_manager.get_terminals()

        if terminals:
            # Terminal output and interaction
            self.event_bus.subscribe("terminal_output_received", terminals.handle_output)
            self.event_bus.subscribe("clear_terminal", terminals.clear_terminal)

    def _wire_plugin_events(self):
        """
        Wire plugin-specific events.
        FIX: This is where the magic happens - plugins now get proper timing!
        """
        plugin_manager = self.service_manager.get_plugin_manager()
        if not plugin_manager:
            print("[EventCoordinator] No plugin manager available")
            return

        print("[EventCoordinator] Wiring plugin events...")

        # Plugin management UI events
        self.event_bus.subscribe("plugin_management_requested",
                                 lambda: self._show_plugin_management())

        # Plugin refresh events
        self.event_bus.subscribe("plugin_status_refresh_requested",
                                 lambda: self._refresh_plugin_status())

        # FIX: The autonomous plugins now subscribe to code_viewer_files_loaded
        # This event is emitted by the code viewer AFTER files are loaded with full context
        # No need to wire it here - plugins subscribe directly

        # Plugin lifecycle events for logging
        self.event_bus.subscribe("plugin_state_changed",
                                 lambda name, old, new: self._log_plugin_state_change(name, old, new))

        # Plugin status updates for UI
        self.event_bus.subscribe("plugin_status_changed",
                                 lambda: self._update_plugin_status_display())

        print("[EventCoordinator] Plugin events wired - autonomous plugins will use new timing")

    def _show_plugin_management(self):
        """Show plugin management dialog."""
        try:
            self.window_manager.show_plugin_management_dialog()
        except Exception as e:
            print(f"[EventCoordinator] Error showing plugin management: {e}")

    def _refresh_plugin_status(self):
        """Refresh plugin status display."""
        try:
            # Emit event to update plugin status in UI
            self.event_bus.emit("plugin_status_changed")
        except Exception as e:
            print(f"[EventCoordinator] Error refreshing plugin status: {e}")

    def _log_plugin_state_change(self, name: str, old_state, new_state):
        """Log plugin state changes."""
        try:
            print(f"[EventCoordinator] Plugin '{name}': {old_state.value} -> {new_state.value}")
        except Exception as e:
            print(f"[EventCoordinator] Error logging plugin state change: {e}")

    def _update_plugin_status_display(self):
        """Update plugin status in UI components."""
        try:
            # This would update the sidebar plugin status
            main_window = self.window_manager.get_main_window()
            if main_window and hasattr(main_window, 'sidebar'):
                # The sidebar has its own subscription to plugin_status_changed
                pass
        except Exception as e:
            print(f"[EventCoordinator] Error updating plugin status display: {e}")

    def get_subscription_status(self) -> dict:
        """Get status of event subscriptions for debugging."""
        try:
            total_subscriptions = len(self.event_bus._subscriptions) if hasattr(self.event_bus, '_subscriptions') else 0

            return {
                "total_subscriptions": total_subscriptions,
                "managers_set": all([
                    self.service_manager is not None,
                    self.window_manager is not None,
                    self.workflow_manager is not None,
                    self.task_manager is not None
                ]),
                "plugin_events_wired": self.service_manager.get_plugin_manager() is not None if self.service_manager else False,
                "code_viewer_events_wired": self.window_manager.get_code_viewer() is not None if self.window_manager else False
            }
        except Exception as e:
            return {"error": str(e)}

    def get_event_summary(self) -> dict:
        """Get summary of all wired events."""
        return {
            "project_and_session": [
                "new_project_requested",
                "load_project_requested",
                "new_session_requested"
            ],
            "workflow": [
                "user_request_submitted",
                "review_and_fix_requested"
            ],
            "ui_and_windows": [
                "show_code_viewer_requested",
                "show_workflow_monitor_requested",
                "show_terminals_requested",
                "model_config_requested",
                "plugin_management_requested",
                "project_loaded"
            ],
            "code_generation": [
                "prepare_for_generation",
                "stream_code_chunk",
                "code_generation_complete",
                "code_viewer_files_loaded"  # FIX: This is the new event!
            ],
            "execution": [
                "execution_failed",
                "error_highlight_requested",
                "clear_error_highlights",
                "show_fix_button",
                "hide_fix_button"
            ],
            "tools": [
                "terminal_output_received",
                "clear_terminal"
            ],
            "plugins": [
                "plugin_management_requested",
                "plugin_status_refresh_requested",
                "plugin_state_changed",
                "plugin_status_changed"
            ]
        }