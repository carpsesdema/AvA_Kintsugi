# kintsugi_ava/core/application.py
# V13: Completely refactored into clean SRP-based architecture with managers

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
    """

    def __init__(self):
        print("[Application] Initializing with manager-based architecture...")

        # --- Central Communication ---
        self.event_bus = EventBus()

        # --- Create Managers (just instances, no initialization yet) ---
        self.service_manager = ServiceManager(self.event_bus)
        self.window_manager = WindowManager(self.event_bus)
        self.event_coordinator = EventCoordinator(self.event_bus)
        self.workflow_manager = WorkflowManager(self.event_bus)
        self.task_manager = TaskManager(self.event_bus)

        # --- Initialize in dependency order ---
        self._initialize_all_managers()

        print("[Application] Manager-based architecture initialized successfully")

    def _initialize_all_managers(self):
        """Initialize all managers in the correct dependency order."""
        print("[Application] Initializing managers in dependency order...")

        # 1. Initialize core components first (no dependencies)
        self.service_manager.initialize_core_components()

        # 2. Initialize windows (depends on core components)
        llm_client = self.service_manager.get_llm_client()
        self.window_manager.initialize_windows(llm_client)

        # 3. Initialize services (some depend on windows being available)
        code_viewer = self.window_manager.get_code_viewer()
        self.service_manager.initialize_services(code_viewer)

        # 4. Set manager cross-references for coordination
        self._set_manager_references()

        # 5. Wire all events (must happen after all components exist)
        self.event_coordinator.wire_all_events()

        print("[Application] All managers initialized and wired")

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

    def show(self):
        """Show the main application window."""
        self.window_manager.show_main_window()

    async def cancel_all_tasks(self):
        """
        Cleanly shuts down all background processes and tasks.
        This is called when the application is about to quit.
        """
        print("[Application] Starting shutdown sequence...")

        # 1. Terminate external processes (RAG server)
        rag_manager = self.service_manager.get_rag_manager()
        if rag_manager:
            rag_manager.terminate_rag_server()

        # 2. Cancel all background tasks
        await self.task_manager.cancel_all_tasks()

        print("[Application] Shutdown sequence complete")

    def get_system_status(self) -> dict:
        """Get comprehensive system status for debugging."""
        return {
            "application": "Manager-based Architecture v13",
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