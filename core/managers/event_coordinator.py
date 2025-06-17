# kintsugi_ava/core/managers/event_coordinator.py
# UPDATED: Re-wired the main user chat event to the new central router.

import asyncio
from core.event_bus import EventBus


class EventCoordinator:
    """
    Coordinates events between different components of the application.
    Single responsibility: Event routing and component integration.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
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
        if not all([self.workflow_manager, self.window_manager, self.service_manager]):
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
            self.event_bus.subscribe("plugin_enable_requested",
                                     lambda name: asyncio.create_task(plugin_manager.enable_plugin(name)))
            self.event_bus.subscribe("plugin_disable_requested",
                                     lambda name: asyncio.create_task(plugin_manager.disable_plugin(name)))
            self.event_bus.subscribe("plugin_reload_requested",
                                     lambda name: asyncio.create_task(plugin_manager.reload_plugin(name)))

        # Session & Tools
        self.event_bus.subscribe("new_session_requested", self.workflow_manager.handle_new_session)
        self.event_bus.subscribe("show_log_viewer_requested", self.window_manager.show_log_viewer)
        self.event_bus.subscribe("show_code_viewer_requested", self.window_manager.show_code_viewer)
        print("[EventCoordinator] ✓ UI events wired")

    def _wire_ai_workflow_events(self):
        """
        UPDATED: This now routes all chat input to the new central handler
        in WorkflowManager, which will decide what to do based on the app state.
        """
        if self.workflow_manager:
            self.event_bus.subscribe("user_request_submitted", self.workflow_manager.handle_user_request)
            self.event_bus.subscribe("review_and_fix_requested", self.workflow_manager.handle_review_and_fix)

        code_viewer = self.window_manager.get_code_viewer()
        if code_viewer:
            self.event_bus.subscribe("prepare_for_generation", code_viewer.prepare_for_generation)
            self.event_bus.subscribe("stream_code_chunk", code_viewer.stream_code_chunk)
            self.event_bus.subscribe("code_generation_complete", code_viewer.display_code)

        print("[EventCoordinator] ✓ AI workflow events wired")

    def _wire_execution_events(self):
        code_viewer = self.window_manager.get_code_viewer()

        if code_viewer:
            self.event_bus.subscribe("error_highlight_requested", code_viewer.highlight_error_in_editor)
            self.event_bus.subscribe("clear_error_highlights", code_viewer.clear_all_error_highlights)

        if self.workflow_manager:
            self.event_bus.subscribe("execution_failed", self.workflow_manager.handle_execution_failed)
        print("[EventCoordinator] ✓ Execution events wired")

    def _wire_terminal_events(self):
        """Wire integrated terminal events."""
        if not (self.task_manager and self.service_manager): return

        self.event_bus.subscribe("terminal_command_entered", self._handle_terminal_command)
        print("[EventCoordinator] ✓ Terminal events wired")

    def _handle_terminal_command(self, command: str, session_id: int):
        """Handle a command from any terminal session."""
        terminal_service = self.service_manager.get_terminal_service()
        if not terminal_service: return

        command_coroutine = terminal_service.execute_command(command, session_id)
        self.task_manager.start_terminal_command_task(command_coroutine, session_id)

    def _wire_plugin_events(self):
        plugin_manager = self.service_manager.get_plugin_manager()
        if plugin_manager:
            self.event_bus.subscribe("plugin_loaded", lambda name: print(f"[EventCoordinator] Plugin loaded: {name}"))
            self.event_bus.subscribe("plugin_unloaded",
                                     lambda name: print(f"[EventCoordinator] Plugin unloaded: {name}"))
            self.event_bus.subscribe("plugin_error",
                                     lambda name, err: self.event_bus.emit("log_message_received", "Plugin", "error",
                                                                           f"Error in {name}: {err}"))
        print("[EventCoordinator] ✓ Plugin events wired")