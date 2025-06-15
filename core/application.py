# kintsugi_ava/core/application.py
# V14: Added plugin system integration to clean SRP-based architecture

import asyncio

from core.event_bus import EventBus
from core.managers import (
    ServiceManager,
    WindowManager,
    EventCoordinator,
    WorkflowManager,
    TaskManager
)


class Application:
    """
    The main application coordinator - now lean and focused.
    Single responsibility: Initialize and coordinate managers.
    V14: Now includes plugin system integration.
    """

    def __init__(self):
        print("[Application] Initializing with plugin-enabled manager architecture...")

        # --- Central Communication ---
        self.event_bus = EventBus()

        # --- Create Managers (just instances, no initialization yet) ---
        self.service_manager = ServiceManager(self.event_bus)
        self.window_manager = WindowManager(self.event_bus)
        self.event_coordinator = EventCoordinator(self.event_bus)
        self.workflow_manager = WorkflowManager(self.event_bus)
        self.task_manager = TaskManager(self.event_bus)

        # Track initialization state
        self._initialization_complete = False

        print("[Application] Managers created, starting async initialization...")

    async def initialize_async(self):
        """
        Async initialization method that handles plugin system setup.
        Must be called after creating the Application instance.
        """
        if self._initialization_complete:
            print("[Application] Already initialized")
            return

        print("[Application] Starting async initialization sequence...")

        # --- Initialize in dependency order ---
        await self._initialize_all_managers_async()

        self._initialization_complete = True
        print("[Application] Plugin-enabled manager architecture initialized successfully")

    async def _initialize_all_managers_async(self):
        """Initialize all managers in the correct dependency order with plugin support."""
        print("[Application] Initializing managers in dependency order...")

        # 1. Initialize core components first (no dependencies)
        self.service_manager.initialize_core_components()

        # 2. Initialize plugin system (depends on core components)
        self.service_manager.initialize_plugin_system()

        # 3. Discover and load plugins (async operation)
        plugin_success = await self.service_manager.initialize_plugins()
        if plugin_success:
            print("[Application] Plugin system ready")
        else:
            print("[Application] Plugin system initialized with warnings")

        # 4. Initialize windows (depends on core components, may be used by plugins)
        llm_client = self.service_manager.get_llm_client()
        self.window_manager.initialize_windows(llm_client)

        # 5. Initialize services (some depend on windows being available)
        code_viewer = self.window_manager.get_code_viewer()
        self.service_manager.initialize_services(code_viewer)

        # 6. Set manager cross-references for coordination
        self._set_manager_references()

        # 7. Wire all events (must happen after all components exist)
        self.event_coordinator.wire_all_events()

        # 8. Wire plugin-specific events
        self._wire_plugin_events()

        print("[Application] All managers initialized and wired with plugin support")

    def _set_manager_references(self):
        """Set cross-references between managers for coordination."""
        # EventCoordinator needs all managers for event wiring
        self.event_coordinator.set_managers(
            self.service_manager,
            self.window_manager,
            self.workflow_manager,
            self.task_manager
        )

        # WorkflowManager needs other managers for orchestration
        self.workflow_manager.set_managers(
            self.service_manager,
            self.window_manager,
            self.task_manager
        )

        # TaskManager needs managers for task coordination
        self.task_manager.set_managers(
            self.service_manager,
            self.window_manager
        )

    def _wire_plugin_events(self):
        """Wire plugin-specific events."""
        plugin_manager = self.service_manager.get_plugin_manager()
        if not plugin_manager:
            return

        # Subscribe to application shutdown to ensure plugins are properly shut down
        self.event_bus.subscribe("application_shutdown",
                                 lambda: asyncio.create_task(plugin_manager.shutdown()))

        # Log plugin state changes
        self.event_bus.subscribe("plugin_state_changed",
                                 lambda name, old, new: print(
                                     f"[Application] Plugin '{name}': {old.value} -> {new.value}"))

        print("[Application] Plugin events wired")

    def show(self):
        """Show the main application window."""
        if not self._initialization_complete:
            print("[Application] Warning: Attempting to show before initialization complete")

        self.window_manager.show_main_window()

    async def cancel_all_tasks(self):
        """
        Cleanly shuts down all background processes, plugins, and tasks.
        This is called when the application is about to quit.
        """
        print("[Application] Starting shutdown sequence...")

        # 1. Emit application shutdown event for plugins and other components
        self.event_bus.emit("application_shutdown")

        # 2. Cancel all background tasks
        await self.task_manager.cancel_all_tasks()

        # 3. Shutdown services and plugins through service manager
        await self.service_manager.shutdown()

        print("[Application] Shutdown sequence complete")

    def get_system_status(self) -> dict:
        """Get comprehensive system status for debugging."""
        plugin_status = {}
        plugin_manager = self.service_manager.get_plugin_manager()
        if plugin_manager:
            plugin_status = {
                "plugin_count": len(plugin_manager.get_all_plugin_status()),
                "enabled_plugins": [name for name, status in plugin_manager.get_all_plugin_status().items()
                                    if status.get("enabled", False)],
                "loaded_plugins": [name for name, status in plugin_manager.get_all_plugin_status().items()
                                   if status.get("loaded", False)]
            }

        return {
            "application": "Plugin-Enabled Manager Architecture v14",
            "initialization_complete": self._initialization_complete,
            "plugin_system": plugin_status,
            "managers": {
                "service_manager": self.service_manager.get_initialization_status(),
                "window_manager": self.window_manager.get_initialization_status(),
                "event_coordinator": self.event_coordinator.get_subscription_status(),
                "workflow_manager": self.workflow_manager.get_workflow_status(),
                "task_manager": self.task_manager.get_task_status()
            },
            "overall_health": self._assess_overall_health()
        }

    def _assess_overall_health(self) -> str:
        """Assess overall application health."""
        try:
            if not self._initialization_complete:
                return "Initializing"

            service_ok = self.service_manager.is_fully_initialized()
            window_ok = self.window_manager.is_fully_initialized()

            if service_ok and window_ok:
                return "Healthy"
            elif service_ok or window_ok:
                return "Partially Initialized"
            else:
                return "Initialization Failed"

        except Exception as e:
            return f"Error: {e}"

    def is_ready(self) -> bool:
        """Check if the application is fully initialized and ready to use."""
        return (self._initialization_complete and
                self.service_manager.is_fully_initialized() and
                self.window_manager.is_fully_initialized())