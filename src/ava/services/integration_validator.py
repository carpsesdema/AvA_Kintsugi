import ast
import json
import textwrap
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from src.ava.services.context_manager import GenerationContext


@dataclass
class ValidationResult:
    """Result of integration validation."""
    is_valid: bool
    issues: List[str]
    suggestions: List[str]
    confidence: float


class IntegrationValidator:
    """
    Validates integration in real-time during generation.

    Single Responsibility: Ensure generated files integrate properly
    with existing and previously generated files.
    """

    def __init__(self, service_manager):
        self.service_manager = service_manager

    async def validate_integration(self, filename: str, code: str,
                                   previously_generated: Dict[str, str],
                                   context: GenerationContext) -> ValidationResult:
        """Validate that a file integrates properly with the rest of the system."""
        issues = []
        suggestions = []

        # 1. Validate imports
        import_issues = self._validate_imports(code, previously_generated, context)
        issues.extend(import_issues)

        # 2. Validate dependencies are satisfied
        dep_issues = self._validate_dependencies(filename, code, previously_generated, context)
        issues.extend(dep_issues)

        # 3. Validate interfaces match expectations
        interface_issues = self._validate_interfaces(filename, code, context)
        issues.extend(interface_issues)

        is_valid = len(issues) == 0
        confidence = 1.0 - (len(issues) * 0.1)  # Reduce confidence for each issue

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            suggestions=suggestions,
            confidence=max(0.0, confidence)
        )

    async def fix_integration_issues(self, filename: str, code: str,
                                     validation_result: ValidationResult,
                                     context: GenerationContext) -> Optional[str]:
        """Attempt to fix integration issues using LLM."""
        if validation_result.is_valid:
            return code

        llm_client = self.service_manager.get_llm_client()
        provider, model = llm_client.get_model_for_role("coder")

        if not provider or not model:
            return None

        fix_prompt = self._build_fix_prompt(filename, code, validation_result, context)

        fixed_code = ""
        async for chunk in llm_client.stream_chat(provider, model, fix_prompt, "coder"):
            fixed_code += chunk

        return self._clean_code_output(fixed_code)

    def _validate_imports(self, code: str, previously_generated: Dict[str, str],
                          context: GenerationContext) -> List[str]:
        """Validate that all imports can be resolved."""
        issues = []

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if not self._can_resolve_import(alias.name, previously_generated, context):
                            issues.append(f"Cannot resolve import: {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and not self._can_resolve_import(node.module, previously_generated, context):
                        issues.append(f"Cannot resolve import: from {node.module}")

        except SyntaxError as e:
            issues.append(f"Syntax error in code: {e}")

        return issues

    def _validate_dependencies(self, filename: str, code: str,
                               previously_generated: Dict[str, str],
                               context: GenerationContext) -> List[str]:
        """Validate that dependencies are properly satisfied."""
        # This would be expanded with more sophisticated dependency checking
        return []

    def _validate_interfaces(self, filename: str, code: str,
                             context: GenerationContext) -> List[str]:
        """Validate that interfaces match what other files expect."""
        # This would be expanded with interface contract validation
        return []

    def _can_resolve_import(self, import_name: str, previously_generated: Dict[str, str],
                            context: GenerationContext) -> bool:
        """Check if an import can be resolved."""
        # Check if it's a standard library import
        try:
            __import__(import_name.split('.')[0])
            return True
        except ImportError:
            pass

        # Check if it's in previously generated files
        for filename in previously_generated:
            module_name = Path(filename).stem
            if import_name.startswith(module_name):
                return True

        # Check if it's in existing project files
        if import_name in context.project_index:
            return True

        return False

    def _build_fix_prompt(self, filename: str, code: str,
                          validation_result: ValidationResult,
                          context: GenerationContext) -> str:
        """Build prompt for fixing integration issues."""
        return textwrap.dedent(f"""\
            You are fixing integration issues in generated code.

            **FILE:** {filename}

            **CURRENT CODE:**
            ```python
            {code}
            ```

            **INTEGRATION ISSUES FOUND:**
            {chr(10).join(f"- {issue}" for issue in validation_result.issues)}

            **CONTEXT:**
            - Project structure: {json.dumps(context.project_index, indent=2)}
            - Generation session: {json.dumps(context.generation_session, indent=2)}

            **INSTRUCTIONS:**
            Fix the integration issues in the code. Return ONLY the corrected complete code for the file.
            Do not include explanations or markdown formatting.

            Fixed code:""")

    def _clean_code_output(self, code: str) -> str:
        """Clean code output."""
        code = code.strip()
        if code.startswith("```python"):
            code = code[len("```python"):].lstrip()
        elif code.startswith("```"):
            code = code[3:].lstrip()
        if code.endswith("```"):
            code = code[:-3].rstrip()
        return code.strip()