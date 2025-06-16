# kintsugi_ava/core/plugins/examples/system_integrator/__init__.py
# System Integrator Plugin - Production-quality holistic code integration analysis and fixing

import asyncio
import ast
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass

from core.plugins import PluginBase, PluginMetadata, PluginState


@dataclass
class IntegrationIssue:
    """Represents a code integration issue that needs fixing."""
    issue_type: str
    severity: str  # "critical", "high", "medium", "low"
    file_path: str
    line_number: Optional[int]
    description: str
    context: Dict[str, Any]
    suggested_fix: Optional[str] = None
    fix_confidence: float = 0.0  # 0.0 to 1.0


@dataclass
class CodeElement:
    """Represents a code element (class, function, method) with its signature."""
    name: str
    element_type: str  # "class", "function", "method"
    file_path: str
    line_number: int
    signature: Dict[str, Any]
    dependencies: Set[str]
    parent_class: Optional[str] = None


class SystemIntegratorPlugin(PluginBase):
    """
    Production-quality System Integrator that ensures all generated code works together.

    This plugin:
    - Performs deep AST analysis of the entire codebase
    - Identifies and fixes integration issues between modules
    - Validates constructor calls, method signatures, and interfaces
    - Ensures main.py properly initializes all components
    - Applies LLM-powered fixes for complex integration problems
    - Integrates fully with ProjectManager and LLMClient
    """

    def __init__(self, event_bus, plugin_config: Dict[str, Any]):
        super().__init__(event_bus, plugin_config)

        # Service references (injected by ServiceManager)
        self.service_manager = None
        self.project_manager = None
        self.llm_client = None

        # Code analysis state
        self.code_elements: Dict[str, CodeElement] = {}
        self.integration_issues: List[IntegrationIssue] = []
        self.import_map: Dict[str, Set[str]] = defaultdict(set)  # file -> imported names
        self.definition_map: Dict[str, str] = {}  # name -> file where defined
        self.usage_map: Dict[str, List[Tuple[str, int]]] = defaultdict(list)  # name -> [(file, line)]

        # Integration tracking
        self.last_integration_check: Optional[datetime] = None
        self.fixes_applied: List[Dict[str, Any]] = []
        self.integration_queue: asyncio.Queue = asyncio.Queue()

        # Processing state
        self.is_analyzing = False
        self.integration_worker_task: Optional[asyncio.Task] = None

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="system_integrator",
            version="1.0.0",
            description="Production-quality system integration analysis and automatic fixing",
            author="Kintsugi AvA Team",
            dependencies=[],
            event_subscriptions=[
                "code_generation_complete",
                "prepare_for_generation",
                "execution_failed",
                "new_project_requested"
            ],
            event_emissions=[
                "integration_analysis_started",
                "integration_issue_detected",
                "integration_fix_applied",
                "integration_analysis_complete"
            ],
            config_schema={
                "auto_integration_check": {
                    "type": "bool",
                    "default": True,
                    "description": "Automatically check integration after code generation"
                },
                "auto_fix_enabled": {
                    "type": "bool",
                    "default": True,
                    "description": "Automatically fix detected integration issues"
                },
                "fix_confidence_threshold": {
                    "type": "float",
                    "default": 0.8,
                    "description": "Minimum confidence level to auto-apply fixes (0.0-1.0)"
                },
                "analysis_depth": {
                    "type": "str",
                    "default": "deep",
                    "description": "Analysis depth: 'quick', 'standard', 'deep'"
                },
                "detailed_logging": {
                    "type": "bool",
                    "default": True,
                    "description": "Log detailed integration analysis information"
                }
            },
            enabled_by_default=True
        )

    async def load(self) -> bool:
        try:
            self.log("info", "Loading System Integrator...")
            self._reset_analysis_state()
            self.set_state(PluginState.LOADED)
            self.log("success", "System Integrator loaded")
            return True
        except Exception as e:
            self.log("error", f"Failed to load System Integrator: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def start(self) -> bool:
        try:
            self.log("info", "Starting System Integrator...")

            # Get service references
            await self._initialize_service_references()

            # Subscribe to events
            self.subscribe_to_event("code_generation_complete", self._on_code_generated)
            self.subscribe_to_event("prepare_for_generation", self._on_generation_prepared)
            self.subscribe_to_event("execution_failed", self._on_execution_failed)
            self.subscribe_to_event("new_project_requested", self._on_new_project)

            # Start integration worker
            self.integration_worker_task = asyncio.create_task(self._integration_worker())

            self.set_state(PluginState.STARTED)
            self.log("info", "🔗 System Integrator active - production-quality integration monitoring")
            return True

        except Exception as e:
            self.log("error", f"Failed to start System Integrator: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def stop(self) -> bool:
        try:
            self.log("info", "Stopping System Integrator...")

            if self.integration_worker_task:
                self.integration_worker_task.cancel()
                try:
                    await self.integration_worker_task
                except asyncio.CancelledError:
                    pass

            await self._generate_integration_report()
            self.set_state(PluginState.STOPPED)
            return True

        except Exception as e:
            self.log("error", f"Failed to stop System Integrator: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def unload(self) -> bool:
        try:
            self.log("info", "Unloading System Integrator...")
            self._reset_analysis_state()
            self.set_state(PluginState.UNLOADED)
            self.log("info", "System Integrator unloaded")
            return True
        except Exception as e:
            self.log("error", f"Failed to unload System Integrator: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def _initialize_service_references(self):
        """Initialize references to required services."""
        # Wait a bit for services to be fully initialized
        await asyncio.sleep(0.1)

        # Get service manager from event bus context (this would be injected in a real implementation)
        # For now, we'll emit an event to request service manager reference
        self.emit_event("plugin_service_manager_request", "system_integrator")

    # Event Handlers
    def _on_code_generated(self, files: Dict[str, str]):
        """Handle code generation completion - queue integration analysis."""
        if not self.get_config_value("auto_integration_check", True):
            return

        self.log("info", f"Code generation complete - queueing deep integration analysis for {len(files)} files")

        asyncio.create_task(self.integration_queue.put({
            "type": "full_analysis",
            "files": files,
            "timestamp": datetime.now().isoformat(),
            "priority": "normal"
        }))

    def _on_generation_prepared(self, filenames: List[str], project_path: str = None):
        """Handle generation preparation."""
        if self.get_config_value("detailed_logging", True):
            self.log("info", f"Generation prepared for {len(filenames)} files - resetting analysis state")
        self._reset_analysis_state()

    def _on_execution_failed(self, error_report: str):
        """Handle execution failures - high priority integration analysis."""
        self.log("warning", "Execution failed - prioritizing integration analysis")

        asyncio.create_task(self.integration_queue.put({
            "type": "error_focused_analysis",
            "error_report": error_report,
            "priority": "critical",
            "timestamp": datetime.now().isoformat()
        }))

    def _on_new_project(self):
        """Handle new project creation."""
        self.log("info", "New project detected - resetting integration state")
        self._reset_analysis_state()

    # Core Integration Analysis
    async def _integration_worker(self):
        """Worker that processes integration analysis requests."""
        self.log("info", "Integration worker started")

        while self.state == PluginState.STARTED:
            try:
                request = await asyncio.wait_for(self.integration_queue.get(), timeout=1.0)

                self.is_analyzing = True
                await self._process_integration_request(request)
                self.is_analyzing = False

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log("error", f"Error in integration worker: {e}")
                self.is_analyzing = False

    async def _process_integration_request(self, request: Dict[str, Any]):
        """Process integration analysis request with full error handling."""
        try:
            request_type = request.get("type", "unknown")
            priority = request.get("priority", "normal")

            self.log("info", f"Processing {priority} integration request: {request_type}")

            self.emit_event("integration_analysis_started", {
                "request_type": request_type,
                "priority": priority,
                "timestamp": datetime.now().isoformat()
            })

            if request_type == "full_analysis":
                await self._perform_full_integration_analysis(request.get("files", {}))
            elif request_type == "error_focused_analysis":
                await self._perform_error_focused_analysis(request.get("error_report", ""))

            self.emit_event("integration_analysis_complete", {
                "request_type": request_type,
                "issues_found": len(self.integration_issues),
                "fixes_applied": len(self.fixes_applied),
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            self.log("error", f"Failed to process integration request: {e}")

    async def _perform_full_integration_analysis(self, files_to_analyze: Dict[str, str]):
        """
        Perform comprehensive integration analysis using in-memory code.
        """
        try:
            self.log("info", "Starting comprehensive integration analysis...")

            # --- THIS IS THE FIX ---
            # We now use the 'files_to_analyze' dictionary from the event payload,
            # which contains the complete, final code. We no longer read from disk here.
            if not files_to_analyze:
                self.log("warning", "No files provided for analysis.")
                return

            self.log("info", f"Analyzing {len(files_to_analyze)} in-memory files...")

            # Step 1: Deep AST analysis of all files passed in the event
            await self._build_comprehensive_code_map(files_to_analyze)
            # --- END OF FIX ---

            # Step 2: Identify integration issues
            issues = await self._identify_all_integration_issues()

            if issues:
                self.log("warning", f"Found {len(issues)} integration issues")
                critical = [i for i in issues if i.severity == "critical"]
                high = [i for i in issues if i.severity == "high"]
                medium = [i for i in issues if i.severity == "medium"]
                low = [i for i in issues if i.severity == "low"]
                self.log("info", f"Issues by severity - Critical: {len(critical)}, High: {len(high)}, Medium: {len(medium)}, Low: {len(low)}")

                # Step 3: Apply fixes if enabled
                if self.get_config_value("auto_fix_enabled", True):
                    await self._apply_comprehensive_fixes(issues)
            else:
                self.log("success", "No integration issues found - project is well integrated")

            self.last_integration_check = datetime.now()

        except Exception as e:
            self.log("error", f"Failed to perform integration analysis: {e}")
            import traceback
            traceback.print_exc()

    async def _build_comprehensive_code_map(self, files: Dict[str, str]):
        """Build comprehensive map of all code elements, imports, and usage."""
        try:
            self.log("info", "Building comprehensive code map...")

            # Clear previous analysis
            self.code_elements.clear()
            self.import_map.clear()
            self.definition_map.clear()
            self.usage_map.clear()

            # Analyze each file
            for file_path, content in files.items():
                if file_path.endswith('.py'):
                    await self._analyze_file_comprehensively(file_path, content)

            # Build cross-references
            self._build_cross_references()

            self.log("success", f"Code map complete: {len(self.code_elements)} elements, {len(self.definition_map)} definitions")

        except Exception as e:
            self.log("error", f"Failed to build code map: {e}")

    async def _analyze_file_comprehensively(self, file_path: str, content: str):
        """Perform comprehensive analysis of a single file."""
        try:
            tree = ast.parse(content)

            # Track imports
            self._extract_imports(tree, file_path)

            # Track definitions and usage
            visitor = ComprehensiveASTVisitor(file_path)
            visitor.visit(tree)

            # Store results
            for element in visitor.elements:
                key = f"{file_path}::{element.name}"
                self.code_elements[key] = element
                self.definition_map[element.name] = file_path

            # Store usage information
            for name, line in visitor.name_usage:
                self.usage_map[name].append((file_path, line))

        except SyntaxError as e:
            # Syntax errors are critical integration issues
            issue = IntegrationIssue(
                issue_type="syntax_error",
                severity="critical",
                file_path=file_path,
                line_number=e.lineno,
                description=f"Syntax error: {e.msg}",
                context={"error": str(e), "text": e.text},
                fix_confidence=0.9
            )
            self.integration_issues.append(issue)
        except Exception as e:
            self.log("warning", f"Could not analyze {file_path}: {e}")

    def _extract_imports(self, tree: ast.AST, file_path: str):
        """Extract all imports from a file."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_name = alias.asname or alias.name
                    self.import_map[file_path].add(imported_name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        imported_name = alias.asname or alias.name
                        self.import_map[file_path].add(imported_name)

    def _build_cross_references(self):
        """Build cross-references between definitions and usage."""
        for element_key, element in self.code_elements.items():
            # Add imports as dependencies
            file_imports = self.import_map.get(element.file_path, set())
            element.dependencies.update(file_imports)

    async def _identify_all_integration_issues(self) -> List[IntegrationIssue]:
        """Identify all types of integration issues."""
        issues = []

        # Check for undefined name usage
        issues.extend(await self._check_undefined_names())
        # Check constructor calls
        issues.extend(await self._check_constructor_calls())
        # Check main.py integration
        issues.extend(await self._check_main_py_integration())
        # Check import consistency
        issues.extend(await self._check_import_consistency())

        # Store and emit issues
        self.integration_issues.extend(issues)
        for issue in issues:
            self.emit_event("integration_issue_detected", {
                "issue_type": issue.issue_type, "severity": issue.severity,
                "file_path": issue.file_path, "description": issue.description,
                "confidence": issue.fix_confidence
            })
        return issues

    async def _check_undefined_names(self) -> List[IntegrationIssue]:
        """Check for usage of undefined names."""
        issues = []
        for name, usage_locations in self.usage_map.items():
            if name in {'self', 'cls', 'super', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple'}:
                continue
            for file_path, line_num in usage_locations:
                file_imports = self.import_map.get(file_path, set())
                local_definitions = {elem.name for elem in self.code_elements.values() if elem.file_path == file_path}
                if name not in file_imports and name not in local_definitions and name not in self.definition_map:
                    issue = IntegrationIssue(
                        issue_type="undefined_name", severity="high", file_path=file_path, line_number=line_num,
                        description=f"Undefined name '{name}' used",
                        context={"name": name, "available_definitions": list(self.definition_map.keys())},
                        fix_confidence=0.7
                    )
                    issues.append(issue)
        return issues

    async def _check_constructor_calls(self) -> List[IntegrationIssue]:
        """Check constructor calls against class definitions."""
        issues = []
        main_py_content = await self._get_file_content("main.py")
        if main_py_content:
            try:
                tree = ast.parse(main_py_content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        class_name = node.func.id
                        class_element = self._find_class_definition(class_name)
                        if class_element:
                            expected_args = class_element.signature.get("constructor_args", [])
                            provided_args = len(node.args)
                            if provided_args != len(expected_args):
                                issue = IntegrationIssue(
                                    issue_type="constructor_mismatch", severity="high", file_path="main.py", line_number=node.lineno,
                                    description=f"Constructor for {class_name} expects {len(expected_args)} args but got {provided_args}",
                                    context={
                                        "class_name": class_name, "expected_args": expected_args,
                                        "provided_args": provided_args, "definition_file": class_element.file_path
                                    },
                                    fix_confidence=0.9
                                )
                                issues.append(issue)
            except Exception as e:
                self.log("warning", f"Could not analyze main.py for constructor calls: {e}")
        return issues

    async def _check_main_py_integration(self) -> List[IntegrationIssue]:
        """Check main.py for integration issues."""
        issues = []
        main_content = await self._get_file_content("main.py")
        if not main_content: return issues
        try:
            tree = ast.parse(main_content)
            has_try_except = any(isinstance(node, ast.Try) for node in ast.walk(tree))
            if not has_try_except:
                issue = IntegrationIssue(
                    issue_type="missing_error_handling", severity="medium", file_path="main.py", line_number=1,
                    description="main.py lacks error handling - could fail silently",
                    context={"suggestion": "Add try-except blocks around main logic"},
                    fix_confidence=0.8
                )
                issues.append(issue)
        except Exception as e:
            self.log("warning", f"Could not analyze main.py integration: {e}")
        return issues

    async def _check_import_consistency(self) -> List[IntegrationIssue]:
        """Check for import-related issues."""
        issues = []
        for file_path, imports in self.import_map.items():
            for imported_name in imports:
                if imported_name not in self.definition_map and not self._is_external_import(imported_name):
                    issue = IntegrationIssue(
                        issue_type="missing_import_target", severity="medium", file_path=file_path, line_number=1,
                        description=f"Import '{imported_name}' not found in project",
                        context={"import_name": imported_name}, fix_confidence=0.6
                    )
                    issues.append(issue)
        return issues

    def _is_external_import(self, name: str) -> bool:
        """Check if an import is external (standard library or third-party)."""
        external_prefixes = {
            'os', 'sys', 'json', 'ast', 're', 'pathlib', 'typing', 'datetime', 'collections',
            'asyncio', 'dataclasses', 'PySide6', 'qtawesome', 'aiohttp', 'openai'
        }
        return any(name.startswith(prefix) for prefix in external_prefixes)

    def _find_class_definition(self, class_name: str) -> Optional[CodeElement]:
        """Find class definition by name."""
        for element in self.code_elements.values():
            if element.element_type == "class" and element.name == class_name:
                return element
        return None

    async def _get_file_content(self, file_path: str) -> Optional[str]:
        """Get content of a specific file from the project."""
        if not self.project_manager or not self.project_manager.active_project_path: return None
        try:
            full_path = self.project_manager.active_project_path / file_path
            if full_path.exists(): return full_path.read_text(encoding='utf-8')
        except Exception as e:
            self.log("warning", f"Could not read {file_path}: {e}")
        return None

    async def _apply_comprehensive_fixes(self, issues: List[IntegrationIssue]):
        """Apply fixes with confidence thresholding."""
        confidence_threshold = self.get_config_value("fix_confidence_threshold", 0.8)
        issues_to_fix = sorted(
            [i for i in issues if i.fix_confidence >= confidence_threshold],
            key=lambda x: ({"critical": 0, "high": 1, "medium": 2, "low": 3}[x.severity], -x.fix_confidence)
        )
        self.log("info", f"Applying {len(issues_to_fix)} high-confidence fixes (threshold: {confidence_threshold})")
        files_to_update = {}
        for issue in issues_to_fix:
            fix_result = await self._generate_and_apply_fix(issue)
            if fix_result:
                if issue.file_path not in files_to_update:
                    files_to_update[issue.file_path] = await self._get_file_content(issue.file_path) or ""
                files_to_update[issue.file_path] = fix_result["new_content"]
                self.fixes_applied.append({
                    "issue": issue, "fix_applied": fix_result["fix_description"],
                    "timestamp": datetime.now().isoformat(), "confidence": issue.fix_confidence
                })
        if files_to_update and self.project_manager:
            try:
                commit_message = f"fix: system integration fixes - {len(self.fixes_applied)} issues resolved"
                self.project_manager.save_and_commit_files(files_to_update, commit_message)
                self.log("success", f"Applied {len(self.fixes_applied)} integration fixes and committed changes")
            except Exception as e:
                self.log("error", f"Failed to commit fixes: {e}")

    async def _generate_and_apply_fix(self, issue: IntegrationIssue) -> Optional[Dict[str, Any]]:
        """Generate and apply a fix for a specific issue."""
        try:
            if issue.issue_type == "undefined_name": return await self._fix_undefined_name(issue)
            elif issue.issue_type == "constructor_mismatch": return await self._fix_constructor_mismatch(issue)
            elif issue.issue_type == "syntax_error": return await self._fix_syntax_error(issue)
            elif issue.issue_type == "missing_error_handling": return await self._fix_missing_error_handling(issue)
            else:
                self.log("warning", f"No fix handler for issue type: {issue.issue_type}")
                return None
        except Exception as e:
            self.log("error", f"Failed to generate fix for {issue.issue_type}: {e}")
            return None

    async def _fix_undefined_name(self, issue: IntegrationIssue) -> Optional[Dict[str, Any]]:
        """Fix undefined name by adding appropriate import."""
        name = issue.context["name"]
        if name in self.definition_map:
            definition_file = self.definition_map[name]
            module_name = definition_file.replace('.py', '').replace('/', '.')
            import_statement = f"from {module_name} import {name}"
            current_content = await self._get_file_content(issue.file_path)
            if current_content:
                lines = current_content.split('\n')
                import_insert_line = 0
                for i, line in enumerate(lines):
                    if line.strip().startswith(('import ', 'from ')): import_insert_line = i + 1
                    elif line.strip() and not line.strip().startswith('#'): break
                lines.insert(import_insert_line, import_statement)
                return {"new_content": '\n'.join(lines), "fix_description": f"Added import: {import_statement}"}
        return None

    async def _fix_constructor_mismatch(self, issue: IntegrationIssue) -> Optional[Dict[str, Any]]:
        """Fix constructor mismatch using LLM."""
        if not self.llm_client: return None
        try:
            context = issue.context
            class_name = context["class_name"]
            expected_args = context["expected_args"]
            prompt = f"""Fix this constructor call in main.py:
Current issue: {issue.description}
Class: {class_name}
Expected constructor arguments: {expected_args}
Generate the correct constructor call. Respond with only the corrected line of code.
Example: MyClass(arg1, arg2, arg3)"""
            provider, model = self.llm_client.get_model_for_role("reviewer")
            if provider and model:
                fix_response = "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, prompt, "reviewer")]).strip()
                if fix_response and class_name in fix_response:
                    current_content = await self._get_file_content(issue.file_path)
                    if current_content:
                        lines = current_content.split('\n')
                        if issue.line_number and issue.line_number <= len(lines):
                            old_line = lines[issue.line_number - 1]
                            if class_name in old_line:
                                new_line = re.sub(rf'{class_name}\([^)]*\)', fix_response, old_line)
                                lines[issue.line_number - 1] = new_line
                                return {"new_content": '\n'.join(lines), "fix_description": f"Fixed constructor call: {fix_response}"}
        except Exception as e:
            self.log("error", f"Failed to generate LLM fix for constructor: {e}")
        return None

    async def _fix_syntax_error(self, issue: IntegrationIssue) -> Optional[Dict[str, Any]]:
        """Fix syntax error using LLM."""
        if not self.llm_client: return None
        try:
            prompt = f"""Fix this Python syntax error:
File: {issue.file_path}
Line: {issue.line_number}
Error: {issue.description}
Problematic text: {issue.context.get('text', '')}
Provide the corrected line of code. Respond with only the fixed line."""
            provider, model = self.llm_client.get_model_for_role("reviewer")
            if provider and model:
                fix_response = "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, prompt, "reviewer")]).strip()
                if fix_response:
                    current_content = await self._get_file_content(issue.file_path)
                    if current_content and issue.line_number:
                        lines = current_content.split('\n')
                        if issue.line_number <= len(lines):
                            lines[issue.line_number - 1] = fix_response
                            return {"new_content": '\n'.join(lines), "fix_description": f"Fixed syntax error on line {issue.line_number}"}
        except Exception as e:
            self.log("error", f"Failed to generate syntax fix: {e}")
        return None

    async def _fix_missing_error_handling(self, issue: IntegrationIssue) -> Optional[Dict[str, Any]]:
        """Add basic error handling to main.py."""
        current_content = await self._get_file_content(issue.file_path)
        if not current_content: return None
        try:
            lines = current_content.split('\n')
            main_start = -1
            for i, line in enumerate(lines):
                if 'if __name__ == "__main__"' in line: main_start = i; break
            if main_start >= 0:
                indent = "    "
                lines.insert(main_start + 1, f"{indent}try:")
                for i in range(main_start + 2, len(lines)):
                    if lines[i].strip(): lines[i] = f"{indent}{lines[i]}"
                lines.extend([
                    f"{indent}except Exception as e:",
                    f"{indent}    print(f'Application error: {{e}}')",
                    f"{indent}    import traceback",
                    f"{indent}    traceback.print_exc()"
                ])
                return {"new_content": '\n'.join(lines), "fix_description": "Added error handling to main.py"}
        except Exception as e:
            self.log("error", f"Failed to add error handling: {e}")
        return None

    async def _perform_error_focused_analysis(self, error_report: str):
        """Perform targeted analysis based on execution error."""
        try:
            self.log("info", "Starting error-focused integration analysis...")
            error_context = self._parse_execution_error(error_report)
            if not error_context: return
            issue = IntegrationIssue(
                issue_type="execution_error", severity="critical", file_path=error_context.get("file_path", ""),
                line_number=error_context.get("line_number"),
                description=f"Execution error: {error_context.get('error_type', 'Unknown')}",
                context=error_context, fix_confidence=0.6
            )
            self.integration_issues.append(issue)
            if self.get_config_value("auto_fix_enabled", True):
                await self._apply_comprehensive_fixes([issue])
        except Exception as e:
            self.log("error", f"Failed to perform error-focused analysis: {e}")

    def _parse_execution_error(self, error_report: str) -> Optional[Dict[str, Any]]:
        """Parse execution error to extract actionable information."""
        try:
            file_matches = re.findall(r'File "([^"]+)", line (\d+)', error_report)
            error_type_match = re.search(r'(\w+Error|\w+Exception):', error_report)
            error_type = error_type_match.group(1) if error_type_match else "Unknown"
            if file_matches:
                file_path, line_num = file_matches[-1]
                if self.project_manager and self.project_manager.active_project_path:
                    project_root = self.project_manager.active_project_path
                    try:
                        abs_file_path = Path(file_path).resolve()
                        rel_path = abs_file_path.relative_to(project_root)
                        return {
                            "file_path": str(rel_path).replace('\\', '/'), "line_number": int(line_num),
                            "error_type": error_type, "error_report": error_report
                        }
                    except ValueError: pass
        except Exception as e:
            self.log("warning", f"Could not parse execution error: {e}")
        return None

    def _reset_analysis_state(self):
        """Reset all analysis state."""
        self.code_elements.clear()
        self.integration_issues.clear()
        self.import_map.clear()
        self.definition_map.clear()
        self.usage_map.clear()
        self.fixes_applied.clear()

    async def _generate_integration_report(self):
        """Generate comprehensive integration report."""
        total_issues = len(self.integration_issues)
        total_fixes = len(self.fixes_applied)
        issue_breakdown = defaultdict(lambda: defaultdict(int))
        for issue in self.integration_issues:
            issue_breakdown[issue.issue_type][issue.severity] += 1
        self.log("info", f"Integration Analysis Report:")
        self.log("info", f"   Total Issues Found: {total_issues}")
        self.log("info", f"   Total Fixes Applied: {total_fixes}")
        self.log("info", f"   Success Rate: {(total_fixes / max(total_issues, 1)) * 100:.1f}%")
        self.log("info", f"   Code Elements Analyzed: {len(self.code_elements)}")
        if issue_breakdown:
            self.log("info", "   Issue Breakdown:")
            for issue_type, severities in issue_breakdown.items():
                self.log("info", f"     {issue_type}: {', '.join(f'{sev}: {count}' for sev, count in severities.items())}")

    def get_status_info(self) -> Dict[str, Any]:
        """Get comprehensive plugin status information."""
        return {
            "integration_active": self.state == PluginState.STARTED, "is_analyzing": self.is_analyzing,
            "service_manager_available": self.service_manager is not None,
            "project_manager_available": self.project_manager is not None,
            "llm_client_available": self.llm_client is not None,
            "statistics": {
                "code_elements": len(self.code_elements), "integration_issues": len(self.integration_issues),
                "fixes_applied": len(self.fixes_applied), "pending_requests": self.integration_queue.qsize(),
                "definitions_mapped": len(self.definition_map), "files_with_imports": len(self.import_map)
            },
            "last_integration_check": self.last_integration_check.isoformat() if self.last_integration_check else None,
            "configuration": {
                "auto_integration_check": self.get_config_value("auto_integration_check", True),
                "auto_fix_enabled": self.get_config_value("auto_fix_enabled", True),
                "fix_confidence_threshold": self.get_config_value("fix_confidence_threshold", 0.8),
                "analysis_depth": self.get_config_value("analysis_depth", "deep")
            }
        }


class ComprehensiveASTVisitor(ast.NodeVisitor):
    """Comprehensive AST visitor for detailed code analysis."""
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.elements: List[CodeElement] = []
        self.name_usage: List[Tuple[str, int]] = []
        self.current_class: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definition."""
        signature = {
            "methods": [], "attributes": [], "inheritance": [base.id for base in node.bases if isinstance(base, ast.Name)],
            "constructor_args": []
        }
        prev_class = self.current_class
        self.current_class = node.name
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_sig = {"name": item.name, "args": [arg.arg for arg in item.args.args[1:]], "line": item.lineno}
                signature["methods"].append(method_sig)
                if item.name == "__init__": signature["constructor_args"] = method_sig["args"]
        element = CodeElement(
            name=node.name, element_type="class", file_path=self.file_path, line_number=node.lineno,
            signature=signature, dependencies=set()
        )
        self.elements.append(element)
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definition."""
        if self.current_class is None:
            signature = {
                "args": [arg.arg for arg in node.args.args], "defaults": len(node.args.defaults),
                "is_async": isinstance(node, ast.AsyncFunctionDef), "returns": self._extract_return_annotation(node)
            }
            element = CodeElement(
                name=node.name, element_type="function", file_path=self.file_path, line_number=node.lineno,
                signature=signature, dependencies=set()
            )
            self.elements.append(element)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        """Visit name usage."""
        if isinstance(node.ctx, ast.Load): self.name_usage.append((node.id, node.lineno))
        self.generic_visit(node)

    def _extract_return_annotation(self, node: ast.FunctionDef) -> Optional[str]:
        """Extract return type annotation."""
        if node.returns:
            if isinstance(node.returns, ast.Name): return node.returns.id
            elif isinstance(node.returns, ast.Constant): return str(node.returns.value)
        return None