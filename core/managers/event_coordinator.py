# kintsugi_ava/core/managers/event_coordinator.py
# Centralized event subscription management

from core.event_bus import EventBus


class EventCoordinator:
    """
    Centralized event subscription coordinator.
    Single responsibility: Wire up all event subscriptions between components.
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

    def get_subscription_status(self) -> dict:
        """Get status of event subscriptions for debugging."""
        return {
            "managers_set": all([
                self.service_manager,
                self.window_manager,
                self.workflow_manager,
                self.task_manager
            ]),
            "event_bus_available": self.event_bus is not None,
            "subscription_count": len(self.event_bus._subscribers) if hasattr(self.event_bus, '_subscribers') else 0
        }