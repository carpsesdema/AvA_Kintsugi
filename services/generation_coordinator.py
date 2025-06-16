# services/generation_coordinator.py
# ENHANCED: Better project context building for coder prompt

import asyncio
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass
from collections import defaultdict

from core.event_bus import EventBus


@dataclass
class FileGenerationSpec:
    """Specification for generating a single file."""
    filename: str
    purpose: str
    context: 'GenerationContext'


@dataclass
class GenerationContext:
    """Complete context for code generation session."""
    plan: Dict[str, Any]
    project_index: Dict[str, Any]
    living_design_context: Dict[str, Any]
    dependency_order: List[str]
    generation_session: Dict[str, Any]
    rag_context: str
    relevance_scores: Dict[str, float]


class GenerationCoordinator:
    """
    Coordinates intelligent, context-aware code generation.
    ENHANCED: Now builds comprehensive project context for perfect import awareness.
    """

    def __init__(self, service_manager, event_bus: EventBus, context_manager,
                 dependency_planner, integration_validator):
        self.service_manager = service_manager
        self.event_bus = event_bus
        self.context_manager = context_manager
        self.dependency_planner = dependency_planner
        self.integration_validator = integration_validator

    async def coordinate_generation(self, plan: Dict[str, Any], rag_context: str) -> Dict[str, str]:
        """
        Coordinate generation of all files with enhanced project context awareness.
        """
        try:
            self.event_bus.emit("log_message_received", "GenerationCoordinator", "info",
                                "🚀 Starting coordinated generation with enhanced context...")

            # 1. Build comprehensive generation context
            context = await self.context_manager.build_generation_context(plan, rag_context)

            # 2. Create generation specifications with enhanced context
            generation_specs = await self._create_enhanced_generation_specs(plan, context)

            # 3. Generate files in dependency order with full context
            generated_files = await self._generate_files_with_context(generation_specs)

            # 4. Validate and fix integration issues
            validated_files = await self._validate_and_fix_integration(generated_files, context)

            self.event_bus.emit("log_message_received", "GenerationCoordinator", "success",
                                f"✅ Coordinated generation complete: {len(validated_files)} files")

            return validated_files

        except Exception as e:
            self.event_bus.emit("log_message_received", "GenerationCoordinator", "error",
                                f"Coordinated generation failed: {e}")
            return {}

    async def _create_enhanced_generation_specs(self, plan: Dict[str, Any],
                                                context: GenerationContext) -> List[FileGenerationSpec]:
        """Create generation specs with enhanced context for each file."""
        specs = []

        files_to_generate = plan.get("files", [])

        for file_info in files_to_generate:
            if file_info["filename"].endswith('.py'):
                spec = FileGenerationSpec(
                    filename=file_info["filename"],
                    purpose=file_info["purpose"],
                    context=context
                )
                specs.append(spec)

        return specs

    async def _generate_files_with_context(self, generation_specs: List[FileGenerationSpec]) -> Dict[str, str]:
        """Generate files with comprehensive project context."""
        generated_files = {}

        for i, spec in enumerate(generation_specs):
            try:
                self.event_bus.emit("log_message_received", "GenerationCoordinator", "info",
                                    f"📝 Generating {spec.filename} ({i + 1}/{len(generation_specs)})...")

                # Build enhanced prompt with full project context
                enhanced_prompt = await self._build_enhanced_context_prompt(spec, generated_files)

                # Generate the file
                generated_code = await self._generate_file_with_enhanced_prompt(spec, enhanced_prompt)

                if generated_code:
                    generated_files[spec.filename] = generated_code

                    # Update context with newly generated file
                    spec.context = self.context_manager.update_session_context(
                        spec.context, {spec.filename: generated_code}
                    )

                self.event_bus.emit("coordinated_generation_progress", {
                    "filename": spec.filename,
                    "completed": len(generated_files),
                    "total": len(generation_specs)
                })

            except Exception as e:
                self.event_bus.emit("log_message_received", "GenerationCoordinator", "error",
                                    f"Failed to generate {spec.filename}: {e}")
                # Continue with a placeholder
                generated_files[spec.filename] = f"# ERROR: Failed to generate {spec.filename}\n# {str(e)}\npass"

        return generated_files

    async def _build_enhanced_context_prompt(self, spec: FileGenerationSpec,
                                             generated_files: Dict[str, str]) -> str:
        """
        Build enhanced context prompt with comprehensive project awareness.
        This is the key fix for import/integration issues!
        """
        try:
            # Build comprehensive symbol index
            symbol_index = await self._build_comprehensive_symbol_index(generated_files, spec.context)

            # Build dependency map
            dependency_map = await self._build_dependency_map(generated_files, spec.context)

            # Build project structure
            project_structure = await self._build_project_structure(spec.context.plan, generated_files)

            # Enhanced coder prompt with all context
            from prompts.prompts import CODER_PROMPT

            enhanced_prompt = CODER_PROMPT.format(
                filename=spec.filename,
                purpose=spec.purpose,
                file_plan_json=json.dumps(spec.context.plan, indent=2),
                symbol_index_json=json.dumps(symbol_index, indent=2),
                existing_files_json=json.dumps(generated_files, indent=2),
                dependency_map_json=json.dumps(dependency_map, indent=2),
                project_structure_json=json.dumps(project_structure, indent=2),
                rag_context=spec.context.rag_context
            )

            return enhanced_prompt

        except Exception as e:
            self.event_bus.emit("log_message_received", "GenerationCoordinator", "warning",
                                f"Failed to build enhanced context for {spec.filename}, using fallback: {e}")
            return self._build_fallback_prompt(spec)

    async def _build_comprehensive_symbol_index(self, generated_files: Dict[str, str],
                                                context: GenerationContext) -> Dict[str, Any]:
        """Build comprehensive index of all classes and functions."""
        import ast
        import re

        symbol_index = {}

        # Analyze generated files
        for filename, content in generated_files.items():
            if filename.endswith('.py'):
                symbols = {"classes": [], "functions": [], "imports": []}

                try:
                    # AST-based analysis for accurate symbol extraction
                    tree = ast.parse(content)

                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            symbols["classes"].append(node.name)
                        elif isinstance(node, ast.FunctionDef):
                            symbols["functions"].append(node.name)
                        elif isinstance(node, ast.Import):
                            for alias in node.names:
                                symbols["imports"].append(alias.name)
                        elif isinstance(node, ast.ImportFrom):
                            module = node.module or ""
                            for alias in node.names:
                                symbols["imports"].append(f"{module}.{alias.name}" if module else alias.name)

                except SyntaxError:
                    # Fallback to regex-based analysis
                    symbols["classes"] = re.findall(r'^class\s+(\w+)', content, re.MULTILINE)
                    symbols["functions"] = re.findall(r'^def\s+(\w+)', content, re.MULTILINE)
                    symbols["imports"] = re.findall(r'^(?:import|from)\s+(\w+)', content, re.MULTILINE)

                symbol_index[filename] = symbols

        # Add planned files (not yet generated)
        for file_info in context.plan.get("files", []):
            filename = file_info["filename"]
            if filename.endswith('.py') and filename not in symbol_index:
                # Predict likely symbols based on purpose
                predicted_symbols = self._predict_symbols_from_purpose(file_info["purpose"], filename)
                symbol_index[filename] = predicted_symbols

        return symbol_index

    async def _build_dependency_map(self, generated_files: Dict[str, str],
                                    context: GenerationContext) -> Dict[str, List[str]]:
        """Build map of file dependencies."""
        import re

        dependency_map = {}

        for filename, content in generated_files.items():
            if filename.endswith('.py'):
                dependencies = []

                # Extract import statements
                import_patterns = [
                    r'^from\s+(\w+(?:\.\w+)*)\s+import',
                    r'^import\s+(\w+(?:\.\w+)*)'
                ]

                for pattern in import_patterns:
                    matches = re.findall(pattern, content, re.MULTILINE)
                    dependencies.extend(matches)

                dependency_map[filename] = dependencies

        return dependency_map

    async def _build_project_structure(self, plan: Dict[str, Any],
                                       generated_files: Dict[str, str]) -> Dict[str, Any]:
        """Build project structure information."""
        all_files = list(generated_files.keys())
        planned_files = [f["filename"] for f in plan.get("files", [])]

        # Combine generated and planned files
        all_files.extend([f for f in planned_files if f not in all_files])

        structure = {
            "total_files": len(all_files),
            "python_files": [f for f in all_files if f.endswith('.py')],
            "directories": list(set([
                '/'.join(f.split('/')[:-1]) for f in all_files
                if '/' in f and f.split('/')[:-1]
            ])),
            "main_files": [f for f in all_files if f.endswith('main.py')],
            "dependencies": plan.get("dependencies", [])
        }

        return structure

    def _predict_symbols_from_purpose(self, purpose: str, filename: str) -> Dict[str, List[str]]:
        """Predict likely symbols based on file purpose."""
        symbols = {"classes": [], "functions": [], "imports": []}

        # Extract potential class names from purpose
        import re

        # Look for class-like words in purpose
        class_words = re.findall(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)*)\b', purpose)
        symbols["classes"] = class_words

        # Predict common functions based on filename
        base_name = filename.replace('.py', '').split('/')[-1]
        if 'main' in base_name:
            symbols["functions"] = ['main', 'run', 'start']
        elif 'manager' in base_name:
            symbols["functions"] = ['initialize', 'manage', 'update']
        elif 'service' in base_name:
            symbols["functions"] = ['process', 'handle', 'execute']

        return symbols

    async def _generate_file_with_enhanced_prompt(self, spec: FileGenerationSpec,
                                                  enhanced_prompt: str) -> Optional[str]:
        """Generate file using enhanced prompt."""
        llm_client = self.service_manager.get_llm_client()
        provider, model = llm_client.get_model_for_role("coder")

        if not provider or not model:
            return None

        file_content = ""
        try:
            async for chunk in llm_client.stream_chat(provider, model, enhanced_prompt, "coder"):
                file_content += chunk
                self.event_bus.emit("stream_code_chunk", spec.filename, chunk)
        except Exception as e:
            self.event_bus.emit("log_message_received", "GenerationCoordinator", "error",
                                f"LLM generation failed for {spec.filename}: {e}")
            return None

        return self._clean_code_output(file_content)

    async def _validate_and_fix_integration(self, generated_files: Dict[str, str],
                                            context: GenerationContext) -> Dict[str, str]:
        """Validate and fix integration issues in generated files."""
        try:
            validated_files = generated_files.copy()

            # Run integration validation
            for filename, content in generated_files.items():
                if filename.endswith('.py'):
                    validation_result = await self.integration_validator.validate_integration(
                        filename, content, generated_files, context
                    )

                    if not validation_result.is_valid:
                        self.event_bus.emit("log_message_received", "GenerationCoordinator", "warning",
                                            f"Integration issues found in {filename}, attempting fixes...")

                        fixed_content = await self.integration_validator.fix_integration_issues(
                            filename, content, validation_result, context
                        )

                        if fixed_content:
                            validated_files[filename] = fixed_content
                            self.event_bus.emit("log_message_received", "GenerationCoordinator", "success",
                                                f"✅ Fixed integration issues in {filename}")

            return validated_files

        except Exception as e:
            self.event_bus.emit("log_message_received", "GenerationCoordinator", "error",
                                f"Integration validation failed: {e}")
            return generated_files

    def _build_fallback_prompt(self, spec: FileGenerationSpec) -> str:
        """Build fallback prompt if enhanced context fails."""
        from prompts.prompts import CODER_PROMPT

        return CODER_PROMPT.format(
            filename=spec.filename,
            purpose=spec.purpose,
            file_plan_json=json.dumps(spec.context.plan, indent=2),
            symbol_index_json="{}",
            existing_files_json="{}",
            dependency_map_json="{}",
            project_structure_json="{}",
            rag_context=spec.context.rag_context
        )

    def _clean_code_output(self, content: str) -> str:
        """Clean the generated code output."""
        # Remove any markdown code blocks
        import re
        content = re.sub(r'^```python\s*\n?', '', content, flags=re.MULTILINE)
        content = re.sub(r'^```\s*$', '', content, flags=re.MULTILINE)

        # Remove any leading/trailing whitespace
        content = content.strip()

        return content