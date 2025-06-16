# kintsugi_ava/core/managers/event_coordinator.py
# Fixed event coordinator with correct terminal event handling

import asyncio
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

        self._wire_ui_events()
        self._wire_ai_workflow_events()
        self._wire_execution_events()
        self._wire_terminal_events()
        self._wire_plugin_events()

        print("[EventCoordinator] ✓ All events wired successfully")

    def _wire_ui_events(self):
        """Wire main UI events from the sidebar and other components."""
        if not (self.workflow_manager and self.window_manager and self.service_manager):
            print("[EventCoordinator] Warning: Cannot wire UI events, managers not fully set.")
            return

        # Project Management
        self.event_bus.subscribe("new_project_requested", self.workflow_manager.handle_new_project)
        self.event_bus.subscribe("load_project_requested", self.workflow_manager.handle_load_project)

        # Model Configuration
        self.event_bus.subscribe("configure_models_requested", self.window_manager.show_model_config_dialog)

        # RAG Management
        rag_manager = self.service_manager.get_rag_manager()
        if rag_manager:
            self.event_bus.subscribe("launch_rag_server_requested", rag_manager.launch_rag_server)
            self.event_bus.subscribe("scan_directory_requested", rag_manager.open_scan_directory_dialog)
            self.event_bus.subscribe("add_active_project_to_rag_requested", rag_manager.ingest_active_project)

        # Plugin Management
        self.event_bus.subscribe("plugin_management_requested", self.window_manager.show_plugin_management_dialog)
        plugin_manager = self.service_manager.get_plugin_manager()
        if plugin_manager:
            self.event_bus.subscribe(
                "plugin_enable_requested",
                lambda name: asyncio.create_task(plugin_manager.enable_plugin(name))
            )
            self.event_bus.subscribe(
                "plugin_disable_requested",
                lambda name: asyncio.create_task(plugin_manager.disable_plugin(name))
            )
            self.event_bus.subscribe(
                "plugin_reload_requested",
                lambda name: asyncio.create_task(plugin_manager.reload_plugin(name))
            )

        # Session & Tools
        self.event_bus.subscribe("new_session_requested", self.workflow_manager.handle_new_session)

        # Window Management
        self.event_bus.subscribe("show_terminals_requested", self.window_manager.show_terminals)
        self.event_bus.subscribe("show_workflow_monitor_requested", self.window_manager.show_workflow_monitor)
        self.event_bus.subscribe("show_code_viewer_requested", self.window_manager.show_code_viewer)

        print("[EventCoordinator] ✓ UI events wired")

    def _wire_ai_workflow_events(self):
        """Wire AI workflow related events."""
        if self.workflow_manager:
            self.event_bus.subscribe("user_request_submitted", self.workflow_manager.handle_user_request)
            self.event_bus.subscribe("review_and_fix_requested", self.workflow_manager.handle_review_and_fix)

        print("[EventCoordinator] ✓ AI workflow events wired")

    def _wire_execution_events(self):
        """Wire code execution related events."""
        code_viewer = self.window_manager.get_code_viewer() if self.window_manager else None
        workflow_monitor = self.window_manager.get_workflow_monitor() if self.window_manager else None

        if code_viewer:
            self.event_bus.subscribe("error_highlight_requested", code_viewer.highlight_error_in_editor)
            self.event_bus.subscribe("clear_error_highlights", code_viewer.clear_all_error_highlights)
            self.event_bus.subscribe("show_fix_button", code_viewer.show_fix_button)
            self.event_bus.subscribe("hide_fix_button", code_viewer.hide_fix_button)

        if self.workflow_manager:
            self.event_bus.subscribe("execution_failed", self.workflow_manager.handle_execution_failed)

        if workflow_monitor:
            self.event_bus.subscribe("node_status_changed", workflow_monitor.scene.update_node_status)

        print("[EventCoordinator] ✓ Execution events wired")


    def _wire_terminal_events(self):
        """Wire terminal events with session support."""
        terminals = self.window_manager.get_terminals() if self.window_manager else None
        terminal_service = self.service_manager.get_terminal_service() if self.service_manager else None

        if terminals:
            self.event_bus.subscribe("terminal_output_received", self._route_terminal_output)
            self.event_bus.subscribe("terminal_error_received", self._route_terminal_error)
            self.event_bus.subscribe("terminal_success_received", self._route_terminal_success)
            self.event_bus.subscribe("clear_terminal", self._route_clear_terminal)
            self.event_bus.subscribe("terminal_command_finished", self._route_command_finished)
            terminals.terminal_command_entered.connect(self._handle_terminal_command)

        if self.task_manager and terminal_service:
            self.event_bus.subscribe("terminal_command_entered", self._handle_legacy_terminal_command)

        print("[EventCoordinator] ✓ Terminal events wired")

    def _wire_plugin_events(self):
        """Wire plugin-specific events."""
        plugin_manager = self.service_manager.get_plugin_manager() if self.service_manager else None

        if plugin_manager:
            self.event_bus.subscribe("plugin_loaded", self._handle_plugin_loaded)
            self.event_bus.subscribe("plugin_unloaded", self._handle_plugin_unloaded)
            self.event_bus.subscribe("plugin_error", self._handle_plugin_error)

        print("[EventCoordinator] ✓ Plugin events wired")

    def _route_terminal_output(self, text: str, session_id: int = None):
        if self.window_manager:
            self.window_manager.handle_terminal_output(text, session_id)

    def _route_terminal_error(self, text: str, session_id: int = None):
        if self.window_manager:
            self.window_manager.handle_terminal_error(text, session_id)

    def _route_terminal_success(self, text: str, session_id: int = None):
        if self.window_manager:
            self.window_manager.handle_terminal_success(text, session_id)

    def _route_clear_terminal(self, session_id: int = None):
        if self.window_manager:
            self.window_manager.clear_terminal(session_id)

    def _route_command_finished(self, session_id: int = None):
        if self.window_manager:
            self.window_manager.mark_terminal_command_finished(session_id)

    def _handle_terminal_command(self, command: str, session_id: int):
        if not self.task_manager or not self.service_manager:
            print("[EventCoordinator] Cannot handle terminal command: Managers not available")
            return

        terminal_service = self.service_manager.get_terminal_service()
        if not terminal_service:
            print("[EventCoordinator] Cannot handle terminal command: Terminal service not available")
            return

        command_coroutine = terminal_service.execute_command(command, session_id)
        success = self.task_manager.start_terminal_command_task(command_coroutine, session_id)
        if not success:
            self.event_bus.emit("terminal_error_received",
                                "Another command is already running in this session.\n",
                                session_id)

    def _handle_legacy_terminal_command(self, command: str):
        if self.task_manager:
            self.task_manager.handle_terminal_command(command)

    def _handle_plugin_loaded(self, plugin_name: str):
        print(f"[EventCoordinator] Plugin loaded: {plugin_name}")

    def _handle_plugin_unloaded(self, plugin_name: str):
        print(f"[EventCoordinator] Plugin unloaded: {plugin_name}")

    def _handle_plugin_error(self, plugin_name: str, error: str):
        print(f"[EventCoordinator] Plugin error in {plugin_name}: {error}")
        self.event_bus.emit("log_message_received", "Plugin", "error", f"Error in {plugin_name}: {error}")

    def get_wiring_status(self) -> dict:
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