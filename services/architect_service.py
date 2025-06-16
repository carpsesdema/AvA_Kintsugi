# services/architect_service.py
# V15: Integrated with GenerationCoordinator for coordinated code generation
# Single Responsibility: AI-driven planning and orchestrated code generation

from __future__ import annotations
import asyncio
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Dict

from core.event_bus import EventBus
from core.llm_client import LLMClient
from core.project_manager import ProjectManager
from prompts.prompts import (
    HIERARCHICAL_PLANNER_PROMPT,
    CODER_PROMPT
)
from services.rag_service import RAGService
from services.project_indexer_service import ProjectIndexerService
from services.import_fixer_service import ImportFixerService
from services.generation_coordinator import GenerationCoordinator
from services.context_manager import ContextManager
from services.dependency_planner import DependencyPlanner
from services.integration_validator import IntegrationValidator

if TYPE_CHECKING:
    from core.managers.service_manager import ServiceManager


class ArchitectService:
    """
    Handles AI-driven planning and coordinated code generation.
    """

    def __init__(self, service_manager: 'ServiceManager', event_bus: EventBus,
                 llm_client: LLMClient, project_manager: ProjectManager,
                 rag_service: RAGService, project_indexer: ProjectIndexerService,
                 import_fixer: ImportFixerService):
        self.service_manager = service_manager
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.project_manager = project_manager
        self.rag_service = rag_service
        self.project_indexer = project_indexer
        self.import_fixer = import_fixer

        # The Architect now owns the full generation pipeline coordination
        self.context_manager = ContextManager(service_manager)
        self.dependency_planner = DependencyPlanner(service_manager)
        self.integration_validator = IntegrationValidator(service_manager)
        self.generation_coordinator = GenerationCoordinator(
            service_manager, event_bus, self.context_manager,
            self.dependency_planner, self.integration_validator
        )

    async def generate_or_modify(self, prompt: str, existing_files: dict | None) -> bool:
        """Determines whether to start a new project or modify an existing one."""
        self.log("info", f"Task received: '{prompt}'")
        success = False

        if not existing_files:
            # 1. Get RAG context for the initial plan
            rag_context = await self.rag_service.query(prompt)

            # 2. Generate the high-level plan
            plan = await self._generate_hierarchical_plan(prompt, rag_context)

            # 3. Execute the unified generation process
            if plan:
                success = await self._execute_coordinated_generation(plan, rag_context)
        else:
            self.log("info", "Modification of existing project is not fully implemented yet.")
            success = False

        if success:
            self.log("success", "Code generation complete.")
        else:
            self.handle_error("coder", "Code generation failed.")
        return success

    async def _generate_hierarchical_plan(self, prompt: str, rag_context: str) -> dict | None:
        """Generates a structured, multi-file plan for a new project."""
        self.log("info", "Designing project structure...")

        plan_prompt = HIERARCHICAL_PLANNER_PROMPT.format(prompt=prompt, rag_context=rag_context)

        provider, model = self.llm_client.get_model_for_role("architect")
        if not provider or not model:
            self.handle_error("architect", "No model configured.")
            return None

        raw_plan_response = ""
        try:
            async for chunk in self.llm_client.stream_chat(provider, model, plan_prompt, "architect"):
                raw_plan_response += chunk
            plan = self._parse_json_response(raw_plan_response)
            if not plan.get("files"):
                raise ValueError("AI did not return a valid file plan.")
            self.log("success", f"Plan created: {len(plan['files'])} file(s).")
            return plan
        except (json.JSONDecodeError, ValueError) as e:
            self.handle_error("architect", f"Hierarchical plan creation failed: {e}", raw_plan_response)
            return None
        except Exception as e:
            self.handle_error("architect", f"An unexpected error occurred during planning: {e}", raw_plan_response)
            return None

    async def _execute_coordinated_generation(self, plan: dict, rag_context: str) -> bool:
        """
        Executes the entire generation process using the unified GenerationCoordinator.
        This is the core of the performance fix.
        """
        try:
            files_to_generate = plan.get("files", [])
            project_root = self.project_manager.active_project_path

            # Prepare UI and file structure
            all_filenames = [f['filename'] for f in files_to_generate]
            self.event_bus.emit("prepare_for_generation", all_filenames, str(project_root))
            await self._create_package_structure(files_to_generate)
            await asyncio.sleep(0.1)  # Give UI time to update

            self.log("info", "Handing off to unified Generation Coordinator...")

            # --- THE UNIFIED CALL ---
            # The GenerationCoordinator now handles ALL file types.
            # We pass the full plan and context to it. No more special loops here.
            generated_files = await self.generation_coordinator.coordinate_generation(plan, rag_context)

            if not generated_files or len(generated_files) != len(all_filenames):
                self.log("error",
                         f"Generation failed. Expected {len(all_filenames)} files, but got {len(generated_files)}.")
                return False

            # Save and commit all generated files at once
            self.log("success", "Unified generation complete. Saving all files...")
            self.project_manager.save_and_commit_files(generated_files, "feat: initial coordinated project generation")
            self.log("success", "Project foundation committed successfully.")

            self.event_bus.emit("code_generation_complete", generated_files)
            return True

        except Exception as e:
            self.handle_error("coder", f"Coordinated generation failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def _create_package_structure(self, files: list):
        """Ensures that all necessary __init__.py files are created for packages."""
        project_root = self.project_manager.active_project_path
        if not project_root: return

        dirs_that_need_init = {Path(f['filename']).parent for f in files if '/' in f['filename']}
        init_files_to_create = {}

        for d in dirs_that_need_init:
            init_path = d / "__init__.py"
            # Check if an __init__.py is already planned for this directory
            is_planned = any(f['filename'] == str(init_path).replace('\\', '/') for f in files)
            # Check if it already exists on disk (e.g., from a previous run)
            exists_on_disk = (project_root / init_path).exists()

            if not is_planned and not exists_on_disk:
                init_files_to_create[str(init_path).replace('\\', '/')] = "# This file makes this a Python package\n"

        if init_files_to_create:
            self.log("info", f"Creating missing __init__.py files: {list(init_files_to_create.keys())}")
            self.project_manager.save_and_commit_files(init_files_to_create, "chore: add package markers")
            await asyncio.sleep(0.1)

    def _parse_json_response(self, response: str) -> dict:
        """Extracts a JSON object from a string, tolerating surrounding text."""
        cleaned_response = self._clean_json_output(response)
        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to decode JSON after cleaning. Error: {e}. Cleaned response: '{cleaned_response[:200]}...'")

    def _clean_json_output(self, response: str) -> str:
        """Cleans AI response to extract only the JSON part."""
        response = response.strip()
        # Find the first '{' and the last '}'
        start = response.find('{')
        end = response.rfind('}')
        if start != -1 and end != -1 and end > start:
            return response[start:end + 1]
        raise ValueError("No valid JSON object found in AI's response.")

    def handle_error(self, agent: str, error_msg: str, response: str = ""):
        self.log("error", f"{agent} failed: {error_msg}\nResponse: {response}")
        self.event_bus.emit("ai_response_ready", f"Sorry, the {agent} failed.")

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "ArchitectService", level, message)