# kintsugi_ava/core/managers/window_manager.py
# UPDATED: Standardized imports to fix class comparison bug.

from ava.gui.main_window import MainWindow
from ava.gui.code_viewer import CodeViewerWindow
from ava.gui.model_config_dialog import ModelConfigurationDialog
from ava.gui.plugin_management_dialog import PluginManagementDialog
from ava.gui.log_viewer import LogViewerWindow

from ava.core.event_bus import EventBus
from ava.core.llm_client import LLMClient
from ava.core.project_manager import ProjectManager


class WindowManager:
    """
    Creates and manages all GUI windows.
    Single responsibility: Window lifecycle and access management.
    """

    def __init__(self, event_bus: EventBus, project_manager: ProjectManager):
        self.event_bus = event_bus
        self.project_manager = project_manager

        # Main windows
        self.main_window: MainWindow = None
        self.code_viewer: CodeViewerWindow = None
        self.log_viewer: LogViewerWindow = None

        # Dialogs
        self.model_config_dialog: ModelConfigurationDialog = None
        self.plugin_management_dialog: PluginManagementDialog = None

        print("[WindowManager] Initialized")

    def initialize_windows(self, llm_client: LLMClient, service_manager):
        """Initialize all GUI windows."""
        print("[WindowManager] Initializing windows...")

        # Create main windows
        self.main_window = MainWindow(self.event_bus)
        self.code_viewer = CodeViewerWindow(self.event_bus, self.project_manager)
        self.log_viewer = LogViewerWindow(self.event_bus)

        # Create dialogs
        self.model_config_dialog = ModelConfigurationDialog(llm_client, self.main_window)
        plugin_manager = service_manager.get_plugin_manager()
        self.plugin_management_dialog = PluginManagementDialog(plugin_manager, self.event_bus, self.main_window)

        print("[WindowManager] Windows initialized")

    # --- Window Getters ---
    def get_main_window(self) -> MainWindow:
        return self.main_window

    def get_code_viewer(self) -> CodeViewerWindow:
        return self.code_viewer

    def get_log_viewer(self) -> LogViewerWindow:
        return self.log_viewer

    def get_model_config_dialog(self) -> ModelConfigurationDialog:
        return self.model_config_dialog

    def get_plugin_management_dialog(self) -> PluginManagementDialog:
        return self.plugin_management_dialog

    # --- Show Window Methods ---
    def show_main_window(self):
        if self.main_window: self.main_window.show()

    def show_code_viewer(self):
        if self.code_viewer: self.code_viewer.show_window()

    def show_log_viewer(self):
        if self.log_viewer: self.log_viewer.show()

    async def show_model_config_dialog(self):
        """Asynchronously populates model data and then shows the dialog."""
        if self.model_config_dialog:
            # Prevent opening multiple instances of the dialog
            if self.model_config_dialog.isVisible():
                self.model_config_dialog.activateWindow()
                self.model_config_dialog.raise_()
                return

            # Asynchronously populate the model list first
            await self.model_config_dialog.populate_models_async()
            # Then synchronously populate the current selections
            self.model_config_dialog.populate_settings()
            # Now show the dialog non-blockingly
            self.model_config_dialog.show()

    def show_plugin_management_dialog(self):
        if self.plugin_management_dialog: self.plugin_management_dialog.exec()

    # --- UI Update Methods ---
    def update_project_display(self, project_name: str):
        if self.main_window and hasattr(self.main_window, 'sidebar'):
            self.main_window.sidebar.update_project_display(project_name)

    def prepare_code_viewer_for_new_project(self):
        if self.code_viewer: self.code_viewer.prepare_for_new_project_session()

    def load_project_in_code_viewer(self, project_path: str):
        if self.code_viewer:
            self.code_viewer.load_project(project_path)

    def is_fully_initialized(self) -> bool:
        """Check if all windows are initialized."""
        return all([
            self.main_window,
            self.code_viewer,
            self.log_viewer,
            self.model_config_dialog,
            self.plugin_management_dialog
        ])