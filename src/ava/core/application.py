# src/ava/core/application.py

import asyncio
import sys
from pathlib import Path

from src.ava.core.event_bus import EventBus
from src.ava.core.managers import (
    ServiceManager,
    WindowManager,
    EventCoordinator,
    WorkflowManager,
    TaskManager
)
from src.ava.core.plugins.plugin_manager import PluginManager
from src.ava.core.project_manager import ProjectManager


class Application:
    """
    Main application class that coordinates all components.
    """

    def __init__(self, project_root: Path):
        """
        Initialize the application with the project root path.

        Args:
            project_root: Root directory for data files.
                          When running from source, this is typically <repo_root>/src.
                          When bundled, this is sys.executable.parent or sys._MEIPASS.
        """
        self.project_root = project_root
        print(f"[Application] Initializing with data_files_root: {self.project_root}")

        self.event_bus = EventBus()
        # ProjectManager still manages the user's workspace (e.g., "workspace/" directory)
        # It does not depend on the data_files_root for its primary operation.
        self.project_manager = ProjectManager()
        # PluginManager needs data_files_root for plugins.json AND for plugin discovery
        self.plugin_manager = PluginManager(self.event_bus, self.project_root)
        self.window_manager = WindowManager(self.event_bus, self.project_manager)
        # ServiceManager and its children (LLMClient, RAGManager) need data_files_root
        self.service_manager = ServiceManager(self.event_bus, self.project_root)
        self.task_manager = TaskManager(self.event_bus)
        self.workflow_manager = WorkflowManager(self.event_bus)
        self.event_coordinator = EventCoordinator(self.event_bus)
        self._initialization_complete = False
        self._connect_events()

    def _connect_events(self):
        """Set up event connections between components."""
        self.event_bus.subscribe("open_code_viewer_requested", self.window_manager.show_code_viewer)
        self.event_bus.subscribe("project_root_selected", self.project_manager.load_project)
        self.event_bus.subscribe("application_shutdown", lambda: asyncio.create_task(self.cancel_all_tasks()))

    async def initialize_async(self):
        """Perform async initialization of components."""
        print("[Application] Starting async initialization...")
        try:
            self.service_manager.plugin_manager = self.plugin_manager
            self._configure_plugin_paths() # Uses self.project_root (data_files_root)
            # Pass data_files_root to service_manager for its sub-components
            self.service_manager.initialize_core_components(self.project_root, self.project_manager)
            await self.service_manager.initialize_plugins()
            self.service_manager.initialize_services()

            rag_manager = self.service_manager.get_rag_manager()
            if rag_manager:
                print("[Application] Triggering automatic RAG server launch...")
                asyncio.create_task(rag_manager.launch_rag_server())

            # Pass data_files_root to window_manager for its sub-components (like LoadingIndicator)
            self.window_manager.initialize_windows(
                self.service_manager.get_llm_client(),
                self.service_manager,
                self.project_root # Pass data_files_root
            )
            self.update_sidebar_plugin_status()
            self.task_manager.set_managers(self.service_manager, self.window_manager)
            self.workflow_manager.set_managers(self.service_manager, self.window_manager, self.task_manager)
            self.event_coordinator.set_managers(self.service_manager, self.window_manager, self.task_manager, self.workflow_manager)
            self.event_coordinator.wire_all_events()
            self._initialization_complete = True
            print("[Application] Async initialization complete")
        except Exception as e:
            print(f"[Application] CRITICAL ERROR during initialization: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            raise

    def _configure_plugin_paths(self):
        """
        Configure plugin discovery paths.
        Uses self.project_root (which is data_files_root) to find bundled plugins.
        When running from source, it derives the actual repository root to find plugins.
        """
        if getattr(sys, 'frozen', False):
            # Bundled executable:
            # self.project_root is data_files_root (e.g., sys.executable.parent or sys._MEIPASS)
            # Built-in plugins are expected in: data_files_root / "ava" / "core" / "plugins" / "examples"
            bundled_builtin_plugins_dir = self.project_root / "ava" / "core" / "plugins" / "examples"
            if bundled_builtin_plugins_dir.exists():
                self.plugin_manager.add_discovery_path(bundled_builtin_plugins_dir)
                print(f"[Application] Added bundled plugin discovery path: {bundled_builtin_plugins_dir}")
            else:
                # This path might be different for cx_Freeze if _MEIPASS is not defined.
                # If sys.executable.parent is used, this check should still be valid.
                print(f"[Application] Bundled built-in plugin path not found: {bundled_builtin_plugins_dir}")

            # Optional: For custom plugins placed in a "plugins" folder next to the executable
            custom_plugins_next_to_exe = self.project_root / "plugins"
            if custom_plugins_next_to_exe.exists():
                self.plugin_manager.add_discovery_path(custom_plugins_next_to_exe)
                print(f"[Application] Added custom (next to exe) plugin discovery path: {custom_plugins_next_to_exe}")
            else:
                print(f"[Application] Custom plugin path (next to exe) not found: {custom_plugins_next_to_exe}")

        else:
            # Source mode:
            # self.project_root is .../repo_root/src
            # We need to find the actual repository root to locate plugins.
            actual_repo_root = self.project_root.parent # Go up one level from 'src'

            # Path for built-in plugins when running from source
            builtin_plugins_src_dir = actual_repo_root / "src" / "ava" / "core" / "plugins" / "examples"
            if builtin_plugins_src_dir.exists():
                self.plugin_manager.add_discovery_path(builtin_plugins_src_dir)
                print(f"[Application] Added source (built-in) plugin discovery path: {builtin_plugins_src_dir}")
            else:
                print(f"[Application] Source built-in plugin path not found: {builtin_plugins_src_dir}")

            # Path for custom plugins in repo_root/plugins when running from source
            custom_plugins_repo_dir = actual_repo_root / "plugins"
            if custom_plugins_repo_dir.exists():
                self.plugin_manager.add_discovery_path(custom_plugins_repo_dir)
                print(f"[Application] Added source (custom) plugin discovery path: {custom_plugins_repo_dir}")
            else:
                print(f"[Application] Source custom plugin path not found: {custom_plugins_repo_dir}")


    def update_sidebar_plugin_status(self):
        """Gets plugin status from the manager and tells the sidebar to update."""
        if not self.plugin_manager or not self.window_manager: return
        try:
            enabled_plugins = self.plugin_manager.config.get_enabled_plugins()
            status = "off"
            if enabled_plugins:
                all_plugins_info = self.plugin_manager.get_all_plugins_info()
                status = "ok"
                for plugin in all_plugins_info:
                    if plugin['name'] in enabled_plugins and plugin.get('state') != 'started':
                        status = "error"; break
            main_window = self.window_manager.get_main_window()
            if main_window and hasattr(main_window, 'sidebar'):
                main_window.sidebar.update_plugin_status(status)
        except Exception as e:
            print(f"[Application] Error updating sidebar plugin status: {e}")

    def show(self):
        self.window_manager.show_main_window()

    async def cancel_all_tasks(self):
        print("[Application] Cancelling all tasks and shutting down...")
        if self.task_manager: await self.task_manager.cancel_all_tasks()
        if self.service_manager: await self.service_manager.shutdown()
        print("[Application] All tasks cancelled and plugins shut down")

    def is_fully_initialized(self) -> bool:
        return (self._initialization_complete and
                self.service_manager.is_fully_initialized() and
                self.window_manager.is_fully_initialized())