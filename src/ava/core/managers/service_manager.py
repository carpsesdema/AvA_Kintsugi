# src/ava/core/managers/service_manager.py
from pathlib import Path

from src.ava.core.event_bus import EventBus
from src.ava.core.llm_client import LLMClient
from src.ava.core.project_manager import ProjectManager
from src.ava.core.execution_engine import ExecutionEngine
from src.ava.core.plugins.plugin_manager import PluginManager

from src.ava.services.terminal_service import TerminalService
from src.ava.services.rag_manager import RAGManager
from src.ava.services.architect_service import ArchitectService
from src.ava.services.reviewer_service import ReviewerService
from src.ava.services.validation_service import ValidationService
from src.ava.services.project_indexer_service import ProjectIndexerService
from src.ava.services.import_fixer_service import ImportFixerService
from src.ava.services.generation_coordinator import GenerationCoordinator
from src.ava.services.context_manager import ContextManager
from src.ava.services.dependency_planner import DependencyPlanner
from src.ava.services.integration_validator import IntegrationValidator


class ServiceManager:
    """
    Manages all application services and their dependencies.
    Single responsibility: Service lifecycle and dependency injection.
    """

    def __init__(self, event_bus: EventBus, project_root: Path):
        self.event_bus = event_bus
        self.project_root = project_root

        # Core components (will be initialized later)
        self.llm_client: LLMClient = None
        self.project_manager: ProjectManager = None
        self.execution_engine: ExecutionEngine = None
        self.plugin_manager: PluginManager = None

        # Initialize all service properties to None
        self.terminal_service: TerminalService = None
        self.rag_manager: RAGManager = None
        self.architect_service: ArchitectService = None
        self.reviewer_service: ReviewerService = None
        self.validation_service: ValidationService = None
        self.project_indexer_service: ProjectIndexerService = None
        self.import_fixer_service: ImportFixerService = None
        self.context_manager: ContextManager = None
        self.dependency_planner: DependencyPlanner = None
        self.integration_validator: IntegrationValidator = None
        self.generation_coordinator: GenerationCoordinator = None

        self._service_injection_enabled = True

        print("[ServiceManager] Initialized")

    def initialize_core_components(self, project_root: Path, project_manager: ProjectManager):
        """Initialize core components in dependency order."""
        print("[ServiceManager] Initializing core components...")
        self.llm_client = LLMClient(project_root)
        self.project_manager = project_manager
        self.execution_engine = ExecutionEngine(self.project_manager)
        print("[ServiceManager] Core components initialized")

    async def initialize_plugins(self) -> bool:
        """Initialize plugins asynchronously."""
        if not self.plugin_manager:
            print("[ServiceManager] No plugin manager available")
            return False
        success = await self.plugin_manager.initialize()
        print("[ServiceManager] Plugin initialization completed")
        return success

    def initialize_services(self, code_viewer=None):
        """Initialize services with proper dependency order."""
        print("[ServiceManager] Initializing services...")

        self.project_indexer_service = ProjectIndexerService()
        self.import_fixer_service = ImportFixerService()
        self.context_manager = ContextManager(self)
        self.dependency_planner = DependencyPlanner(self)
        self.integration_validator = IntegrationValidator(self)

        # --- THIS IS THE FIX ---
        # Pass the project_root to the RAGManager
        self.rag_manager = RAGManager(self.event_bus, self.project_root)
        # --- END OF FIX ---
        if self.project_manager:
            self.rag_manager.set_project_manager(self.project_manager)

        self.generation_coordinator = GenerationCoordinator(
            self, self.event_bus, self.context_manager,
            self.dependency_planner, self.integration_validator
        )
        self.architect_service = ArchitectService(
            self, self.event_bus, self.llm_client, self.project_manager,
            self.rag_manager.rag_service, self.project_indexer_service, self.import_fixer_service
        )
        self.reviewer_service = ReviewerService(self.event_bus, self.llm_client)
        self.validation_service = ValidationService(self.event_bus, self.project_manager, self.reviewer_service)
        self.terminal_service = TerminalService(self.event_bus, self.project_manager)

        print("[ServiceManager] Services initialized")

    # Getters...
    def get_llm_client(self) -> LLMClient: return self.llm_client
    def get_project_manager(self) -> ProjectManager: return self.project_manager
    def get_execution_engine(self) -> ExecutionEngine: return self.execution_engine
    def get_terminal_service(self) -> TerminalService: return self.terminal_service
    def get_rag_manager(self) -> RAGManager: return self.rag_manager
    def get_architect_service(self) -> ArchitectService: return self.architect_service
    def get_reviewer_service(self) -> ReviewerService: return self.reviewer_service
    def get_validation_service(self) -> ValidationService: return self.validation_service
    def get_project_indexer_service(self) -> ProjectIndexerService: return self.project_indexer_service
    def get_import_fixer_service(self) -> ImportFixerService: return self.import_fixer_service
    def get_context_manager(self) -> ContextManager: return self.context_manager
    def get_dependency_planner(self) -> DependencyPlanner: return self.dependency_planner
    def get_integration_validator(self) -> IntegrationValidator: return self.integration_validator
    def get_generation_coordinator(self) -> GenerationCoordinator: return self.generation_coordinator
    def get_plugin_manager(self) -> PluginManager: return self.plugin_manager

    def is_fully_initialized(self) -> bool:
        return all([
            self.llm_client, self.project_manager, self.execution_engine, self.terminal_service,
            self.rag_manager, self.architect_service, self.reviewer_service, self.validation_service,
            self.project_indexer_service, self.import_fixer_service, self.context_manager,
            self.dependency_planner, self.integration_validator, self.generation_coordinator, self.plugin_manager
        ])

    def get_all_services(self) -> dict:
        return {name.replace('_service', ''): service for name, service in vars(self).items() if hasattr(service, 'is_service')}

    def get_service_status(self) -> dict:
        return {name: service is not None for name, service in self.get_all_services().items()}

    async def shutdown(self):
        """Async shutdown method for compatibility with Application."""
        print("[ServiceManager] Shutting down services...")
        if self.plugin_manager and hasattr(self.plugin_manager, 'shutdown'):
            try: await self.plugin_manager.shutdown()
            except Exception as e: print(f"[ServiceManager] Error shutting down plugin manager: {e}")
        # Other services shutdown logic...
        print("[ServiceManager] Services shutdown complete")