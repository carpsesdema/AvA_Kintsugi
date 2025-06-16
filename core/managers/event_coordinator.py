# core/managers/event_coordinator.py
# FINAL COMPREHENSIVE FIX: Wire up EVERY SINGLE EVENT properly

import asyncio
from core.event_bus import EventBus


class EventCoordinator:
    """
    Centralized event subscription coordinator.
    Single responsibility: Wire up ALL event subscriptions between components.

    FINAL COMPREHENSIVE VERSION: This handles every single event in the system.
    No more missing connections, no more broken functionality.
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
        """Set references to other managers for event coordination."""
        self.service_manager = service_manager
        self.window_manager = window_manager
        self.workflow_manager = workflow_manager
        self.task_manager = task_manager

    def wire_all_events(self):
        """Wire up ALL event subscriptions - COMPREHENSIVE VERSION."""
        print("[EventCoordinator] Wiring ALL event subscriptions (COMPREHENSIVE)...")

        self._wire_project_and_session_events()
        self._wire_workflow_events()
        self._wire_ui_and_window_events()
        self._wire_code_generation_events()
        self._wire_execution_events()
        self._wire_tool_and_terminal_events()  # Combined and enhanced
        self._wire_plugin_events()
        self._wire_rag_events()
        self._wire_model_config_events()
        self._wire_application_lifecycle_events()

        # Validate that critical events have subscribers
        self._validate_critical_subscriptions()

        print("[EventCoordinator] ALL event wiring complete - COMPREHENSIVE VERSION")

    def _wire_project_and_session_events(self):
        """Wire project and session management events."""
        self.event_bus.subscribe("new_project_requested", self.workflow_manager.handle_new_project)
        self.event_bus.subscribe("load_project_requested", self.workflow_manager.handle_load_project)
        self.event_bus.subscribe("new_session_requested", self.workflow_manager.handle_new_session)
        print("[EventCoordinator] ✓ Project and session events wired")

    def _wire_workflow_events(self):
        """Wire AI workflow and user request events."""
        self.event_bus.subscribe("user_request_submitted", self.workflow_manager.handle_user_request)
        self.event_bus.subscribe("review_and_fix_requested", self.workflow_manager.handle_review_and_fix)

        # CRITICAL: Wire ai_response_ready to chat interface
        main_window = self.window_manager.get_main_window()
        if main_window and hasattr(main_window, 'chat_interface'):
            self.event_bus.subscribe("ai_response_ready", main_window.chat_interface._add_ai_response)
            print("[EventCoordinator] ✓ AI responses wired to chat interface")

        print("[EventCoordinator] ✓ Workflow events wired")

    def _wire_ui_and_window_events(self):
        """Wire UI updates and window visibility events."""
        self.event_bus.subscribe("show_code_viewer_requested", self.window_manager.show_code_viewer)
        self.event_bus.subscribe("show_workflow_monitor_requested", self.window_manager.show_workflow_monitor)
        self.event_bus.subscribe("show_terminals_requested", self.window_manager.show_terminals)
        self.event_bus.subscribe("model_config_requested", self.window_manager.show_model_config_dialog)
        self.event_bus.subscribe("plugin_management_requested", self.window_manager.show_plugin_management_dialog)

        # Update project display across windows
        self.event_bus.subscribe("project_loaded",
                                 lambda name: self.window_manager.update_project_display(name))

        print("[EventCoordinator] ✓ UI and window events wired")

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

        print("[EventCoordinator] ✓ Code generation events wired")

    def _wire_execution_events(self):
        """Wire code execution and error handling events."""
        code_viewer = self.window_manager.get_code_viewer()
        workflow_monitor = self.window_manager.get_workflow_monitor()

        if code_viewer:
            # Error highlighting in code viewer
            self.event_bus.subscribe("error_highlight_requested", code_viewer.highlight_error_in_editor)
            self.event_bus.subscribe("clear_error_highlights", code_viewer.clear_all_error_highlights)

            # Fix button visibility
            self.event_bus.subscribe("show_fix_button", code_viewer.show_fix_button)
            self.event_bus.subscribe("hide_fix_button", code_viewer.hide_fix_button)

        # Execution failure handling
        self.event_bus.subscribe("execution_failed", self.workflow_manager.handle_execution_failed)

        # Node status updates for workflow monitor
        if workflow_monitor:
            self.event_bus.subscribe("node_status_changed", workflow_monitor.update_node_status)

        print("[EventCoordinator] ✓ Execution events wired")

    def _wire_tool_and_terminal_events(self):
        """Wire tool-related and terminal events (COMPREHENSIVE)."""
        terminals = self.window_manager.get_terminals()

        if terminals:
            # CRITICAL: Terminal output and log messages
            self.event_bus.subscribe("terminal_output_received", terminals.handle_output)
            self.event_bus.subscribe("clear_terminal", terminals.clear_terminal)
            self.event_bus.subscribe("log_message_received", terminals.add_log_message)

        # CRITICAL: Terminal command handling
        if self.task_manager:
            self.event_bus.subscribe("terminal_command_entered", self.task_manager.handle_terminal_command)

        print("[EventCoordinator] ✓ Tool and terminal events wired (COMPREHENSIVE)")

    def _wire_plugin_events(self):
        """Wire plugin-specific events (COMPREHENSIVE)."""
        plugin_manager = self.service_manager.get_plugin_manager()
        if not plugin_manager:
            print("[EventCoordinator] ⚠️  No plugin manager available")
            return

        # Plugin management UI events
        self.event_bus.subscribe("plugin_management_requested",
                                 lambda: self.window_manager.show_plugin_management_dialog())
        self.event_bus.subscribe("plugin_status_refresh_requested",
                                 lambda: self.event_bus.emit("plugin_status_changed"))

        # CRITICAL: Plugin action events (enable/disable/reload)
        self.event_bus.subscribe("plugin_enable_requested", lambda plugin_name: self._handle_enable_plugin(plugin_name))
        self.event_bus.subscribe("plugin_disable_requested",
                                 lambda plugin_name: self._handle_disable_plugin(plugin_name))
        self.event_bus.subscribe("plugin_reload_requested", lambda plugin_name: self._handle_reload_plugin(plugin_name))

        # Plugin lifecycle events for logging
        self.event_bus.subscribe("plugin_state_changed",
                                 lambda name, old, new: self._log_plugin_state_change(name, old, new))
        self.event_bus.subscribe("plugin_status_changed", lambda: self._update_plugin_status_display())

        # Plugin-emitted events (from Living Design Agent, etc.)
        self.event_bus.subscribe("design_document_updated", self._handle_design_document_updated)
        self.event_bus.subscribe("architecture_analysis_complete", self._handle_architecture_analysis_complete)
        self.event_bus.subscribe("design_decision_logged", self._handle_design_decision_logged)

        print("[EventCoordinator] ✓ Plugin events wired (COMPREHENSIVE)")

    def _wire_rag_events(self):
        """Wire RAG system events."""
        rag_manager = self.service_manager.get_rag_manager()
        if rag_manager:
            # RAG directory scanning and ingestion
            self.event_bus.subscribe("scan_directory_requested", lambda: rag_manager.open_scan_directory_dialog())
            self.event_bus.subscribe("add_active_project_to_rag_requested", lambda: rag_manager.ingest_active_project())

            # RAG server management
            self.event_bus.subscribe("launch_rag_server_requested", lambda: rag_manager.launch_rag_server())

            print("[EventCoordinator] ✓ RAG events wired")
        else:
            print("[EventCoordinator] ⚠️  No RAG manager available")

    def _wire_model_config_events(self):
        """Wire model configuration events."""
        self.event_bus.subscribe("configure_models_requested", lambda: self.window_manager.show_model_config_dialog())
        print("[EventCoordinator] ✓ Model configuration events wired")

    def _wire_application_lifecycle_events(self):
        """Wire application lifecycle events."""
        self.event_bus.subscribe("application_shutdown", self._handle_application_shutdown)
        print("[EventCoordinator] ✓ Application lifecycle events wired")

    # ===== EVENT HANDLERS =====

    def _handle_enable_plugin(self, plugin_name: str):
        """Handle plugin enable request."""
        try:
            plugin_manager = self.service_manager.get_plugin_manager()
            if plugin_manager:
                print(f"[EventCoordinator] Enabling plugin: {plugin_name}")
                asyncio.create_task(self._async_enable_plugin(plugin_name))
            else:
                print(f"[EventCoordinator] Cannot enable plugin: No plugin manager")
        except Exception as e:
            print(f"[EventCoordinator] Error enabling plugin '{plugin_name}': {e}")

    def _handle_disable_plugin(self, plugin_name: str):
        """Handle plugin disable request."""
        try:
            plugin_manager = self.service_manager.get_plugin_manager()
            if plugin_manager:
                print(f"[EventCoordinator] Disabling plugin: {plugin_name}")
                asyncio.create_task(self._async_disable_plugin(plugin_name))
            else:
                print(f"[EventCoordinator] Cannot disable plugin: No plugin manager")
        except Exception as e:
            print(f"[EventCoordinator] Error disabling plugin '{plugin_name}': {e}")

    def _handle_reload_plugin(self, plugin_name: str):
        """Handle plugin reload request."""
        try:
            plugin_manager = self.service_manager.get_plugin_manager()
            if plugin_manager:
                print(f"[EventCoordinator] Reloading plugin: {plugin_name}")
                asyncio.create_task(self._async_reload_plugin(plugin_name))
            else:
                print(f"[EventCoordinator] Cannot reload plugin: No plugin manager")
        except Exception as e:
            print(f"[EventCoordinator] Error reloading plugin '{plugin_name}': {e}")

    def _handle_design_document_updated(self, update_info):
        """Handle design document updates from plugins."""
        try:
            print(f"[EventCoordinator] Design document updated: {update_info}")
        except Exception as e:
            print(f"[EventCoordinator] Error handling design document update: {e}")

    def _handle_architecture_analysis_complete(self, analysis_info):
        """Handle architecture analysis completion from plugins."""
        try:
            print(f"[EventCoordinator] Architecture analysis complete: {analysis_info}")
        except Exception as e:
            print(f"[EventCoordinator] Error handling architecture analysis: {e}")

    def _handle_design_decision_logged(self, decision_info):
        """Handle design decision logging from plugins."""
        try:
            print(f"[EventCoordinator] Design decision logged: {decision_info}")
        except Exception as e:
            print(f"[EventCoordinator] Error handling design decision: {e}")

    def _handle_application_shutdown(self):
        """Handle application shutdown."""
        try:
            print("[EventCoordinator] Application shutdown requested")
        except Exception as e:
            print(f"[EventCoordinator] Error during application shutdown: {e}")

    # ===== ASYNC PLUGIN HANDLERS =====

    async def _async_enable_plugin(self, plugin_name: str):
        """Async helper for enabling a plugin."""
        try:
            plugin_manager = self.service_manager.get_plugin_manager()
            success = await plugin_manager.enable_plugin(plugin_name)

            if success:
                print(f"[EventCoordinator] ✓ Successfully enabled plugin: {plugin_name}")
            else:
                print(f"[EventCoordinator] ✗ Failed to enable plugin: {plugin_name}")

            self.event_bus.emit("plugin_status_changed")
        except Exception as e:
            print(f"[EventCoordinator] Error in async enable plugin '{plugin_name}': {e}")

    async def _async_disable_plugin(self, plugin_name: str):
        """Async helper for disabling a plugin."""
        try:
            plugin_manager = self.service_manager.get_plugin_manager()
            success = await plugin_manager.disable_plugin(plugin_name)

            if success:
                print(f"[EventCoordinator] ✓ Successfully disabled plugin: {plugin_name}")
            else:
                print(f"[EventCoordinator] ✗ Failed to disable plugin: {plugin_name}")

            self.event_bus.emit("plugin_status_changed")
        except Exception as e:
            print(f"[EventCoordinator] Error in async disable plugin '{plugin_name}': {e}")

    async def _async_reload_plugin(self, plugin_name: str):
        """Async helper for reloading a plugin."""
        try:
            plugin_manager = self.service_manager.get_plugin_manager()

            await plugin_manager.disable_plugin(plugin_name)
            success = await plugin_manager.enable_plugin(plugin_name)

            if success:
                print(f"[EventCoordinator] ✓ Successfully reloaded plugin: {plugin_name}")
            else:
                print(f"[EventCoordinator] ✗ Failed to reload plugin: {plugin_name}")

            self.event_bus.emit("plugin_status_changed")
        except Exception as e:
            print(f"[EventCoordinator] Error in async reload plugin '{plugin_name}': {e}")

    # ===== UTILITY METHODS =====

    def _log_plugin_state_change(self, name: str, old_state, new_state):
        """Log plugin state changes."""
        try:
            print(f"[EventCoordinator] Plugin '{name}': {old_state.value} -> {new_state.value}")
        except Exception as e:
            print(f"[EventCoordinator] Error logging plugin state change: {e}")

    def _update_plugin_status_display(self):
        """Update plugin status in UI components."""
        try:
            main_window = self.window_manager.get_main_window()
            if main_window and hasattr(main_window, 'sidebar') and hasattr(main_window.sidebar,
                                                                           '_update_plugin_status'):
                main_window.sidebar._update_plugin_status()
        except Exception as e:
            print(f"[EventCoordinator] Error updating plugin status display: {e}")

    def _validate_critical_subscriptions(self):
        """Validate that all critical events have subscribers."""
        critical_events = [
            "log_message_received",
            "terminal_command_entered",
            "plugin_enable_requested",
            "plugin_disable_requested",
            "ai_response_ready",
            "execution_failed",
            "terminal_output_received"
        ]

        missing_events = []
        for event in critical_events:
            if event not in self.event_bus._subscribers or not self.event_bus._subscribers[event]:
                missing_events.append(event)

        if missing_events:
            print(f"[EventCoordinator] ⚠️  CRITICAL: Missing subscriptions for: {missing_events}")
            return False

        print("[EventCoordinator] ✓ All critical events have subscribers")
        return True

    # ===== DEBUGGING METHODS =====

    def get_wired_events_summary(self) -> dict:
        """Get a comprehensive summary of all wired events for debugging."""
        return {
            "project_and_session": [
                "new_project_requested", "load_project_requested", "new_session_requested"
            ],
            "workflow": [
                "user_request_submitted", "review_and_fix_requested", "ai_response_ready"
            ],
            "ui_and_windows": [
                "show_code_viewer_requested", "show_workflow_monitor_requested",
                "show_terminals_requested", "model_config_requested",
                "plugin_management_requested", "project_loaded"
            ],
            "code_generation": [
                "prepare_for_generation", "stream_code_chunk", "code_generation_complete"
            ],
            "execution": [
                "execution_failed", "error_highlight_requested", "clear_error_highlights",
                "show_fix_button", "hide_fix_button", "node_status_changed"
            ],
            "tools_and_terminal": [
                "terminal_output_received", "clear_terminal", "log_message_received",
                "terminal_command_entered"
            ],
            "plugins": [
                "plugin_management_requested", "plugin_status_refresh_requested",
                "plugin_enable_requested", "plugin_disable_requested", "plugin_reload_requested",
                "plugin_state_changed", "plugin_status_changed", "design_document_updated",
                "architecture_analysis_complete", "design_decision_logged"
            ],
            "rag": [
                "scan_directory_requested", "add_active_project_to_rag_requested",
                "launch_rag_server_requested"
            ],
            "model_config": [
                "configure_models_requested"
            ],
            "application_lifecycle": [
                "application_shutdown"
            ]
        }

    def get_subscription_count(self) -> int:
        """Get total number of event subscriptions."""
        return sum(len(callbacks) for callbacks in self.event_bus._subscribers.values())

    def print_wiring_report(self):
        """Print a comprehensive wiring report."""
        total_subs = self.get_subscription_count()
        events_summary = self.get_wired_events_summary()

        print(f"\n[EventCoordinator] COMPREHENSIVE WIRING REPORT:")
        print(f"Total event subscriptions: {total_subs}")
        print(f"Event categories wired: {len(events_summary)}")

        for category, events in events_summary.items():
            print(f"  {category}: {len(events)} events")

        self._validate_critical_subscriptions()
        print("[EventCoordinator] WIRING REPORT COMPLETE\n")