# kintsugi_ava/core/managers/window_manager.py
# Fixed window manager with proper terminal integration

from gui.main_window import MainWindow
from gui.code_viewer import CodeViewerWindow
from gui.workflow_monitor_window import WorkflowMonitorWindow
from gui.model_config_dialog import ModelConfigurationDialog
from gui.plugin_management_dialog import PluginManagementDialog
from gui.terminals import TerminalsWindow

from core.event_bus import EventBus
from core.llm_client import LLMClient


class WindowManager:
    """
    Creates and manages all GUI windows.
    Single responsibility: Window lifecycle and access management.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        # Main windows
        self.main_window: MainWindow = None
        self.code_viewer: CodeViewerWindow = None
        self.workflow_monitor: WorkflowMonitorWindow = None
        self.terminals: TerminalsWindow = None

        # Dialogs
        self.model_config_dialog: ModelConfigurationDialog = None
        self.plugin_management_dialog: PluginManagementDialog = None

        print("[WindowManager] Initialized")

    def initialize_windows(self, llm_client: LLMClient, service_manager, project_manager=None):
        """Initialize all GUI windows."""
        print("[WindowManager] Initializing windows...")

        # Get project manager from service manager if not provided
        if project_manager is None:
            project_manager = service_manager.get_project_manager()

        # Create main windows
        self.main_window = MainWindow(self.event_bus)
        self.code_viewer = CodeViewerWindow(self.event_bus)
        self.workflow_monitor = WorkflowMonitorWindow(self.event_bus)

        # Create terminals window with project manager
        self.terminals = TerminalsWindow(self.event_bus, project_manager)

        # Create dialogs
        self.model_config_dialog = ModelConfigurationDialog(llm_client, self.main_window)

        # Plugin management dialog
        plugin_manager = service_manager.get_plugin_manager()
        self.plugin_management_dialog = PluginManagementDialog(plugin_manager, self.event_bus, self.main_window)

        print("[WindowManager] Windows initialized")

    def get_main_window(self) -> MainWindow:
        """Get the main window instance."""
        return self.main_window

    def get_code_viewer(self) -> CodeViewerWindow:
        """Get the code viewer window instance."""
        return self.code_viewer

    def get_workflow_monitor(self) -> WorkflowMonitorWindow:
        """Get the workflow monitor window instance."""
        return self.workflow_monitor

    def get_terminals(self) -> TerminalsWindow:
        """Get the terminals window instance."""
        return self.terminals

    def get_model_config_dialog(self) -> ModelConfigurationDialog:
        """Get the model configuration dialog instance."""
        return self.model_config_dialog

    def get_plugin_management_dialog(self) -> PluginManagementDialog:
        """Get the plugin management dialog instance."""
        return self.plugin_management_dialog

    def show_main_window(self):
        """Show the main application window."""
        if self.main_window:
            self.main_window.show()

    def show_code_viewer(self):
        """Show the code viewer window."""
        if self.code_viewer:
            self.code_viewer.show_window()

    def show_workflow_monitor(self):
        """Show the workflow monitor window."""
        if self.workflow_monitor:
            self.workflow_monitor.show()

    def show_terminals(self):
        """Show the terminals window."""
        if self.terminals:
            self.terminals.show()

    def show_model_config_dialog(self):
        """Show the model configuration dialog."""
        if self.model_config_dialog:
            self.model_config_dialog.exec()

    def show_plugin_management_dialog(self):
        """Show the plugin management dialog."""
        if self.plugin_management_dialog:
            self.plugin_management_dialog.exec()

    def update_project_display(self, project_name: str):
        """Update project name display across windows."""
        if self.main_window and hasattr(self.main_window, 'sidebar'):
            self.main_window.sidebar.update_project_display(project_name)

    def prepare_code_viewer_for_new_project(self):
        """Prepare code viewer for new project session."""
        if self.code_viewer:
            self.code_viewer.prepare_for_new_project_session()

    def load_project_in_code_viewer(self, project_path: str):
        """Load project in code viewer."""
        if self.code_viewer:
            self.code_viewer.load_project(project_path)

    def update_terminals_project_manager(self, project_manager):
        """Update the project manager in the terminals window."""
        if self.terminals:
            self.terminals.set_project_manager(project_manager)

    def handle_terminal_output(self, text: str, session_id: int = None):
        """Route terminal output to the terminals window."""
        if self.terminals:
            self.terminals.handle_terminal_output(text, session_id)

    def handle_terminal_error(self, text: str, session_id: int = None):
        """Route terminal error output to the terminals window."""
        if self.terminals:
            self.terminals.handle_terminal_error(text, session_id)

    def handle_terminal_success(self, text: str, session_id: int = None):
        """Route terminal success output to the terminals window."""
        if self.terminals:
            self.terminals.handle_terminal_success(text, session_id)

    def clear_terminal(self, session_id: int = None):
        """Clear terminal output."""
        if self.terminals:
            if session_id is not None:
                # Clear specific session
                if session_id in self.terminals.terminal_sessions:
                    self.terminals.terminal_sessions[session_id]["widget"].clear_output()
            else:
                # Clear current terminal
                self.terminals.clear_current_terminal()

    def mark_terminal_command_finished(self, session_id: int = None):
        """Mark terminal command as finished."""
        if self.terminals:
            self.terminals.mark_command_finished(session_id)

    def get_terminal_session_info(self) -> dict:
        """Get information about terminal sessions."""
        if self.terminals:
            return {
                "active_session": self.terminals.get_active_session_info(),
                "all_sessions": self.terminals.get_all_session_info()
            }
        return {"active_session": {}, "all_sessions": []}

    def is_fully_initialized(self) -> bool:
        """Check if all windows are initialized."""
        return all([
            self.main_window is not None,
            self.code_viewer is not None,
            self.workflow_monitor is not None,
            self.terminals is not None,
            self.model_config_dialog is not None,
            self.plugin_management_dialog is not None
        ])

    def is_fully_initialized(self) -> bool:
        """Check if all windows are initialized."""
        return all([
            self.main_window is not None,
            self.code_viewer is not None,
            self.workflow_monitor is not None,
            self.terminals is not None,
            self.model_config_dialog is not None,
            self.plugin_management_dialog is not None
        ])