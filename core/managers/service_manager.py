# kintsugi_ava/core/managers/service_manager.py
# Creates and manages all services and core components
# V2: Added PluginManager integration

from pathlib import Path

from core.event_bus import EventBus
from core.llm_client import LLMClient
from core.project_manager import ProjectManager
from core.execution_engine import ExecutionEngine

# Plugin system imports
from core.plugins import PluginManager

from services.rag_manager import RAGManager
from services.architect_service import ArchitectService
from services.reviewer_service import ReviewerService
from services.validation_service import ValidationService
from services.terminal_service import TerminalService
from services.project_indexer_service import ProjectIndexerService
from services.import_fixer_service import ImportFixerService


class ServiceManager:
    """
    Creates and manages all services and core components.
    Single responsibility: Service lifecycle and dependency management.
    V2: Now includes plugin system management.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        # Core components
        self.llm_client: LLMClient = None
        self.project_manager: ProjectManager = None
        self.execution_engine: ExecutionEngine = None

        # Plugin system
        self.plugin_manager: PluginManager = None

        # Services
        self.rag_manager: RAGManager = None
        self.architect_service: ArchitectService = None
        self.reviewer_service: ReviewerService = None
        self.validation_service: ValidationService = None
        self.terminal_service: TerminalService = None
        self.project_indexer_service: ProjectIndexerService = None
        self.import_fixer_service: ImportFixerService = None

        print("[ServiceManager] Initialized")

    def initialize_core_components(self):
        """Initialize core components in dependency order."""
        print("[ServiceManager] Initializing core components...")

        # Core components (no dependencies)
        self.llm_client = LLMClient()
        self.project_manager = ProjectManager()

        # Execution engine depends on project manager
        self.execution_engine = ExecutionEngine(self.project_manager)

        print("[ServiceManager] Core components initialized")

    def initialize_plugin_system(self):
        """Initialize the plugin system."""
        print("[ServiceManager] Initializing plugin system...")

        # Create plugin manager
        self.plugin_manager = PluginManager(self.event_bus)

        # Add standard discovery paths
        self._setup_plugin_discovery_paths()

        print("[ServiceManager] Plugin system initialized")

    def _setup_plugin_discovery_paths(self):
        """Set up standard plugin discovery paths."""
        if not self.plugin_manager:
            return

        # Standard plugin locations
        plugin_paths = [
            Path("plugins"),  # Local plugins directory
            Path("core/plugins/examples"),  # Example plugins
            Path.home() / ".kintsugi_ava" / "plugins",  # User plugins directory
        ]

        # Create directories if they don't exist and add to discovery
        for path in plugin_paths:
            try:
                if not path.exists():
                    path.mkdir(parents=True, exist_ok=True)
                    print(f"[ServiceManager] Created plugin directory: {path}")

                self.plugin_manager.add_discovery_path(path)
                print(f"[ServiceManager] Added plugin discovery path: {path}")

            except Exception as e:
                print(f"[ServiceManager] Warning: Could not set up plugin path {path}: {e}")

    async def initialize_plugins(self):
        """Discover and initialize plugins asynchronously."""
        if not self.plugin_manager:
            print("[ServiceManager] Plugin manager not initialized")
            return False

        print("[ServiceManager] Starting plugin discovery and initialization...")

        success = await self.plugin_manager.initialize()

        if success:
            print("[ServiceManager] Plugin system initialization completed successfully")
        else:
            print("[ServiceManager] Plugin system initialization completed with errors")

        return success

    def initialize_services(self, code_viewer=None):
        """
        Initialize services in dependency order.

        Args:
            code_viewer: CodeViewer instance needed by TerminalService
        """
        print("[ServiceManager] Initializing services...")

        # --- NEW: Instantiate our micro-agents ---
        self.project_indexer_service = ProjectIndexerService()
        self.import_fixer_service = ImportFixerService()
        # ----------------------------------------

        # RAG Manager (no dependencies on other services)
        self.rag_manager = RAGManager(self.event_bus)

        # Set project manager reference for RAG operations
        if self.project_manager:
            self.rag_manager.set_project_manager(self.project_manager)

        # Architect Service (now depends on our new micro-agents)
        self.architect_service = ArchitectService(
            self.event_bus,
            self.llm_client,
            self.project_manager,
            self.rag_manager.rag_service,
            self.project_indexer_service,
            self.import_fixer_service
        )

        # Reviewer Service
        self.reviewer_service = ReviewerService(
            self.event_bus,
            self.llm_client
        )

        # Validation Service (depends on reviewer_service)
        self.validation_service = ValidationService(
            self.event_bus,
            self.execution_engine,
            self.project_manager,
            self.reviewer_service
        )

        # Terminal Service (depends on code_viewer, needs to be set later)
        if code_viewer:
            self.terminal_service = TerminalService(
                self.event_bus,
                self.project_manager,
                self.execution_engine,
                code_viewer
            )

        print("[ServiceManager] Services initialized")

    def set_terminal_service_code_viewer(self, code_viewer):
        """
        Set the code viewer for terminal service after window manager is ready.

        Args:
            code_viewer: CodeViewer instance
        """
        if not self.terminal_service:
            self.terminal_service = TerminalService(
                self.event_bus,
                self.project_manager,
                self.execution_engine,
                code_viewer
            )
            print("[ServiceManager] Terminal service initialized with code viewer")

    # Core component getters
    def get_llm_client(self) -> LLMClient:
        """Get the LLM client instance."""
        return self.llm_client

    def get_project_manager(self) -> ProjectManager:
        """Get the project manager instance."""
        return self.project_manager

    def get_execution_engine(self) -> ExecutionEngine:
        """Get the execution engine instance."""
        return self.execution_engine

    # Plugin system getter
    def get_plugin_manager(self) -> PluginManager:
        """Get the plugin manager instance."""
        return self.plugin_manager

    # Service getters
    def get_rag_manager(self) -> RAGManager:
        """Get the RAG manager instance."""
        return self.rag_manager

    def get_architect_service(self) -> ArchitectService:
        """Get the architect service instance."""
        return self.architect_service

    def get_reviewer_service(self) -> ReviewerService:
        """Get the reviewer service instance."""
        return self.reviewer_service

    def get_validation_service(self) -> ValidationService:
        """Get the validation service instance."""
        return self.validation_service

    def get_terminal_service(self) -> TerminalService:
        """Get the terminal service instance."""
        return self.terminal_service

    # --- NEW: Getters for our new micro-agents ---
    def get_project_indexer_service(self) -> ProjectIndexerService:
        """Get the project indexer service instance."""
        return self.project_indexer_service

    def get_import_fixer_service(self) -> ImportFixerService:
        """Get the import fixer service instance."""
        return self.import_fixer_service
    # -------------------------------------------

    def is_fully_initialized(self) -> bool:
        """Check if all services are initialized."""
        core_ready = all([
            self.llm_client,
            self.project_manager,
            self.execution_engine
        ])

        plugin_ready = self.plugin_manager is not None

        services_ready = all([
            self.rag_manager,
            self.architect_service,
            self.reviewer_service,
            self.validation_service,
            self.terminal_service,
            self.project_indexer_service,
            self.import_fixer_service
        ])

        return core_ready and plugin_ready and services_ready

    async def shutdown(self):
        """Shutdown all services and plugins gracefully."""
        print("[ServiceManager] Starting shutdown sequence...")

        # Shutdown plugins first (they may depend on services)
        if self.plugin_manager:
            await self.plugin_manager.shutdown()

        # Shutdown other services
        if self.rag_manager:
            self.rag_manager.terminate_rag_server()

        print("[ServiceManager] Shutdown complete")

    def get_initialization_status(self) -> dict:
        """Get detailed initialization status for debugging."""
        return {
            "core_components": {
                "llm_client": self.llm_client is not None,
                "project_manager": self.project_manager is not None,
                "execution_engine": self.execution_engine is not None
            },
            "plugin_system": {
                "plugin_manager": self.plugin_manager is not None,
                "plugin_status": self.plugin_manager.get_all_plugin_status() if self.plugin_manager else {}
            },
            "services": {
                "rag_manager": self.rag_manager is not None,
                "architect_service": self.architect_service is not None,
                "reviewer_service": self.reviewer_service is not None,
                "validation_service": self.validation_service is not None,
                "terminal_service": self.terminal_service is not None,
                "project_indexer_service": self.project_indexer_service is not None,
                "import_fixer_service": self.import_fixer_service is not None
            },
            "fully_initialized": self.is_fully_initialized()
        }