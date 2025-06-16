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
            spec.context = self.context_manager.update_session_context(
                spec.context, generated_files
            )

            # Step 1: Generate the code from the LLM, now with imports included.
            generated_code = await self._generate_coordinated_file(spec)
            if generated_code is None:
                raise Exception(f"Failed to generate {spec.filename}")

            # Step 2: Use the import fixer as a "linter" or safety net for any minor misses.
            self.event_bus.emit("log_message_received", "ImportFixer", "info",
                                f"Verifying imports for {spec.filename}...")
            fixed_code = import_fixer.fix_imports(
                code=generated_code,
                project_index=spec.context.project_index,
                current_module=spec.filename.replace('.py', '').replace('/', '.')
            )
            generated_code = fixed_code

            # Step 3: Validate the now-complete code.
            validation_result = await self.integration_validator.validate_integration(
                spec.filename, generated_code, generated_files, spec.context
            )

            if not validation_result.is_valid:
                fixed_code = await self.integration_validator.fix_integration_issues(
                    spec.filename, generated_code, validation_result, spec.context
                )
                generated_code = fixed_code if fixed_code else generated_code

            generated_files[spec.filename] = generated_code

            self.event_bus.emit("coordinated_generation_progress", {
                "filename": spec.filename, "completed": len(generated_files),
                "total": len(generation_specs), "validation_passed": validation_result.is_valid
            })

        return generated_files

    async def _generate_coordinated_file(self, spec: 'FileGenerationSpec') -> Optional[str]:
        """Generate a single file with full coordination context."""
        llm_client = self.service_manager.get_llm_client()
        provider, model = llm_client.get_model_for_role("coder")

        if not provider or not model: return None

        prompt = self._build_coordinated_prompt(spec)

        file_content = ""
        async for chunk in llm_client.stream_chat(provider, model, prompt, "coder"):
            file_content += chunk
            self.event_bus.emit("stream_code_chunk", spec.filename, chunk)

        return self._clean_code_output(file_content)

    def _build_coordinated_prompt(self, spec: 'FileGenerationSpec') -> str:
        """Build a prompt with comprehensive coordination context."""
        # --- THIS IS THE FIX ---
        # The prompt now explicitly instructs the AI to write complete, runnable files with imports.
        return f"""You are an expert Python developer generating code for a multi-file application.

**HIGH-LEVEL GOAL:** Write the complete, runnable Python code for the file `{spec.filename}`.

**KNOWLEDGE BASE CONTEXT (RAG):**
Use this information for best practices, API examples, and to inform your code structure.
---
{spec.context.rag_context}
---

**SYSTEM ARCHITECTURE & CONTEXT:**
- **Full Project Plan:** {json.dumps(spec.context.plan, indent=2)}
- **Your Specific Task:** The purpose of `{spec.filename}` is: "{spec.purpose}"
- **Project File Index:** {json.dumps(spec.context.project_index, indent=2)}

**CRITICAL INSTRUCTIONS:**
1.  **Write All Imports:** You MUST write all necessary `import` statements. The code must be self-contained and runnable.
2.  **Be Precise:** Ensure class names, function names, and method parameters match the definitions in other files as described in the project context.
3.  **Focus on Your File:** Only generate the code for `{spec.filename}`.
4.  **No Explanations:** Your response MUST ONLY be the raw source code for the file. Do not add any conversational text or markdown.

Generate the complete code for `{spec.filename}`:"""

    def _clean_code_output(self, code: str) -> str:
        """Clean code output by removing markdown formatting."""
        code = code.strip()
        if code.startswith("```python"):
            code = code[len("```python"):].lstrip()
        elif code.startswith("```"):
            code = code[3:].lstrip()
        if code.endswith("```"):
            code = code[:-3].rstrip()
        return code.strip()