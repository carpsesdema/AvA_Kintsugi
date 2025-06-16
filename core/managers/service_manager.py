# core/managers/service_manager.py
# V6: Added coordination components for integrated code generation
# Single Responsibility: Service lifecycle and dependency management

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Optional

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

# NEW: Coordination components
from services.generation_coordinator import GenerationCoordinator
from services.context_manager import ContextManager
from services.dependency_planner import DependencyPlanner
from services.integration_validator import IntegrationValidator

if TYPE_CHECKING:
    from core.plugins import PluginBase


class ServiceManager:
    """
    Creates and manages all services and core components.
    Single responsibility: Service lifecycle and dependency management.
    V6: Now includes coordination components for integrated code generation.
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

        # NEW: Coordination components
        self.context_manager: ContextManager = None
        self.dependency_planner: DependencyPlanner = None
        self.integration_validator: IntegrationValidator = None
        self.generation_coordinator: GenerationCoordinator = None

        # Service injection tracking
        self._service_injection_enabled = False

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

        # Setup service injection event handling
        self._setup_service_injection()

        print("[ServiceManager] Plugin system initialized")

    def _setup_plugin_discovery_paths(self):
        """Set up standard plugin discovery paths."""
        core_plugins_path = Path(__file__).parent.parent / "plugins" / "examples"
        if core_plugins_path.exists():
            self.plugin_manager.add_discovery_path(core_plugins_path)
            print(f"[ServiceManager] Added plugin discovery path: {core_plugins_path}")

    def _setup_service_injection(self):
        """Set up service injection for plugins that need service references."""
        # Subscribe to plugin service manager requests
        self.event_bus.subscribe("plugin_service_manager_request", self._handle_service_injection_request)
        self._service_injection_enabled = True
        print("[ServiceManager] Service injection system enabled")

    async def initialize_plugins(self) -> bool:
        """
        Initialize the plugin system - discover plugins and load enabled ones.

        Returns:
            True if initialization succeeded, False otherwise
        """
        if not self.plugin_manager:
            print("[ServiceManager] Plugin manager not initialized, cannot initialize plugins")
            return False

        try:
            success = await self.plugin_manager.initialize()
            if success:
                print("[ServiceManager] Plugin initialization completed successfully")
                # Inject services into any plugins that need them after loading
                if self._service_injection_enabled:
                    self.inject_services_into_all_compatible_plugins()
            else:
                print("[ServiceManager] Plugin initialization completed with warnings")
            return success
        except Exception as e:
            print(f"[ServiceManager] Error during plugin initialization: {e}")
            return False

    def _handle_service_injection_request(self, plugin_name: str):
        """
        Handle a plugin's request for service manager injection.

        Args:
            plugin_name: Name of the plugin requesting injection
        """
        if self.inject_services_into_plugin(plugin_name):
            print(f"[ServiceManager] Services injected into plugin: {plugin_name}")
        else:
            print(f"[ServiceManager] Failed to inject services into plugin: {plugin_name}")

    def inject_services_into_plugin(self, plugin_name: str) -> bool:
        """
        Inject service references into a specific plugin.

        Args:
            plugin_name: Name of the plugin to inject services into

        Returns:
            True if injection succeeded, False otherwise
        """
        if not self.plugin_manager:
            return False

        plugin_instance = self.plugin_manager.get_active_plugin_instance(plugin_name)
        if not plugin_instance:
            return False

        try:
            # Inject service manager reference
            plugin_instance.service_manager = self

            # Inject core services that plugins commonly need
            plugin_instance.project_manager = self.project_manager
            plugin_instance.llm_client = self.llm_client

            return True
        except Exception as e:
            print(f"[ServiceManager] Error injecting services into {plugin_name}: {e}")
            return False

    def inject_services_into_all_compatible_plugins(self):
        """Inject services into all compatible active plugins."""
        if not self.plugin_manager:
            return

        injected_count = 0
        for plugin_name, plugin_info in self.plugin_manager.get_all_plugin_status().items():
            if plugin_info.get("state") in ["loaded", "started"]:
                if self.inject_services_into_plugin(plugin_name):
                    injected_count += 1

        if injected_count > 0:
            print(f"[ServiceManager] Injected services into {injected_count} compatible plugins")

    def initialize_services(self, code_viewer=None):
        """
        Initialize all services.

        Args:
            code_viewer: CodeViewer instance needed by TerminalService
        """
        print("[ServiceManager] Initializing services...")

        # --- Micro-agents (no dependencies) ---
        self.project_indexer_service = ProjectIndexerService()
        self.import_fixer_service = ImportFixerService()

        # NEW: Coordination components (depend on service manager)
        self.context_manager = ContextManager(self)
        self.dependency_planner = DependencyPlanner(self)
        self.integration_validator = IntegrationValidator(self)
        print("[ServiceManager] Coordination components initialized")

        # RAG Manager (no dependencies on other services)
        self.rag_manager = RAGManager(self.event_bus)

        # Set project manager reference for RAG operations
        if self.project_manager:
            self.rag_manager.set_project_manager(self.project_manager)

        # NEW: Generation coordinator (depends on coordination components)
        self.generation_coordinator = GenerationCoordinator(
            self, self.event_bus, self.context_manager,
            self.dependency_planner, self.integration_validator
        )

        # Architect Service (now depends on coordination components)
        self.architect_service = ArchitectService(
            self,  # Pass self (the service manager)
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

        # Inject services into any plugins that need them
        if self._service_injection_enabled:
            self.inject_services_into_all_compatible_plugins()

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

    def get_active_plugin_instance(self, plugin_name: str) -> Optional['PluginBase']:
        """
        Safely retrieves an active plugin instance by name from the PluginManager.
        This allows services to interact with plugins without direct dependencies.

        Args:
            plugin_name: The name of the plugin to retrieve.

        Returns:
            The plugin instance if it is active (loaded/started), otherwise None.
        """
        if self.plugin_manager:
            return self.plugin_manager.get_active_plugin_instance(plugin_name)
        return None

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

    # Micro-agent getters
    def get_project_indexer_service(self) -> ProjectIndexerService:
        """Get the project indexer service instance."""
        return self.project_indexer_service

    def get_import_fixer_service(self) -> ImportFixerService:
        """Get the import fixer service instance."""
        return self.import_fixer_service

    # NEW: Coordination component getters
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

    def is_fully_initialized(self) -> bool:
        """Check if all services are initialized."""
        return all([
            self.llm_client is not None,
            self.project_manager is not None,
            self.execution_engine is not None,
            self.rag_manager is not None,
            self.architect_service is not None,
            self.reviewer_service is not None,
            self.validation_service is not None,
            self.project_indexer_service is not None,
            self.import_fixer_service is not None,
            # NEW: Check coordination components
            self.context_manager is not None,
            self.dependency_planner is not None,
            self.integration_validator is not None,
            self.generation_coordinator is not None
        ])

    def shutdown(self):
        """Shutdown all services gracefully."""
        print("[ServiceManager] Shutting down services...")

        # Shutdown services in reverse dependency order
        if self.terminal_service:
            # Terminal service doesn't have explicit shutdown
            pass

        if self.validation_service:
            # Validation service doesn't have explicit shutdown
            pass

        if self.reviewer_service:
            # Reviewer service doesn't have explicit shutdown
            pass

        if self.architect_service:
            # Architect service doesn't have explicit shutdown
            pass

        if self.rag_manager:
            # RAG manager doesn't have explicit shutdown
            pass

        # Shutdown coordination components
        if self.generation_coordinator:
            # Generation coordinator doesn't have explicit shutdown
            pass

        # Shutdown plugin system
        if self.plugin_manager:
            asyncio.create_task(self.plugin_manager.shutdown())

        print("[ServiceManager] Services shutdown complete")