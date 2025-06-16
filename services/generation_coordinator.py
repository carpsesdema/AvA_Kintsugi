# services/generation_coordinator.py
# Orchestrates coordinated code generation with cross-file awareness
# Single Responsibility: Coordinate the generation of multiple files as a cohesive system

from __future__ import annotations
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from core.event_bus import EventBus

if TYPE_CHECKING:
    from services.context_manager import GenerationContext, ContextManager
    from services.dependency_planner import FileGenerationSpec, DependencyPlanner
    from services.integration_validator import IntegrationValidator


class GenerationCoordinator:
    """
    Orchestrates coordinated code generation.
    """

    def __init__(self, service_manager, event_bus: EventBus,
                 context_manager: 'ContextManager',
                 dependency_planner: 'DependencyPlanner',
                 integration_validator: 'IntegrationValidator'):
        self.service_manager = service_manager
        self.event_bus = event_bus
        self.context_manager = context_manager
        self.dependency_planner = dependency_planner
        self.integration_validator = integration_validator

    async def coordinate_generation(self, plan: Dict[str, Any], rag_context: str) -> Dict[str, str]:
        """
        Coordinate the generation of all files with full cross-file awareness.
        """
        context = await self.context_manager.build_generation_context(plan, rag_context)
        generation_specs = await self.dependency_planner.plan_generation_order(context)
        return await self._execute_coordinated_generation(generation_specs, context)

    async def _execute_coordinated_generation(self,
                                              generation_specs: List['FileGenerationSpec'],
                                              context: 'GenerationContext') -> Dict[str, str]:
        """Execute generation with real-time coordination and validation."""
        generated_files = {}
        import_fixer = self.service_manager.get_import_fixer_service()

        for spec in generation_specs:
            try:
                spec.context = self.context_manager.update_session_context(
                    spec.context, generated_files
                )

                # Step 1: Generate the code with focused context
                generated_code = await self._generate_coordinated_file(spec)
                if generated_code is None:
                    raise Exception(f"Failed to generate {spec.filename}")

                # Step 2: Use the import fixer as a safety net
                self.event_bus.emit("log_message_received", "ImportFixer", "info",
                                    f"Verifying imports for {spec.filename}...")
                try:
                    fixed_code = import_fixer.fix_imports(
                        code=generated_code,
                        project_index=spec.context.project_index,
                        current_module=spec.filename.replace('.py', '').replace('/', '.')
                    )
                    generated_code = fixed_code
                except Exception as e:
                    self.event_bus.emit("log_message_received", "ImportFixer", "warning",
                                        f"Import fixing failed for {spec.filename}: {e}")

                # Step 3: Validate the complete code
                validation_result = await self.integration_validator.validate_integration(
                    spec.filename, generated_code, generated_files, spec.context
                )

                if not validation_result.is_valid:
                    try:
                        fixed_code = await self.integration_validator.fix_integration_issues(
                            spec.filename, generated_code, validation_result, spec.context
                        )
                        generated_code = fixed_code if fixed_code else generated_code
                    except Exception as e:
                        self.event_bus.emit("log_message_received", "IntegrationValidator", "warning",
                                            f"Integration fixing failed for {spec.filename}: {e}")

                generated_files[spec.filename] = generated_code

                self.event_bus.emit("coordinated_generation_progress", {
                    "filename": spec.filename, "completed": len(generated_files),
                    "total": len(generation_specs), "validation_passed": validation_result.is_valid
                })

            except Exception as e:
                self.event_bus.emit("log_message_received", "GenerationCoordinator", "error",
                                    f"Failed to generate {spec.filename}: {e}")
                # Continue with other files rather than failing completely
                generated_files[spec.filename] = f"# ERROR: Failed to generate {spec.filename}\n# {str(e)}\npass"

        return generated_files

    async def _generate_coordinated_file(self, spec: 'FileGenerationSpec') -> Optional[str]:
        """Generate a single file with focused, relevant context."""
        llm_client = self.service_manager.get_llm_client()
        provider, model = llm_client.get_model_for_role("coder")

        if not provider or not model:
            return None

        prompt = self._build_focused_prompt(spec)

        file_content = ""
        try:
            async for chunk in llm_client.stream_chat(provider, model, prompt, "coder"):
                file_content += chunk
                self.event_bus.emit("stream_code_chunk", spec.filename, chunk)
        except Exception as e:
            self.event_bus.emit("log_message_received", "GenerationCoordinator", "error",
                                f"LLM generation failed for {spec.filename}: {e}")
            return None

        return self._clean_code_output(file_content)

    def _build_focused_prompt(self, spec: 'FileGenerationSpec') -> str:
        """Build a focused prompt with only relevant context."""
        try:
            # Extract relevant context intelligently
            relevant_context = self._extract_relevant_context(spec)
            dependencies = self._extract_file_dependencies(spec)
            examples = self._get_relevant_examples(spec)

            return f"""You are an expert Python developer writing production-ready code.

**FILE TO GENERATE:** `{spec.filename}`
**PURPOSE:** {spec.purpose}

**RELEVANT CONTEXT:**
{relevant_context}

**REQUIRED IMPORTS & DEPENDENCIES:**
{self._format_dependencies(dependencies)}

**ARCHITECTURAL GUIDANCE:**
{self._format_architectural_guidance(spec)}

**EXAMPLES FROM CODEBASE:**
{examples}

**CRITICAL REQUIREMENTS:**
1. Include ALL necessary import statements at the top
2. Write complete, runnable code with proper error handling
3. Follow exact class/method signatures from the context
4. Use descriptive variable names and clear logic
5. Include docstrings for classes and complex methods

**OUTPUT INSTRUCTIONS:**
- Return ONLY the complete Python code for {spec.filename}
- Do NOT include explanations, markdown, or code fences
- Ensure the code is immediately executable

Generate the complete code for `{spec.filename}`:`"""

        except Exception as e:
            self.event_bus.emit("log_message_received", "GenerationCoordinator", "warning",
                                f"Failed to build focused prompt for {spec.filename}, using fallback: {e}")
            return self._build_fallback_prompt(spec)

    def _extract_relevant_context(self, spec: 'FileGenerationSpec') -> str:
        """Extract only context relevant to the current file being generated."""
        try:
            context_parts = []

            # Add RAG context if available and relevant
            if spec.context.rag_context and len(spec.context.rag_context) > 50:
                # Truncate RAG context to most relevant parts
                rag_summary = self._summarize_rag_context(spec.context.rag_context, spec.filename, spec.purpose)
                if rag_summary:
                    context_parts.append(f"Knowledge Base Guidance:\n{rag_summary}")

            # Add living design context if available
            if spec.context.living_design_context:
                design_summary = self._extract_design_context(spec.context.living_design_context, spec.filename)
                if design_summary:
                    context_parts.append(f"Design Documentation:\n{design_summary}")

            # Add project structure context
            structure_info = self._get_project_structure_context(spec)
            if structure_info:
                context_parts.append(f"Project Structure:\n{structure_info}")

            return "\n\n".join(context_parts) if context_parts else "No additional context available."

        except Exception as e:
            return f"Error extracting context: {e}"

    def _summarize_rag_context(self, rag_context: str, filename: str, purpose: str = "") -> str:
        """Summarize RAG context to most relevant parts for the file."""
        try:
            # Split into chunks and find most relevant
            chunks = rag_context.split("--- Relevant Document Snippet")
            relevant_chunks = []

            # Look for chunks mentioning the filename or related concepts
            file_stem = Path(filename).stem
            search_terms = [file_stem, filename, purpose.lower() if purpose else '']

            for chunk in chunks[:3]:  # Limit to first 3 chunks
                if any(term in chunk.lower() for term in search_terms if term):
                    relevant_chunks.append(chunk.strip())

            if relevant_chunks:
                return "\n".join(relevant_chunks)
            else:
                # If no specific matches, return first chunk
                return chunks[0][:500] + "..." if chunks and len(chunks[0]) > 500 else chunks[0] if chunks else ""

        except Exception:
            return rag_context[:500] + "..." if len(rag_context) > 500 else rag_context

    def _extract_design_context(self, design_context: Dict[str, Any], filename: str) -> str:
        """Extract relevant design context for the specific file."""
        try:
            relevant_info = []
            file_stem = Path(filename).stem

            # Look for classes and functions relevant to this file
            if 'classes' in design_context:
                for class_info in design_context['classes']:
                    if file_stem in class_info.get('file', '') or filename in class_info.get('file', ''):
                        relevant_info.append(f"Class: {class_info.get('name', 'Unknown')}")
                        if 'methods' in class_info:
                            methods = [m.get('name', '') for m in class_info['methods'][:3]]
                            relevant_info.append(f"  Methods: {', '.join(methods)}")

            if 'functions' in design_context:
                for func_info in design_context['functions']:
                    if file_stem in func_info.get('file', '') or filename in func_info.get('file', ''):
                        relevant_info.append(f"Function: {func_info.get('name', 'Unknown')}")

            return "\n".join(relevant_info) if relevant_info else ""

        except Exception:
            return ""

    def _get_project_structure_context(self, spec: 'FileGenerationSpec') -> str:
        """Get relevant project structure information."""
        try:
            structure_parts = []

            # Add information about files this one depends on
            file_dir = str(Path(spec.filename).parent)
            if file_dir != ".":
                structure_parts.append(f"Module location: {file_dir}/")

            # Add information about related files in the plan
            related_files = []
            for file_info in spec.context.plan.get('files', []):
                if file_info['filename'] != spec.filename:
                    related_files.append(f"  {file_info['filename']}: {file_info['purpose']}")

            if related_files and len(related_files) <= 5:  # Limit to avoid overwhelming
                structure_parts.append("Related files in project:")
                structure_parts.extend(related_files)

            return "\n".join(structure_parts) if structure_parts else ""

        except Exception:
            return ""

    def _extract_file_dependencies(self, spec: 'FileGenerationSpec') -> List[str]:
        """Extract likely dependencies for the current file."""
        try:
            dependencies = []

            # Standard library imports based on file purpose
            purpose_lower = spec.purpose.lower()
            if any(word in purpose_lower for word in ['async', 'asyncio', 'await']):
                dependencies.append('import asyncio')
            if any(word in purpose_lower for word in ['path', 'file', 'directory']):
                dependencies.append('from pathlib import Path')
            if any(word in purpose_lower for word in ['json', 'dict', 'config']):
                dependencies.append('import json')
            if any(word in purpose_lower for word in ['type', 'typing', 'optional']):
                dependencies.append('from typing import Optional, Dict, List, Any')

            # Project-specific imports based on filename and purpose
            if 'service' in spec.filename.lower():
                dependencies.append('from core.event_bus import EventBus')
            if 'manager' in spec.filename.lower():
                dependencies.append('from pathlib import Path')

            # Look for imports from other files in the project
            for file_info in spec.context.plan.get('files', []):
                other_file = file_info['filename']
                if other_file != spec.filename and other_file.endswith('.py'):
                    module_name = other_file.replace('.py', '').replace('/', '.')
                    # Add import if this file likely depends on the other
                    if self._should_import_module(spec, file_info):
                        dependencies.append(f'from {module_name} import *')

            return list(set(dependencies))  # Remove duplicates

        except Exception:
            return ['from typing import Optional, Dict, List, Any']

    def _should_import_module(self, current_spec: 'FileGenerationSpec', other_file_info: Dict[str, str]) -> bool:
        """Determine if current file should import from another file."""
        try:
            current_purpose = current_spec.purpose.lower()
            other_purpose = other_file_info['purpose'].lower()
            other_filename = other_file_info['filename'].lower()

            # Main file usually imports from other modules
            if current_spec.filename == 'main.py':
                return True

            # Services often import from core modules
            if 'service' in current_spec.filename.lower() and 'core' in other_filename:
                return True

            # Look for keyword matches
            current_keywords = set(current_purpose.split())
            other_keywords = set(other_purpose.split())
            if len(current_keywords.intersection(other_keywords)) > 0:
                return True

            return False

        except Exception:
            return False

    def _format_dependencies(self, dependencies: List[str]) -> str:
        """Format dependencies for prompt inclusion."""
        if not dependencies:
            return "No specific dependencies identified."

        return "\n".join(f"- {dep}" for dep in dependencies[:10])  # Limit to 10

    def _format_architectural_guidance(self, spec: 'FileGenerationSpec') -> str:
        """Format architectural guidance for the file."""
        try:
            guidance = []

            # Add guidance based on filename patterns
            if 'service' in spec.filename.lower():
                guidance.append("- This is a service class - follow single responsibility principle")
                guidance.append("- Include proper error handling and logging")
                guidance.append("- Use dependency injection via constructor")

            if 'manager' in spec.filename.lower():
                guidance.append("- This is a manager class - coordinate between components")
                guidance.append("- Provide clear public interface methods")
                guidance.append("- Handle resource management and cleanup")

            if spec.filename == 'main.py':
                guidance.append("- This is the entry point - initialize all components")
                guidance.append("- Handle command line arguments if needed")
                guidance.append("- Include proper error handling for startup")

            # Add guidance based on purpose
            if 'ui' in spec.purpose.lower() or 'gui' in spec.purpose.lower():
                guidance.append("- Follow UI best practices with clear separation")
                guidance.append("- Handle user input validation")

            return "\n".join(guidance) if guidance else "Follow Python best practices and clean code principles."

        except Exception:
            return "Follow Python best practices and clean code principles."

    def _get_relevant_examples(self, spec: 'FileGenerationSpec') -> str:
        """Get relevant code examples from the project context."""
        try:
            examples = []

            # Look for similar files in the project index
            for module_name, module_info in spec.context.project_index.items():
                if isinstance(module_info, str) and len(module_info) > 50:
                    # Extract class/function signatures as examples
                    if 'class ' in module_info or 'def ' in module_info:
                        lines = module_info.split('\n')
                        signatures = [line.strip() for line in lines if
                                      line.strip().startswith(('class ', 'def ', 'async def '))]
                        if signatures:
                            examples.append(f"From {module_name}:")
                            examples.extend(f"  {sig}" for sig in signatures[:3])

            return "\n".join(examples[:10]) if examples else "No relevant examples found in existing code."

        except Exception:
            return "No relevant examples found in existing code."

    def _build_fallback_prompt(self, spec: 'FileGenerationSpec') -> str:
        """Build a simple fallback prompt if the focused prompt fails."""
        return f"""You are an expert Python developer. Write complete, production-ready code for the file `{spec.filename}`.

PURPOSE: {spec.purpose}

REQUIREMENTS:
1. Include all necessary imports
2. Write complete, runnable code
3. Add proper error handling
4. Follow Python best practices

Return ONLY the complete Python code for {spec.filename}. Do not include explanations or markdown.

Generate the code:"""

    def _clean_code_output(self, code: str) -> str:
        """Clean code output by removing markdown formatting."""
        if not code:
            return ""

        code = code.strip()

        # Remove common markdown patterns
        if code.startswith("```python"):
            code = code[len("```python"):].lstrip()
        elif code.startswith("```"):
            code = code[3:].lstrip()

        if code.endswith("```"):
            code = code[:-3].rstrip()

        # Remove any leading/trailing whitespace
        code = code.strip()

        # Ensure the code doesn't start with explanatory text
        lines = code.split('\n')
        start_idx = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'from ', 'class ', 'def ', 'async def ', '#')):
                start_idx = i
                break

        if start_idx > 0:
            code = '\n'.join(lines[start_idx:])

        return code.strip()