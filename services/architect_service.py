# kintsugi_ava/services/architect_service.py
# UPDATED: Now intelligently detects the source root to prevent path ambiguity.

from __future__ import annotations
import asyncio
import json
import re
import os
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from core.event_bus import EventBus
from core.llm_client import LLMClient
from core.project_manager import ProjectManager
from prompts.prompts import (
    HIERARCHICAL_PLANNER_PROMPT,
    MODIFICATION_PLANNER_PROMPT,
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
        self.context_manager = ContextManager(service_manager)
        self.dependency_planner = DependencyPlanner(service_manager)
        self.integration_validator = IntegrationValidator(service_manager)
        self.generation_coordinator = GenerationCoordinator(
            service_manager, event_bus, self.context_manager,
            self.dependency_planner, self.integration_validator
        )

    async def generate_or_modify(self, prompt: str, existing_files: dict | None) -> bool:
        self.log("info", f"Task received: '{prompt}'")
        plan = None
        rag_context = await self.rag_service.query(prompt)

        if not existing_files:
            self.log("info", "No existing project detected. Generating new project plan...")
            plan = await self._generate_hierarchical_plan(prompt, rag_context)
        else:
            self.log("info", "Existing project detected. Generating modification plan...")
            plan = await self._generate_modification_plan(prompt, existing_files)

        if plan:
            success = await self._execute_coordinated_generation(plan, rag_context)
        else:
            self.log("error", "Failed to generate a valid plan. Aborting generation.")
            success = False

        if success:
            self.log("success", "Code generation complete.")
        else:
            self.handle_error("coder", "Code generation failed.")
        return success

    # --- NEW: Helper to find the common source directory ---
    def _determine_source_root(self, file_paths: List[str]) -> Optional[str]:
        """
        Determines the common source directory for a list of file paths.
        This is crucial for projects where source code is in a sub-folder (e.g., 'src/', 'my_app/').
        """
        if not file_paths:
            return None

        paths = [Path(p) for p in file_paths if p.endswith('.py')]
        if not paths:
            return None

        # Find the common ancestor directory of all Python files.
        common_path = Path(os.path.commonpath([str(p) for p in paths]))

        # If the common path is just the root, there's no dedicated source folder.
        if str(common_path) == '.':
            return None

        # If the common path is a directory, it's likely our source root.
        if common_path.name:
            return common_path.as_posix()

        return None

    # --- UPDATED to use the new source root logic ---
    def _format_files_for_prompt(self, files: Dict[str, str]) -> tuple[str, Optional[str]]:
        """
        Formats the file dictionary and determines the source root.
        Returns a tuple: (formatted_string, source_root_or_none).
        """
        if not files:
            return "No existing files in the project.", None

        source_root = self._determine_source_root(list(files.keys()))

        output = []
        for filename, content in sorted(files.items()):
            lang = ""
            if filename.endswith(".py"):
                lang = "python"
            elif filename.endswith(".html"):
                lang = "html"
            elif filename.endswith(".css"):
                lang = "css"
            else:
                lang = "plaintext"

            output.append(f"### File: `{filename}`\n```{lang}\n{content}\n```")

        return "\n\n".join(output), source_root

    async def _generate_modification_plan(self, prompt: str, existing_files: dict) -> dict | None:
        self.log("info", "Analyzing existing files to create a modification plan...")
        try:
            file_context_string, source_root = self._format_files_for_prompt(existing_files)

            plan_prompt = MODIFICATION_PLANNER_PROMPT.format(
                prompt=prompt,
                file_context_string=file_context_string,
                # Provide the source root if detected, otherwise a clear message.
                source_root_info=f"The primary Python package for this project seems to be in the '{source_root}' directory. All new Python files should respect this structure." if source_root else "This project appears to have its source files in the root directory."
            )

            plan = await self._get_plan_from_llm(plan_prompt)

            if not plan or not isinstance(plan.get("files"), list):
                self.log("error", "The AI's modification plan was invalid or missing the 'files' list.")
                return None
            try:
                # This is the line that caused the original error.
                # Now it's wrapped in a try/except to handle malformed entries.
                planned_filenames = {f['filename'] for f in plan.get('files', [])}
            except KeyError:
                self.log("error", "The AI's modification plan contained an entry without a 'filename' key. Aborting.")
                self.event_bus.emit("ai_response_ready", "Sorry, the AI generated an invalid modification plan. Please try again.")
                return None
            is_creating_new_main = "main.py" in planned_filenames and "main.py" not in existing_files
            is_creating_new_config = "config.py" in planned_filenames and "config.py" not in existing_files
            if is_creating_new_main or is_creating_new_config:
                error_msg = "AI attempted to re-architect the project by creating a new entry point or config. Aborting."
                self.log("error", error_msg)
                self.event_bus.emit("ai_response_ready",
                                    "The AI proposed an invalid change that would break the project structure. I've stopped it. Please try rephrasing your request.")
                return None
            return plan
        except Exception as e:
            self.handle_error("architect", f"An unexpected error during modification planning: {e}")
            import traceback
            traceback.print_exc()
            return None

    # --- Other methods remain largely the same ---

    async def _generate_hierarchical_plan(self, prompt: str, rag_context: str) -> dict | None:
        self.log("info", "Designing project structure...")
        plan_prompt = HIERARCHICAL_PLANNER_PROMPT.format(prompt=prompt, rag_context=rag_context)
        return await self._get_plan_from_llm(plan_prompt)

    async def _get_plan_from_llm(self, plan_prompt: str) -> dict | None:
        provider, model = self.llm_client.get_model_for_role("architect")
        if not provider or not model:
            self.handle_error("architect", "No model configured for architect role.")
            return None

        raw_plan_response = ""
        try:
            async for chunk in self.llm_client.stream_chat(provider, model, plan_prompt, "architect"):
                raw_plan_response += chunk
            plan = self._parse_json_response(raw_plan_response)
            if not plan or not plan.get("files"):
                raise ValueError("AI did not return a valid file plan in JSON format.")
            self.log("success", f"Plan created: {len(plan['files'])} file(s).")
            return plan
        except (json.JSONDecodeError, ValueError) as e:
            self.handle_error("architect", f"Plan creation failed: {e}", raw_plan_response)
            return None
        except Exception as e:
            self.handle_error("architect", f"An unexpected error during planning: {e}", raw_plan_response)
            return None

    async def _execute_coordinated_generation(self, plan: dict, rag_context: str) -> bool:
        try:
            files_to_generate = plan.get("files", [])
            project_root = self.project_manager.active_project_path
            all_filenames = [f['filename'] for f in files_to_generate]
            self.event_bus.emit("prepare_for_generation", all_filenames, str(project_root))
            await self._create_package_structure(files_to_generate)
            await asyncio.sleep(0.1)
            self.log("info", "Handing off to unified Generation Coordinator...")
            generated_files = await self.generation_coordinator.coordinate_generation(plan, rag_context)
            if not generated_files or len(generated_files) < len(all_filenames):
                self.log("error",
                         f"Generation failed. Expected {len(all_filenames)} files, but got {len(generated_files)}.")
                return False
            commit_message = f"feat: AI-driven changes for '{plan['files'][0]['purpose'][:50]}...'"
            self.project_manager.save_and_commit_files(generated_files, commit_message)
            self.log("success", "Project changes committed successfully.")
            self.event_bus.emit("code_generation_complete", generated_files)
            return True
        except Exception as e:
            self.handle_error("coder", f"Coordinated generation failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def _create_package_structure(self, files: list):
        project_root = self.project_manager.active_project_path
        if not project_root: return
        dirs_that_need_init = {Path(f['filename']).parent for f in files if '/' in f['filename']}
        init_files_to_create = {}
        for d in dirs_that_need_init:
            init_path = d / "__init__.py"
            is_planned = any(f['filename'] == str(init_path).replace('\\', '/') for f in files)
            exists_on_disk = (project_root / init_path).exists()
            if not is_planned and not exists_on_disk:
                init_files_to_create[str(init_path).replace('\\', '/')] = "# This file makes this a Python package\n"
        if init_files_to_create:
            self.log("info", f"Creating missing __init__.py files: {list(init_files_to_create.keys())}")
            self.project_manager.save_and_commit_files(init_files_to_create, "chore: add package markers")
            await asyncio.sleep(0.1)

    def _parse_json_response(self, response: str) -> dict:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in the response.")
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to decode JSON. Error: {e}. Content: '{match.group(0)[:200]}...'")

    def handle_error(self, agent: str, error_msg: str, response: str = ""):
        self.log("error", f"{agent} failed: {error_msg}\nResponse: {response}")
        self.event_bus.emit("ai_response_ready", f"Sorry, the {agent} failed.")

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "ArchitectService", level, message)