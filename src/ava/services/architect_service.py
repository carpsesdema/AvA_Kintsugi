# src/ava/services/architect_service.py
from __future__ import annotations
import asyncio
import json
import re
import os
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from src.ava.core.event_bus import EventBus
from src.ava.core.llm_client import LLMClient
from src.ava.core.project_manager import ProjectManager
from src.ava.prompts.prompts import (
    HIERARCHICAL_PLANNER_PROMPT,
    MODIFICATION_PLANNER_PROMPT
)
from src.ava.services.rag_service import RAGService
from src.ava.services.project_indexer_service import ProjectIndexerService
from src.ava.services.import_fixer_service import ImportFixerService
from src.ava.services.generation_coordinator import GenerationCoordinator
from src.ava.services.context_manager import ContextManager
from src.ava.services.dependency_planner import DependencyPlanner
from src.ava.services.integration_validator import IntegrationValidator
from src.ava.utils.code_summarizer import CodeSummarizer

if TYPE_CHECKING:
    from src.ava.core.managers import ServiceManager


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

    async def _get_combined_rag_context(self, prompt: str) -> str:
        """Queries both project and global RAG and combines them."""
        project_rag_context = await self.rag_service.query(prompt, target_collection="project")
        global_rag_context = await self.rag_service.query(prompt, target_collection="global")

        # Filter out "not found" or "unreachable" messages to avoid cluttering the LLM prompt
        valid_project_context = project_rag_context if "no relevant documents found" not in project_rag_context.lower() and "not running or is unreachable" not in project_rag_context.lower() else ""
        valid_global_context = global_rag_context if "no relevant documents found" not in global_rag_context.lower() and "not running or is unreachable" not in global_rag_context.lower() else ""

        combined_context_parts = []
        if valid_project_context:
            combined_context_parts.append(
                f"PROJECT-SPECIFIC CONTEXT (e.g., GDD, existing project files):\n{valid_project_context}")
        if valid_global_context:
            combined_context_parts.append(
                f"GENERAL PYTHON EXAMPLES & BEST PRACTICES (GLOBAL CONTEXT):\n{valid_global_context}")

        if not combined_context_parts:
            return "No specific RAG context found for this query."

        return "\n\n---\n\n".join(combined_context_parts)

    async def generate_or_modify(self, prompt: str, existing_files: dict | None) -> bool:
        self.log("info", f"Architect task received: '{prompt}'")
        plan = None

        self.log("info", "Fetching combined RAG context (project & global)...")
        combined_rag_context = await self._get_combined_rag_context(prompt)
        self.log("info", f"Combined RAG context length: {len(combined_rag_context)} chars.")

        if not existing_files:
            self.log("info", "No existing project detected. Generating new project plan...")
            plan = await self._generate_hierarchical_plan(prompt, combined_rag_context)
        else:
            self.log("info", "Existing project detected. Generating modification plan...")
            plan = await self._generate_modification_plan(prompt, existing_files,
                                                          combined_rag_context)  # Pass combined_rag_context here too

        if plan:
            # Pass combined_rag_context to the coordinator as well, it might use it for initial context building.
            success = await self._execute_coordinated_generation(plan, combined_rag_context, existing_files)
        else:
            self.log("error", "Failed to generate a valid plan. Aborting generation.")
            success = False

        if success:
            self.log("success", "Code generation complete.")
        else:
            self.handle_error("coder", "Code generation failed.")
        return success

    def _find_relevant_files(self, prompt: str, existing_files: Dict[str, str], top_n: int = 4) -> List[str]:
        """
        Finds the most relevant files from the existing project to the user's prompt.
        This is a simple but effective keyword-based relevance scoring.
        """
        prompt_keywords = set(re.findall(r'\b\w+\b', prompt.lower()))
        if not prompt_keywords:
            return list(existing_files.keys())[:top_n]

        scored_files = []
        for filename, content in existing_files.items():
            score = 0
            # Heavily weight matches in the filename
            if any(keyword in filename.lower() for keyword in prompt_keywords):
                score += 10
            # Score based on keyword count in content
            content_lower = content.lower()
            for keyword in prompt_keywords:
                score += content_lower.count(keyword)
            scored_files.append((score, filename))

        scored_files.sort(key=lambda x: x[0], reverse=True)

        relevant_set = {filename for score, filename in scored_files[:top_n]}
        if 'main.py' in existing_files:
            relevant_set.add('main.py')
        return list(relevant_set)

    async def _generate_modification_plan(self, prompt: str, existing_files: dict,
                                          rag_context: str) -> dict | None:  # Added rag_context
        self.log("info", "Analyzing existing files to create a modification plan...")
        try:
            relevant_filenames = self._find_relevant_files(prompt, existing_files)
            self.log("info", f"Identified most relevant files for full code context: {relevant_filenames}")

            full_code_context_list = []
            summaries_context_list = []

            for filename, content in sorted(existing_files.items()):
                if filename in relevant_filenames:
                    full_code_context_list.append(f"--- File: {filename} ---\n```python\n{content}\n```")
                else:
                    summary = CodeSummarizer(content).summarize() if filename.endswith('.py') else "// Non-Python file"
                    summaries_context_list.append(f"### File: `{filename}`\n```\n{summary}\n```")

            full_code_context_str = "\n\n".join(full_code_context_list)
            summaries_context_str = "\n\n".join(summaries_context_list)

            # Include RAG context in the modification planner prompt if it exists
            # The MODIFICATION_PLANNER_PROMPT doesn't have a placeholder for rag_context yet.
            # We might need to adjust the prompt or append rag_context to the user's prompt.
            # For now, let's assume the main `prompt` to the LLM might already be enhanced by the user if they used RAG.
            # Or, we can add it to the "CONTEXT ON EXISTING PROJECT" section.
            # Let's add it to the main prompt for now for simplicity.
            enhanced_prompt_for_llm = f"{prompt}\n\nADDITIONAL CONTEXT FROM KNOWLEDGE BASE:\n{rag_context}"

            plan_prompt = MODIFICATION_PLANNER_PROMPT.format(
                prompt=enhanced_prompt_for_llm,  # Use the enhanced prompt
                full_code_context=full_code_context_str,
                file_summaries_string=summaries_context_str
            )

            plan = await self._get_plan_from_llm(plan_prompt)

            if plan:
                plan = self._sanitize_plan_paths(plan)

            if not plan or not isinstance(plan.get("files"), list):
                self.log("error", "The AI's modification plan was invalid or missing the 'files' list.")
                return None
            return plan
        except Exception as e:
            self.handle_error("architect", f"An unexpected error during modification planning: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _sanitize_plan_paths(self, plan: dict) -> dict:
        if not plan or 'files' not in plan: return plan
        sanitized_files = []
        for file_entry in plan.get('files', []):
            original_filename_str = file_entry.get('filename')
            if not original_filename_str: continue
            p = Path(original_filename_str.replace('\\', '/'))
            parts = p.parts
            if len(parts) > 1 and parts[0] == parts[1]:
                corrected_path = Path(*parts[1:])
                corrected_path_str = corrected_path.as_posix()
                self.log("warning",
                         f"FIXED DUPLICATE PATH: Corrected '{original_filename_str}' to '{corrected_path_str}'")
                file_entry['filename'] = corrected_path_str
            sanitized_files.append(file_entry)
        plan['files'] = sanitized_files
        return plan

    async def _generate_hierarchical_plan(self, prompt: str, rag_context: str) -> dict | None:
        self.log("info", "Designing project structure...")
        # HIERARCHICAL_PLANNER_PROMPT already has {rag_context} placeholder
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

    async def _execute_coordinated_generation(self, plan: dict, rag_context: str,
                                              existing_files: Optional[Dict[str, str]]) -> bool:
        try:
            is_modification = existing_files is not None
            files_to_generate = plan.get("files", [])
            project_root = self.project_manager.active_project_path
            all_filenames = [f['filename'] for f in files_to_generate]
            self.event_bus.emit("prepare_for_generation", all_filenames, str(project_root), is_modification)
            await self._create_package_structure(files_to_generate)
            await asyncio.sleep(0.1)
            self.log("info", "Handing off to unified Generation Coordinator...")
            # GenerationCoordinator will use the combined rag_context passed here for its initial context build
            generated_files = await self.generation_coordinator.coordinate_generation(plan, rag_context, existing_files)
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
        dirs_that_need_init = {Path(f['filename']).parent for f in files if
                               '/' in f['filename'] or '\\' in f['filename']}
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