# kintsugi_ava/core/managers/window_manager.py
# Creates and manages all GUI windows

from gui.main_window import MainWindow
from gui.code_viewer import CodeViewerWindow
from gui.workflow_monitor_window import WorkflowMonitorWindow
from gui.model_config_dialog import ModelConfigurationDialog
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

        print("[WindowManager] Initialized")

    def initialize_windows(self, llm_client: LLMClient):
        """
        Initialize all GUI windows.

        Args:
            llm_client: LLM client needed for model configuration dialog
        """
        print("[WindowManager] Initializing windows...")

        # Create main windows
        self.main_window = MainWindow(self.event_bus)
        self.code_viewer = CodeViewerWindow(self.event_bus)
        self.workflow_monitor = WorkflowMonitorWindow(self.event_bus)
        self.terminals = TerminalsWindow(self.event_bus)

        # Create dialogs (parent will be set when shown)
        self.model_config_dialog = ModelConfigurationDialog(llm_client, self.main_window)

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

    def update_project_display(self, project_name: str):
        """
        Update project name display across windows.

        Args:
            project_name: Name of the active project
        """
        if self.main_window and hasattr(self.main_window, 'sidebar'):
            self.main_window.sidebar.update_project_display(project_name)

    def prepare_code_viewer_for_new_project(self):
        """Prepare code viewer for new project session."""
        if self.code_viewer:
            self.code_viewer.prepare_for_new_project_session()

    def load_project_in_code_viewer(self, project_path: str):
        """
        Load project in code viewer.

        Args:
            project_path: Path to the project to load
        """
        if self.code_viewer:
            self.code_viewer.load_project(project_path)

    def is_fully_initialized(self) -> bool:
        """Check if all windows are initialized."""
        return all([
            self.main_window,
            self.code_viewer,
            self.workflow_monitor,
            self.terminals,
            self.model_config_dialog
        ])

    def get_initialization_status(self) -> dict:
        """Get detailed initialization status for debugging."""
        return {
            "main_window": self.main_window is not None,
            "code_viewer": self.code_viewer is not None,
            "workflow_monitor": self.workflow_monitor is not None,
            "terminals": self.terminals is not None,
            "model_config_dialog": self.model_config_dialog is not None,
            "fully_initialized": self.is_fully_initialized()
        }