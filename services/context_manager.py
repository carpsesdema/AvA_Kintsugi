# services/context_manager.py
# Manages and distributes context across file generation
# Single Responsibility: Context coordination and distribution

import ast
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass


@dataclass
class GenerationContext:
    """Comprehensive context for coordinated generation."""
    plan: Dict[str, Any]
    project_index: Dict[str, str]
    living_design_context: Dict[str, Any]
    dependency_order: List[str]
    generation_session: Dict[str, Any]  # Track what's being generated in this session
    # --- THIS IS THE FIX ---
    # Add a field to hold the RAG context for the entire session.
    rag_context: str


class ContextManager:
    """
    Manages comprehensive context for coordinated generation.

    Single Responsibility: Build, maintain, and distribute context
    information across the generation process.
    """

    def __init__(self, service_manager):
        self.service_manager = service_manager

    # --- THIS IS THE FIX ---
    # The method now accepts rag_context to include in the generation context.
    async def build_generation_context(self, plan: Dict[str, Any], rag_context: str) -> GenerationContext:
        """Build comprehensive context for the entire generation session."""
        # Get project indexer and build current index
        project_indexer = self.service_manager.get_project_indexer_service()
        project_manager = self.service_manager.get_project_manager()
        project_index = project_indexer.build_index(project_manager.active_project_path)

        # Get living design context
        living_design_agent = self.service_manager.get_active_plugin_instance("living_design_agent")
        living_design_context = {}
        if living_design_agent and hasattr(living_design_agent, 'get_current_documentation'):
            living_design_context = living_design_agent.get_current_documentation()

        # Build session context - what files are being generated and their purposes
        generation_session = {}
        for file_info in plan.get("files", []):
            generation_session[file_info["filename"]] = {
                "purpose": file_info["purpose"],
                "status": "planned"
            }

        return GenerationContext(
            plan=plan,
            project_index=project_index,
            living_design_context=living_design_context,
            dependency_order=[],  # Will be filled by DependencyPlanner
            generation_session=generation_session,
            rag_context=rag_context # Store the RAG context
        )

    def update_session_context(self, context: GenerationContext,
                               generated_files: Dict[str, str]) -> GenerationContext:
        """Update context with newly generated files in this session."""
        # Update session tracking
        for filename in generated_files:
            if filename in context.generation_session:
                context.generation_session[filename]["status"] = "generated"
                context.generation_session[filename]["interfaces"] = self._extract_interfaces(
                    generated_files[filename]
                )

        return context

    def _extract_interfaces(self, code: str) -> Dict[str, Any]:
        """Extract class and function interfaces from generated code."""
        try:
            tree = ast.parse(code)
            interfaces = {"classes": [], "functions": []}

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    interfaces["classes"].append({
                        "name": node.name,
                        "methods": [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
                    })
                elif isinstance(node, ast.FunctionDef) and not hasattr(node, 'parent'):
                    interfaces["functions"].append(node.name)

            return interfaces
        except Exception:
            return {"classes": [], "functions": []}