# kintsugi_ava/core/managers/event_coordinator.py
# Fixed event coordinator with correct terminal event handling

from core.event_bus import EventBus


class EventCoordinator:
    """
    Coordinates events between different components of the application.
    Single responsibility: Event routing and component integration.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        # Manager references (set by Application)
        self.service_manager = None
        self.window_manager = None
        self.task_manager = None
        self.workflow_manager = None

        print("[EventCoordinator] Initialized")

    def set_managers(self, service_manager, window_manager, task_manager, workflow_manager):
        """Set references to other managers."""
        self.service_manager = service_manager
        self.window_manager = window_manager
        self.task_manager = task_manager
        self.workflow_manager = workflow_manager

    def wire_all_events(self):
        """Wire all events between components."""
        print("[EventCoordinator] Wiring all events...")

        self._wire_ai_workflow_events()
        self._wire_execution_events()
        self._wire_terminal_events()
        self._wire_plugin_events()

        print("[EventCoordinator] ✓ All events wired successfully")

    def _wire_ai_workflow_events(self):
        """Wire AI workflow related events."""
        if self.workflow_manager:
            self.event_bus.subscribe("user_input_received", self.workflow_manager.handle_user_input)
            self.event_bus.subscribe("review_and_fix_requested", self.workflow_manager.handle_review_and_fix)

        print("[EventCoordinator] ✓ AI workflow events wired")

    def _wire_execution_events(self):
        """Wire code execution related events."""
        code_viewer = self.window_manager.get_code_viewer() if self.window_manager else None
        workflow_monitor = self.window_manager.get_workflow_monitor() if self.window_manager else None

        if code_viewer:
            # Error highlighting in code viewer
            self.event_bus.subscribe("error_highlight_requested", code_viewer.highlight_error_in_editor)
            self.event_bus.subscribe("clear_error_highlights", code_viewer.clear_all_error_highlights)

            # Fix button visibility
            self.event_bus.subscribe("show_fix_button", code_viewer.show_fix_button)
            self.event_bus.subscribe("hide_fix_button", code_viewer.hide_fix_button)

        # Execution failure handling
        if self.workflow_manager:
            self.event_bus.subscribe("execution_failed", self.workflow_manager.handle_execution_failed)

        # Node status updates for workflow monitor
        if workflow_monitor:
            self.event_bus.subscribe("node_status_changed", workflow_monitor.scene.update_node_status)

        print("[EventCoordinator] ✓ Execution events wired")

    def _wire_terminal_events(self):
        """Wire terminal events with session support."""
        terminals = self.window_manager.get_terminals() if self.window_manager else None
        terminal_service = self.service_manager.get_terminal_service() if self.service_manager else None

        if terminals:
            # Terminal output routing with session support
            self.event_bus.subscribe("terminal_output_received", self._route_terminal_output)
            self.event_bus.subscribe("terminal_error_received", self._route_terminal_error)
            self.event_bus.subscribe("terminal_success_received", self._route_terminal_success)

            # Terminal control events
            self.event_bus.subscribe("clear_terminal", self._route_clear_terminal)
            self.event_bus.subscribe("terminal_command_finished", self._route_command_finished)

            # Command handling from terminals window
            terminals.terminal_command_entered.connect(self._handle_terminal_command)

        # Terminal command handling
        if self.task_manager and terminal_service:
            # Route terminal commands to the service
            self.event_bus.subscribe("terminal_command_entered", self._handle_legacy_terminal_command)

        print("[EventCoordinator] ✓ Terminal events wired")

    def _wire_plugin_events(self):
        """Wire plugin-specific events."""
        plugin_manager = self.service_manager.get_plugin_manager() if self.service_manager else None

        if plugin_manager:
            # Plugin lifecycle events
            self.event_bus.subscribe("plugin_loaded", self._handle_plugin_loaded)
            self.event_bus.subscribe("plugin_unloaded", self._handle_plugin_unloaded)
            self.event_bus.subscribe("plugin_error", self._handle_plugin_error)

        print("[EventCoordinator] ✓ Plugin events wired")

    def _route_terminal_output(self, text: str, session_id: int = None):
        """Route terminal output to the appropriate terminal session."""
        if self.window_manager:
            self.window_manager.handle_terminal_output(text, session_id)

    def _route_terminal_error(self, text: str, session_id: int = None):
        """Route terminal error output to the appropriate terminal session."""
        if self.window_manager:
            self.window_manager.handle_terminal_error(text, session_id)

    def _route_terminal_success(self, text: str, session_id: int = None):
        """Route terminal success output to the appropriate terminal session."""
        if self.window_manager:
            self.window_manager.handle_terminal_success(text, session_id)

    def _route_clear_terminal(self, session_id: int = None):
        """Route clear terminal command to the appropriate session."""
        if self.window_manager:
            self.window_manager.clear_terminal(session_id)

    def _route_command_finished(self, session_id: int = None):
        """Route command finished signal to the appropriate session."""
        if self.window_manager:
            self.window_manager.mark_terminal_command_finished(session_id)

    def _handle_terminal_command(self, command: str, session_id: int):
        """Handle terminal command from the terminals window."""
        if not self.task_manager or not self.service_manager:
            print("[EventCoordinator] Cannot handle terminal command: Managers not available")
            return

        terminal_service = self.service_manager.get_terminal_service()
        if not terminal_service:
            print("[EventCoordinator] Cannot handle terminal command: Terminal service not available")
            return

        # Create a coroutine for the terminal service
        command_coroutine = terminal_service.execute_command(command, session_id)

        # Use task manager to handle the execution
        success = self.task_manager.start_terminal_command_task(command_coroutine, session_id)
        if not success:
            # Emit error to the specific session
            self.event_bus.emit("terminal_error_received",
                                "Another command is already running in this session.\n",
                                session_id)

    def _handle_legacy_terminal_command(self, command: str):
        """Handle legacy terminal commands (without session ID) for backward compatibility."""
        # Route to the original handle_terminal_command method for backward compatibility
        if self.task_manager:
            self.task_manager.handle_terminal_command(command)

    def _handle_plugin_loaded(self, plugin_name: str):
        """Handle plugin loaded event."""
        print(f"[EventCoordinator] Plugin loaded: {plugin_name}")

    def _handle_plugin_unloaded(self, plugin_name: str):
        """Handle plugin unloaded event."""
        print(f"[EventCoordinator] Plugin unloaded: {plugin_name}")

    def _handle_plugin_error(self, plugin_name: str, error: str):
        """Handle plugin error event."""
        print(f"[EventCoordinator] Plugin error in {plugin_name}: {error}")
        self.event_bus.emit("log_message_received", "Plugin", "error", f"Error in {plugin_name}: {error}")

    def get_wiring_status(self) -> dict:
        """Get the status of event wiring."""
        return {
            "ai_workflow_events": self.workflow_manager is not None,
            "execution_events": self.window_manager is not None,
            "terminal_events": (
                    self.window_manager is not None and
                    self.service_manager is not None and
                    self.task_manager is not None
            ),
            "plugin_events": (
                    self.service_manager is not None and
                    self.service_manager.get_plugin_manager() is not None
            ),
        }