# src/ava/services/service_manager.py
# FINAL: Standardized all imports to be relative to fix circular dependencies.
import asyncio
from pathlib import Path

from ..event_bus import EventBus
from ..llm_client import LLMClient
from ..project_manager import ProjectManager
from ..execution_engine import ExecutionEngine
from ..plugins.plugin_manager import PluginManager

# Services are now imported relative to the 'ava' package root
from ...services.terminal_service import TerminalService
from ...services.rag_manager import RAGManager
from ...services.architect_service import ArchitectService
from ...services.reviewer_service import ReviewerService
from ...services.validation_service import ValidationService
from ...services.project_indexer_service import ProjectIndexerService
from ...services.import_fixer_service import ImportFixerService
from ...services.generation_coordinator import GenerationCoordinator
from ...services.context_manager import ContextManager
from ...services.dependency_planner import DependencyPlanner
from ...services.integration_validator import IntegrationValidator


class ServiceManager:
    """
    Manages all application services and their dependencies.
    Single responsibility: Service lifecycle and dependency injection.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        # Core components (will be initialized later)
        self.llm_client: LLMClient = None
        self.project_manager: ProjectManager = None
        self.execution_engine: ExecutionEngine = None

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
        self.plugin_manager: PluginManager = None

        self._service_injection_enabled = True

        print("[ServiceManager] Initialized")

    def initialize_core_components(self, project_root: Path, project_manager: ProjectManager):
        """Initialize core components in dependency order."""
        print("[ServiceManager] Initializing core components...")

        # Core components (with correct dependency injection)
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

        # Basic services (no dependencies)
        self.project_indexer_service = ProjectIndexerService()
        self.import_fixer_service = ImportFixerService()

        # Coordination components (depend on service manager)
        self.context_manager = ContextManager(self)
        self.dependency_planner = DependencyPlanner(self)
        self.integration_validator = IntegrationValidator(self)

        # RAG Manager
        self.rag_manager = RAGManager(self.event_bus)
        if self.project_manager:
            self.rag_manager.set_project_manager(self.project_manager)

        # Auto-launch the RAG service now that it's initialized
        self.rag_manager.launch_rag_server()

        # Generation coordinator (depends on coordination components)
        self.generation_coordinator = GenerationCoordinator(
            self, self.event_bus, self.context_manager,
            self.dependency_planner, self.integration_validator
        )

        # Architect Service
        self.architect_service = ArchitectService(
            self,
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

        # --- THIS IS THE FIX ---
        # Validation Service now gets the project_indexer passed in correctly.
        self.validation_service = ValidationService(
            self.event_bus,
            self.project_manager,
            self.reviewer_service,
            self.project_indexer_service
        )
        # --- END OF FIX ---

        # Terminal Service (now using the correct TerminalService)
        self.terminal_service = TerminalService(
            self.event_bus,
            self.project_manager
        )

        print("[ServiceManager] Services initialized")

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

    def get_terminal_service(self) -> TerminalService:
        """Get the terminal service instance."""
        return self.terminal_service

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

    def get_project_indexer_service(self) -> ProjectIndexerService:
        """Get the project indexer service instance."""
        return self.project_indexer_service

    def get_import_fixer_service(self) -> ImportFixerService:
        """Get the import fixer service instance."""
        return self.import_fixer_service

    def get_context_manager(self) -> ContextManager:
        """Get the context manager instance."""
        return self.context_manager

    def get_dependency_planner(self) -> DependencyPlanner:
        """Get the dependency planner instance."""
        return self.dependency_planner

    def get_integration_validator(self) -> IntegrationValidator:
        """Get the integration validator instance."""
        return self.integration_validator

    def get_generation_coordinator(self) -> GenerationCoordinator:
        """Get the generation coordinator instance."""
        return self.generation_coordinator

    def get_plugin_manager(self) -> PluginManager:
        """Get the plugin manager instance."""
        return self.plugin_manager

    def is_fully_initialized(self) -> bool:
        """Check if all services are initialized."""
        return all([
            self.llm_client is not None,
            self.project_manager is not None,
            self.execution_engine is not None,
            self.terminal_service is not None,
            self.rag_manager is not None,
            self.architect_service is not None,
            self.reviewer_service is not None,
            self.validation_service is not None,
            self.project_indexer_service is not None,
            self.import_fixer_service is not None,
            self.context_manager is not None,
            self.dependency_planner is not None,
            self.integration_validator is not None,
            self.generation_coordinator is not None,
            self.plugin_manager is not None,
        ])

    def get_all_services(self) -> dict:
        """Get a dictionary of all available services."""
        return {
            'terminal_service': self.terminal_service,
            'rag_manager': self.rag_manager,
            'architect_service': self.architect_service,
            'reviewer_service': self.reviewer_service,
            'validation_service': self.validation_service,
            'project_indexer_service': self.project_indexer_service,
            'import_fixer_service': self.import_fixer_service,
            'context_manager': self.context_manager,
            'dependency_planner': self.dependency_planner,
            'integration_validator': self.integration_validator,
            'generation_coordinator': self.generation_coordinator,
            'plugin_manager': self.plugin_manager,
        }

    def get_service_status(self) -> dict:
        """Get the status of all services."""
        services = self.get_all_services()
        return {
            name: service is not None
            for name, service in services.items()
        }

    async def shutdown_services(self):
        """Shutdown all services gracefully."""
        print("[ServiceManager] Shutting down services...")

        # Handle plugin manager specially since it has async shutdown
        if self.plugin_manager and hasattr(self.plugin_manager, 'shutdown'):
            try:
                await self.plugin_manager.shutdown()
            except Exception as e:
                print(f"[ServiceManager] Error shutting down plugin manager: {e}")

        # Simple shutdown for other services - most don't need explicit cleanup
        services_to_shutdown = [
            self.terminal_service,
            self.validation_service,
            self.reviewer_service,
            self.architect_service,
            self.generation_coordinator,
            self.rag_manager,  # <-- ADDED RAG MANAGER TO SHUTDOWN
            self.integration_validator,
            self.dependency_planner,
            self.context_manager,
            self.import_fixer_service,
            self.project_indexer_service,
        ]

        for service in services_to_shutdown:
            if service and hasattr(service, 'shutdown'):
                try:
                    # RAG manager has an async shutdown, others are sync
                    if asyncio.iscoroutinefunction(service.shutdown):
                        await service.shutdown()
                    else:
                        service.shutdown()
                except Exception as e:
                    print(f"[ServiceManager] Error shutting down service {type(service).__name__}: {e}")

        print("[ServiceManager] Services shutdown complete")

    async def shutdown(self):
        """Async shutdown method for compatibility with Application."""
        await self.shutdown_services()