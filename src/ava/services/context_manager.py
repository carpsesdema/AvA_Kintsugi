# src/ava/services/context_manager.py
import ast
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass


@dataclass
class GenerationContext:
    """Comprehensive context for coordinated generation."""
    plan: Dict[str, Any]
    # THIS IS THE CHANGE: project_index is now a dict of {filepath: summary}
    project_index: Dict[str, str]
    living_design_context: Dict[str, Any]
    dependency_order: List[str]
    generation_session: Dict[str, Any]  # Tracks files in current generation, their status, and their generated code
    rag_context: str
    relevance_scores: Dict[str, float]
    existing_files: Optional[Dict[str, str]]  # Files on disk *before* this session started


class ContextManager:
    """
    Manages comprehensive context for coordinated generation.
    """

    def __init__(self, service_manager):
        self.service_manager = service_manager

    async def build_generation_context(self, plan: Dict[str, Any], rag_context: str,
                                       existing_files: Optional[Dict[str, str]]) -> GenerationContext:
        project_indexer = self.service_manager.get_project_indexer_service()
        project_manager = self.service_manager.get_project_manager()

        # THIS IS THE CHANGE: Build a structural summary for the entire project.
        project_structure_summary = {}
        if project_manager and project_manager.active_project_path:
            project_structure_summary = project_indexer.build_index(project_manager.active_project_path)

        living_design_context = {}  # Placeholder for now

        generation_session = {}
        for file_info in plan.get("files", []):
            generation_session[file_info["filename"]] = {
                "purpose": file_info["purpose"],
                "status": "planned",
                "dependencies": self._extract_file_dependencies(file_info)
            }

        relevance_scores = self._calculate_relevance_scores(plan, project_structure_summary, rag_context)

        return GenerationContext(
            plan=plan,
            project_index=project_structure_summary, # This now holds the rich summaries
            living_design_context=living_design_context,
            dependency_order=[],
            generation_session=generation_session,
            rag_context=rag_context,
            relevance_scores=relevance_scores,
            existing_files=existing_files or {}
        )

    async def update_session_context(self, context: GenerationContext,
                                     newly_generated_file: Dict[str, str]) -> GenerationContext:
        """
        Update the context with a newly generated file, including its structural summary.
        This is the core of the "rolling context".
        """
        try:
            filename, code = list(newly_generated_file.items())[0]

            if filename in context.generation_session:
                context.generation_session[filename]["status"] = "completed"
                context.generation_session[filename]["generated_code"] = code

            # THIS IS THE CHANGE: Update the project_index with the summary of the new code.
            project_indexer = self.service_manager.get_project_indexer_service()
            updated_index = context.project_index.copy()
            if filename.endswith('.py'):
                summary = project_indexer.get_summary_from_content(code)
                updated_index[filename] = summary
                print(f"[ContextManager] Updated structural summary for new file: {filename}")

            return GenerationContext(
                plan=context.plan,
                project_index=updated_index,
                living_design_context=context.living_design_context,
                dependency_order=context.dependency_order,
                generation_session=context.generation_session,
                rag_context=context.rag_context,
                relevance_scores=context.relevance_scores,
                existing_files=context.existing_files
            )

        except Exception as e:
            print(f"Error updating session context for {list(newly_generated_file.keys())[0]}: {e}")
            import traceback
            traceback.print_exc()
            return context

    def _extract_file_dependencies(self, file_info: Dict[str, str]) -> List[str]:
        try:
            dependencies = []
            purpose = file_info.get("purpose", "").lower()
            filename = file_info.get("filename", "").lower()
            dependency_patterns = {
                "async": ["asyncio"], "path": ["pathlib"], "json": ["json"], "typing": ["typing"],
                "service": ["ava.core.event_bus"], "manager": ["pathlib", "typing"],
                "ui": ["tkinter", "PySide6"], "web": ["flask", "fastapi"],
                "database": ["sqlite3", "sqlalchemy"], "api": ["requests", "aiohttp"]
            }
            for keyword, deps in dependency_patterns.items():
                if keyword in purpose or keyword in filename:
                    dependencies.extend(deps)
            return list(set(dependencies))
        except Exception:
            return []

    def _calculate_relevance_scores(self, plan: Dict[str, Any],
                                    project_index: Dict[str, str],
                                    rag_context: str) -> Dict[str, float]:
        try:
            relevance_scores = {}
            plan_keywords = self._extract_keywords_from_plan(plan)
            for filepath, summary in project_index.items():
                score = self._calculate_text_relevance(summary, plan_keywords)
                relevance_scores[f"project_index:{filepath}"] = score
            if rag_context:
                rag_chunks = rag_context.split("--- Relevant Document Snippet")
                for i, chunk in enumerate(rag_chunks):
                    if chunk.strip():
                        score = self._calculate_text_relevance(chunk, plan_keywords)
                        relevance_scores[f"rag_chunk:{i}"] = score
            return relevance_scores
        except Exception:
            return {}

    def _extract_keywords_from_plan(self, plan: Dict[str, Any]) -> Set[str]:
        try:
            keywords = set()
            for file_info in plan.get("files", []):
                purpose = file_info.get("purpose", "")
                filename = file_info.get("filename", "")
                purpose_words = [word.strip().lower() for word in purpose.split()
                                 if len(word) > 3 and word.isalpha()]
                filename_words = [word.strip().lower() for word in filename.replace('.py', '').replace('_', ' ').split()
                                  if len(word) > 3 and word.isalpha()]
                keywords.update(purpose_words)
                keywords.update(filename_words)
            for dep in plan.get("dependencies", []):
                if isinstance(dep, str):
                    keywords.add(dep.lower())
            return keywords
        except Exception:
            return set()

    def _calculate_text_relevance(self, text: str, keywords: Set[str]) -> float:
        try:
            if not text or not keywords: return 0.0
            text_lower = text.lower()
            matches = sum(1 for keyword in keywords if keyword in text_lower)
            text_words = len(text.split())
            keyword_count = len(keywords)
            if text_words == 0 or keyword_count == 0: return 0.0
            base_score = matches / keyword_count
            length_weight = min(1.0, text_words / 100)
            return base_score * length_weight
        except Exception:
            return 0.0