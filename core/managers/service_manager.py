# kintsugi_ava/core/managers/service_manager.py
# Creates and manages all services and core components

from core.event_bus import EventBus
from core.llm_client import LLMClient
from core.project_manager import ProjectManager
from core.execution_engine import ExecutionEngine

from services.rag_manager import RAGManager
from services.architect_service import ArchitectService
from services.reviewer_service import ReviewerService
from services.validation_service import ValidationService
from services.terminal_service import TerminalService


class ServiceManager:
    """
    Creates and manages all services and core components.
    Single responsibility: Service lifecycle and dependency management.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        # Core components
        self.llm_client: LLMClient = None
        self.project_manager: ProjectManager = None
        self.execution_engine: ExecutionEngine = None

        # Services
        self.rag_manager: RAGManager = None
        self.architect_service: ArchitectService = None
        self.reviewer_service: ReviewerService = None
        self.validation_service: ValidationService = None
        self.terminal_service: TerminalService = None

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

    def initialize_services(self, code_viewer=None):
        """
        Initialize services in dependency order.

        Args:
            code_viewer: CodeViewer instance needed by TerminalService
        """
        print("[ServiceManager] Initializing services...")

        # RAG Manager (no dependencies on other services)
        self.rag_manager = RAGManager(self.event_bus)

        # Architect Service (depends on rag_manager)
        self.architect_service = ArchitectService(
            self.event_bus,
            self.llm_client,
            self.project_manager,
            self.rag_manager.rag_service
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

    def get_llm_client(self) -> LLMClient:
        """Get the LLM client instance."""
        return self.llm_client

    def get_project_manager(self) -> ProjectManager:
        """Get the project manager instance."""
        return self.project_manager

    def get_execution_engine(self) -> ExecutionEngine:
        """Get the execution engine instance."""
        return self.execution_engine

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

    def is_fully_initialized(self) -> bool:
        """Check if all services are initialized."""
        core_ready = all([
            self.llm_client,
            self.project_manager,
            self.execution_engine
        ])

        services_ready = all([
            self.rag_manager,
            self.architect_service,
            self.reviewer_service,
            self.validation_service,
            self.terminal_service
        ])

        return core_ready and services_ready

    def get_initialization_status(self) -> dict:
        """Get detailed initialization status for debugging."""
        return {
            "core_components": {
                "llm_client": self.llm_client is not None,
                "project_manager": self.project_manager is not None,
                "execution_engine": self.execution_engine is not None
            },
            "services": {
                "rag_manager": self.rag_manager is not None,
                "architect_service": self.architect_service is not None,
                "reviewer_service": self.reviewer_service is not None,
                "validation_service": self.validation_service is not None,
                "terminal_service": self.terminal_service is not None
            },
            "fully_initialized": self.is_fully_initialized()
        }