# src/ava/core/application.py

import asyncio
import sys
from pathlib import Path

from .event_bus import EventBus
from .managers import (
    ServiceManager,
    WindowManager,
    EventCoordinator,
    WorkflowManager,
    TaskManager
)
from .plugins.plugin_manager import PluginManager
from .project_manager import ProjectManager


class Application:
    """
    Main application class that coordinates all components.
    """

    def __init__(self, project_root: Path):
        """
        Initialize the application with the project root path.

        Args:
            project_root: Root directory of the project/executable
        """
        self.project_root = project_root
        print(f"[Application] Initializing with project root: {project_root}")

        # Core components
        self.event_bus = EventBus()
        self.project_manager = ProjectManager()

        # --- FIX: Create the single, authoritative PluginManager here ---
        self.plugin_manager = PluginManager(self.event_bus, self.project_root)

        # --- FIX: Pass the single ProjectManager to the WindowManager ---
        self.window_manager = WindowManager(self.event_bus, self.project_manager)

        # Service and task management
        self.service_manager = ServiceManager(self.event_bus)
        self.task_manager = TaskManager(self.event_bus)

        # Workflow and Event Coordination
        self.workflow_manager = WorkflowManager(self.event_bus)
        self.event_coordinator = EventCoordinator(self.event_bus)

        # State
        self._initialization_complete = False

        # Connect event handlers
        self._connect_events()

    def _connect_events(self):
        """Set up event connections between components."""
        # Window events
        self.event_bus.subscribe("open_code_viewer_requested",
                                 lambda: self.window_manager.show_code_viewer())
        self.event_bus.subscribe("project_root_selected",
                                 lambda root: self.project_manager.load_project(root))

        # Application lifecycle
        self.event_bus.subscribe("application_shutdown",
                                 lambda: asyncio.create_task(self.cancel_all_tasks()))

    async def initialize_async(self):
        """
        Perform async initialization of components.
        """
        print("[Application] Starting async initialization...")

        try:
            # --- FIX: Pass the single PluginManager instance to the ServiceManager ---
            self.service_manager.plugin_manager = self.plugin_manager

            # Configure plugin discovery paths on the single PluginManager
            self._configure_plugin_paths()

            # Initialize service manager's other core components
            self.service_manager.initialize_core_components(self.project_root, self.project_manager)

            # Initialize plugins using the single manager
            await self.service_manager.initialize_plugins()

            # Initialize services
            self.service_manager.initialize_services()

            # Initialize GUI windows (which may depend on services)
            self.window_manager.initialize_windows(
                self.service_manager.get_llm_client(),
                self.service_manager
            )

            # --- THIS IS THE FIX ---
            # After plugins are loaded AND windows are created, update the sidebar UI.
            self.update_sidebar_plugin_status()
            # --- END OF FIX ---

            # Set manager references for all coordinators
            self.task_manager.set_managers(self.service_manager, self.window_manager)
            self.workflow_manager.set_managers(self.service_manager, self.window_manager, self.task_manager)
            self.event_coordinator.set_managers(self.service_manager, self.window_manager, self.task_manager,
                                                self.workflow_manager)

            # Wire up all events to connect the application components
            self.event_coordinator.wire_all_events()

            self._initialization_complete = True
            print("[Application] Async initialization complete")

        except Exception as e:
            print(f"[Application] Error during initialization: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _configure_plugin_paths(self):
        """Configure plugin discovery paths based on execution mode."""
        # Nuitka places the included 'ava' data folder right next to the executable.
        # The project root is the directory containing the executable.
        builtin_plugins_path = self.project_root / "ava" / "core" / "plugins" / "examples"

        if builtin_plugins_path.exists():
            self.plugin_manager.add_discovery_path(builtin_plugins_path)
            print(f"[Application] Added plugin discovery path: {builtin_plugins_path}")
        else:
            print(f"[Application] Warning: Built-in plugin path not found at {builtin_plugins_path}")

        # Also look for a 'plugins' directory next to the executable for custom user plugins
        custom_plugins_path = self.project_root / "plugins"
        if custom_plugins_path.exists():
            self.plugin_manager.add_discovery_path(custom_plugins_path)
            print(f"[Application] Added custom plugin path: {custom_plugins_path}")

    def update_sidebar_plugin_status(self):
        """Gets plugin status from the manager and tells the sidebar to update."""
        if not self.plugin_manager or not self.window_manager:
            print("[Application] Cannot update plugin status: managers not ready.")
            return

        try:
            enabled_plugins = self.plugin_manager.config.get_enabled_plugins()
            if not enabled_plugins:
                status = "off"
            else:
                all_plugins_info = self.plugin_manager.get_all_plugins_info()
                status = "ok"  # Assume OK unless proven otherwise
                for plugin in all_plugins_info:
                    if plugin['name'] in enabled_plugins and plugin.get('state') != 'started':
                        status = "error"
                        break

            main_window = self.window_manager.get_main_window()
            if main_window and hasattr(main_window, 'sidebar'):
                main_window.sidebar.update_plugin_status(status)
                print(f"[Application] Updated sidebar plugin status to: {status}")
            else:
                print("[Application] Could not find sidebar to update.")

        except Exception as e:
            print(f"[Application] Error updating sidebar plugin status: {e}")

    def show(self):
        """Show the main application window."""
        if not self._initialization_complete:
            print("[Application] Warning: Attempting to show before initialization complete")

        self.window_manager.show_main_window()

    async def cancel_all_tasks(self):
        """
        Cleanly shuts down all background processes, plugins, and tasks.
        """
        print("[Application] Cancelling all tasks and shutting down...")

        # 1. Cancel task manager tasks
        if self.task_manager:
            await self.task_manager.cancel_all_tasks()

        # 2. Shutdown service manager (includes plugins)
        if self.service_manager:
            await self.service_manager.shutdown()

        print("[Application] All tasks cancelled and plugins shut down")

    def is_fully_initialized(self) -> bool:
        """Check if the application is fully initialized and ready."""
        return (self._initialization_complete and
                self.service_manager.is_fully_initialized() and
                self.window_manager.is_fully_initialized())