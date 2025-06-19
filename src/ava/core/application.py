# src/ava/core/application.py

import asyncio
import sys
from pathlib import Path

from ava.core.event_bus import EventBus
from ava.core.managers import (
    ServiceManager,
    WindowManager,
    EventCoordinator,
    WorkflowManager,
    TaskManager
)
from ava.core.plugins.plugin_manager import PluginManager
from ava.gui.project_context_manager import ProjectContextManager
from ava.core.project_manager import ProjectManager


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
        self.project_manager = ProjectManager()  # Only takes workspace path parameter

        # Plugin system - pass the project root
        self.plugin_manager = PluginManager(self.event_bus, project_root)

        # Service and task management
        self.service_manager = ServiceManager(self.event_bus, self.plugin_manager)
        self.task_manager = TaskManager()

        # GUI components
        self.window_manager = WindowManager(self.event_bus, self.project_manager)

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
                                 lambda root: self.project_manager.set_project_root(Path(root)))

        # Application lifecycle
        self.event_bus.subscribe("application_shutdown",
                                 lambda: asyncio.create_task(self.cancel_all_tasks()))

    async def initialize_async(self):
        """
        Perform async initialization of components.
        """
        print("[Application] Starting async initialization...")

        try:
            # Configure plugin discovery paths
            self._configure_plugin_paths()

            # Initialize service manager (includes plugin initialization)
            await self.service_manager.initialize()

            # Initialize any other async components
            # ...

            self._initialization_complete = True
            print("[Application] Async initialization complete")

        except Exception as e:
            print(f"[Application] Error during initialization: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _configure_plugin_paths(self):
        """Configure plugin discovery paths based on execution mode."""
        if getattr(sys, 'frozen', False):
            # Running as bundled executable
            # PyInstaller extracts data files to sys._MEIPASS
            meipass = Path(sys._MEIPASS)

            # Built-in plugins from the bundled application
            builtin_plugins = meipass / "ava" / "core" / "plugins" / "examples"
            if builtin_plugins.exists():
                self.plugin_manager.add_discovery_path(builtin_plugins)
                print(f"[Application] Added bundled plugin path: {builtin_plugins}")

            # Custom plugins directory next to the executable
            custom_plugins = self.project_root / "plugins"
            if custom_plugins.exists():
                self.plugin_manager.add_discovery_path(custom_plugins)
                print(f"[Application] Added custom plugin path: {custom_plugins}")
        else:
            # Running from source
            # Built-in example plugins
            builtin_plugins = self.project_root / "src" / "ava" / "core" / "plugins" / "examples"
            if builtin_plugins.exists():
                self.plugin_manager.add_discovery_path(builtin_plugins)

            # Custom plugins directory
            custom_plugins = self.project_root / "plugins"
            if custom_plugins.exists():
                self.plugin_manager.add_discovery_path(custom_plugins)

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