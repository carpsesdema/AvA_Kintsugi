# src/ava/services/context_manager.py
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
    generation_session: Dict[str, Any]
    rag_context: str
    relevance_scores: Dict[str, float]  # Track relevance of context items
    existing_files: Optional[Dict[str, str]]


class ContextManager:
    """
    Manages comprehensive context for coordinated generation.

    Single Responsibility: Build, maintain, and distribute context
    information across the generation process with intelligent filtering.
    """

    def __init__(self, service_manager):
        self.service_manager = service_manager

    async def build_generation_context(self, plan: Dict[str, Any], rag_context: str, existing_files: Optional[Dict[str, str]]) -> GenerationContext:
        """Build comprehensive context for the entire generation session with intelligent filtering."""
        try:
            # Get project indexer and build current index
            project_indexer = self.service_manager.get_project_indexer_service()
            project_manager = self.service_manager.get_project_manager()

            if project_manager and project_manager.active_project_path:
                project_index = project_indexer.build_index(project_manager.active_project_path)
            else:
                project_index = {}

            # Get living design context with error handling
            living_design_context = {}
            try:
                plugin_manager = self.service_manager.get_plugin_manager()
                if plugin_manager:
                    living_design_agent = plugin_manager.get_active_plugin_instance("living_design_agent")
                    if living_design_agent and hasattr(living_design_agent, 'get_current_documentation'):
                        living_design_context = living_design_agent.get_current_documentation() or {}
            except Exception as e:
                print(f"Warning: Could not get living design context: {e}")

            # Build session context - what files are being generated and their purposes
            generation_session = {}
            for file_info in plan.get("files", []):
                generation_session[file_info["filename"]] = {
                    "purpose": file_info["purpose"],
                    "status": "planned",
                    "dependencies": self._extract_file_dependencies(file_info)
                }

            # Calculate relevance scores for context items
            relevance_scores = self._calculate_relevance_scores(plan, project_index, rag_context)

            return GenerationContext(
                plan=plan,
                project_index=project_index,
                living_design_context=living_design_context,
                dependency_order=[],  # Will be filled by DependencyPlanner
                generation_session=generation_session,
                rag_context=rag_context,
                relevance_scores=relevance_scores,
                existing_files=existing_files or {}
            )

        except Exception as e:
            print(f"Error building generation context: {e}")
            # Return minimal context to prevent total failure
            return GenerationContext(
                plan=plan,
                project_index={},
                living_design_context={},
                dependency_order=[],
                generation_session={},
                rag_context=rag_context,
                relevance_scores={},
                existing_files=existing_files or {}
            )

    def update_session_context(self, context: GenerationContext,
                               generated_files: Dict[str, str]) -> GenerationContext:
        """Update context with newly generated files in this session."""
        try:
            # Update generation session with completed files
            for filename in generated_files:
                if filename in context.generation_session:
                    context.generation_session[filename]["status"] = "completed"
                    context.generation_session[filename]["generated_code"] = generated_files[filename]

            # Update project index with new files
            updated_index = context.project_index.copy()
            for filename, code in generated_files.items():
                if filename.endswith('.py'):
                    module_name = filename.replace('.py', '').replace('/', '.')
                    updated_index[module_name] = self._extract_code_summary(code)

            # Create updated context
            updated_context = GenerationContext(
                plan=context.plan,
                project_index=updated_index,
                living_design_context=context.living_design_context,
                dependency_order=context.dependency_order,
                generation_session=context.generation_session,
                rag_context=context.rag_context,
                relevance_scores=context.relevance_scores,
                existing_files=context.existing_files
            )

            return updated_context

        except Exception as e:
            print(f"Error updating session context: {e}")
            return context

    def get_filtered_context_for_file(self, filename: str, context: GenerationContext) -> Dict[str, Any]:
        """Get filtered, relevant context for a specific file generation."""
        try:
            filtered_context = {}

            # Filter project index to most relevant modules
            relevant_modules = self._get_relevant_modules(filename, context)
            filtered_context["relevant_modules"] = relevant_modules

            # Filter living design context
            relevant_design = self._filter_design_context(filename, context.living_design_context)
            filtered_context["design_context"] = relevant_design

            # Get relevant RAG context
            relevant_rag = self._filter_rag_context(filename, context.rag_context)
            filtered_context["rag_context"] = relevant_rag

            # Get dependency information
            dependencies = self._get_file_dependencies(filename, context)
            filtered_context["dependencies"] = dependencies

            return filtered_context

        except Exception as e:
            print(f"Error filtering context for {filename}: {e}")
            return {}

    def _extract_file_dependencies(self, file_info: Dict[str, str]) -> List[str]:
        """Extract potential dependencies for a file based on its purpose."""
        try:
            dependencies = []
            purpose = file_info.get("purpose", "").lower()
            filename = file_info.get("filename", "").lower()

            # Common dependencies based on keywords
            dependency_patterns = {
                "async": ["asyncio"],
                "path": ["pathlib"],
                "json": ["json"],
                "typing": ["typing"],
                "service": ["ava.core.event_bus"],
                "manager": ["pathlib", "typing"],
                "ui": ["tkinter", "PySide6"],
                "web": ["flask", "fastapi"],
                "database": ["sqlite3", "sqlalchemy"],
                "api": ["requests", "aiohttp"]
            }

            for keyword, deps in dependency_patterns.items():
                if keyword in purpose or keyword in filename:
                    dependencies.extend(deps)

            return list(set(dependencies))  # Remove duplicates

        except Exception:
            return []

    def _calculate_relevance_scores(self, plan: Dict[str, Any],
                                    project_index: Dict[str, str],
                                    rag_context: str) -> Dict[str, float]:
        """Calculate relevance scores for context items."""
        try:
            relevance_scores = {}

            # Get keywords from the plan
            plan_keywords = self._extract_keywords_from_plan(plan)

            # Score project index items
            for module_name, module_content in project_index.items():
                score = self._calculate_text_relevance(module_content, plan_keywords)
                relevance_scores[f"project_index:{module_name}"] = score

            # Score RAG context chunks
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
        """Extract relevant keywords from the generation plan."""
        try:
            keywords = set()

            # Extract from file purposes
            for file_info in plan.get("files", []):
                purpose = file_info.get("purpose", "")
                filename = file_info.get("filename", "")

                # Split and clean keywords
                purpose_words = [word.strip().lower() for word in purpose.split()
                                 if len(word) > 3 and word.isalpha()]
                filename_words = [word.strip().lower() for word in filename.replace('.py', '').replace('_', ' ').split()
                                  if len(word) > 3 and word.isalpha()]

                keywords.update(purpose_words)
                keywords.update(filename_words)

            # Extract from dependencies
            for dep in plan.get("dependencies", []):
                if isinstance(dep, str):
                    keywords.add(dep.lower())

            return keywords

        except Exception:
            return set()

    def _calculate_text_relevance(self, text: str, keywords: Set[str]) -> float:
        """Calculate relevance score for text based on keyword matches."""
        try:
            if not text or not keywords:
                return 0.0

            text_lower = text.lower()
            matches = sum(1 for keyword in keywords if keyword in text_lower)

            # Normalize by text length and keyword count
            text_words = len(text.split())
            keyword_count = len(keywords)

            if text_words == 0 or keyword_count == 0:
                return 0.0

            # Calculate score as percentage of keywords found, weighted by text length
            base_score = matches / keyword_count
            length_weight = min(1.0, text_words / 100)  # Prefer shorter, focused content

            return base_score * length_weight

        except Exception:
            return 0.0

    def _get_relevant_modules(self, filename: str, context: GenerationContext) -> Dict[str, str]:
        """Get the most relevant modules for a specific file."""
        try:
            relevant_modules = {}
            file_stem = Path(filename).stem.lower()

            # Sort modules by relevance score
            scored_modules = []
            for module_name, module_content in context.project_index.items():
                score_key = f"project_index:{module_name}"
                score = context.relevance_scores.get(score_key, 0.0)

                # Boost score if module name is similar to filename
                if file_stem in module_name.lower() or module_name.lower() in file_stem:
                    score += 0.5

                scored_modules.append((score, module_name, module_content))

            # Return top 5 most relevant modules
            scored_modules.sort(reverse=True)
            for score, module_name, module_content in scored_modules[:5]:
                if score > 0.1:  # Only include if somewhat relevant
                    relevant_modules[module_name] = module_content

            return relevant_modules

        except Exception:
            return {}

    def _filter_design_context(self, filename: str, design_context: Dict[str, Any]) -> Dict[str, Any]:
        """Filter design context to items relevant to the specific file."""
        try:
            if not design_context:
                return {}

            filtered_design = {}
            file_stem = Path(filename).stem.lower()

            # Filter classes relevant to this file
            if "classes" in design_context:
                relevant_classes = []
                for class_info in design_context["classes"]:
                    class_file = class_info.get("file", "").lower()
                    class_name = class_info.get("name", "").lower()

                    if (file_stem in class_file or
                            filename.lower() in class_file or
                            file_stem in class_name):
                        relevant_classes.append(class_info)

                if relevant_classes:
                    filtered_design["classes"] = relevant_classes

            # Filter functions relevant to this file
            if "functions" in design_context:
                relevant_functions = []
                for func_info in design_context["functions"]:
                    func_file = func_info.get("file", "").lower()
                    func_name = func_info.get("name", "").lower()

                    if (file_stem in func_file or
                            filename.lower() in func_file or
                            file_stem in func_name):
                        relevant_functions.append(func_info)

                if relevant_functions:
                    filtered_design["functions"] = relevant_functions

            return filtered_design

        except Exception:
            return {}

    def _filter_rag_context(self, filename: str, rag_context: str) -> str:
        """Filter RAG context to most relevant chunks for the file."""
        try:
            if not rag_context:
                return ""

            chunks = rag_context.split("--- Relevant Document Snippet")
            relevant_chunks = []
            file_stem = Path(filename).stem.lower()

            # Find chunks that mention the filename or related concepts
            for chunk in chunks:
                chunk_lower = chunk.lower()
                if (file_stem in chunk_lower or
                        filename.lower() in chunk_lower or
                        any(word in chunk_lower for word in ['class', 'function', 'method', 'import'])):
                    relevant_chunks.append(chunk.strip())

            # If no specific matches, include first 2 chunks
            if not relevant_chunks and chunks:
                relevant_chunks = chunks[:2]

            # Limit total length
            result = "\n\n".join(relevant_chunks)
            if len(result) > 1000:
                result = result[:1000] + "..."

            return result

        except Exception:
            return rag_context[:500] + "..." if len(rag_context) > 500 else rag_context

    def _get_file_dependencies(self, filename: str, context: GenerationContext) -> List[str]:
        """Get dependencies for a specific file."""
        try:
            dependencies = []

            # Get from generation session if available
            if filename in context.generation_session:
                session_deps = context.generation_session[filename].get("dependencies", [])
                dependencies.extend(session_deps)

            # Add dependencies based on other files in the plan
            for file_info in context.plan.get("files", []):
                other_filename = file_info["filename"]
                if other_filename != filename and other_filename.endswith('.py'):
                    # Check if this file should import from the other
                    if self._should_file_import_from(filename, other_filename, context):
                        module_name = other_filename.replace('.py', '').replace('/', '.')
                        dependencies.append(module_name)

            return list(set(dependencies))  # Remove duplicates

        except Exception:
            return []

    def _should_file_import_from(self, current_file: str, other_file: str, context: GenerationContext) -> bool:
        """Determine if current file should import from another file."""
        try:
            # Main file typically imports from everything
            if current_file == "main.py":
                return True

            # Get purposes for comparison
            current_purpose = ""
            other_purpose = ""

            for file_info in context.plan.get("files", []):
                if file_info["filename"] == current_file:
                    current_purpose = file_info["purpose"].lower()
                elif file_info["filename"] == other_file:
                    other_purpose = file_info["purpose"].lower()

            # Check for keyword relationships
            current_words = set(current_purpose.split())
            other_words = set(other_purpose.split())

            # If they share significant keywords, likely related
            if len(current_words.intersection(other_words)) > 1:
                return True

            # Services often import from core modules
            if "service" in current_file.lower() and "core" in other_file.lower():
                return True

            return False

        except Exception:
            return False

    def _extract_code_summary(self, code: str) -> str:
        """Extract a summary of code for indexing."""
        try:
            if not code:
                return ""

            lines = code.split('\n')
            summary_lines = []

            for line in lines:
                stripped = line.strip()
                # Include imports, class definitions, function definitions
                if (stripped.startswith(('import ', 'from ', 'class ', 'def ', 'async def ')) or
                        '=' in stripped and 'def' not in stripped):
                    summary_lines.append(stripped)

                # Limit summary length
                if len(summary_lines) >= 20:
                    break

            return '\n'.join(summary_lines)

        except Exception:
            return code[:200] + "..." if len(code) > 200 else code