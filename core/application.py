# kintsugi_ava/core/application.py
# Fixed to match your existing application pattern and fix the terminal system

import asyncio
from pathlib import Path

from core.event_bus import EventBus
from core.managers import (
    ServiceManager,
    WindowManager,
    EventCoordinator,
    WorkflowManager,
    TaskManager
)
from core.plugins import PluginState


class Application:
    """
    The main application coordinator - now lean and focused.
    Single responsibility: Initialize and coordinate managers.
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
        # FIX: Tell the plugin manager where to look for plugins.
        # The user's example plugin is in `core/plugins/examples`, so we add that path.
        # We also add the root `plugins` directory for any user-added plugins.
        plugin_manager = self.service_manager.get_plugin_manager()
        plugin_manager.add_discovery_path(Path("core/plugins/examples"))
        plugin_manager.add_discovery_path(Path("plugins"))


        # 3. Discover and load plugins (async operation)
        plugin_success = await self.service_manager.initialize_plugins()
        if plugin_success:
            print("[Application] Plugin system ready")
        else:
            print("[Application] Plugin system initialized with warnings")

        # 4. Initialize windows (depends on core components, may be used by plugins)
        llm_client = self.service_manager.get_llm_client()
        self.window_manager.initialize_windows(llm_client, self.service_manager)

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
            self.task_manager,
            self.workflow_manager
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
        """Wire plugin-specific events, including UI updates."""
        plugin_manager = self.service_manager.get_plugin_manager()
        if not plugin_manager:
            return

        self.event_bus.subscribe("application_shutdown",
                                 lambda: asyncio.create_task(plugin_manager.shutdown()))

        sidebar = self.window_manager.get_main_window().sidebar

        # --- NEW: Handler for plugin state changes that updates the UI ---
        def handle_plugin_state_change(name, old_state, new_state):
            """This function is called by the event bus on any plugin state change."""
            # Log the change to the console for debugging
            print(f"[Application] Plugin '{name}': {old_state.value} -> {new_state.value}")

            # Update the sidebar UI with the new total status
            if plugin_manager and sidebar:
                try:
                    all_status = plugin_manager.get_all_plugin_status()
                    # Filter for plugins that are 'STARTED'
                    active_plugins = [
                        s for s in all_status.values()
                        if s.get('state') == PluginState.STARTED.value
                    ]
                    sidebar.update_plugin_status(len(active_plugins), len(all_status))
                except Exception as e:
                    print(f"[Application] Error updating plugin status on sidebar: {e}")

        # Subscribe the unified handler to the event
        self.event_bus.subscribe("plugin_state_changed", handle_plugin_state_change)

        # Call once on startup to set the initial state correctly
        if sidebar:
            try:
                all_status = plugin_manager.get_all_plugin_status()
                active_plugins = [
                    s for s in all_status.values()
                    if s.get('state') == PluginState.STARTED.value
                ]
                sidebar.update_plugin_status(len(active_plugins), len(all_status))
            except Exception as e:
                print(f"[Application] Error setting initial plugin status on sidebar: {e}")

        print("[Application] Plugin events wired")

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