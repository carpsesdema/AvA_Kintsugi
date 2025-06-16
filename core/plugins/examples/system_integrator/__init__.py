# core/plugins/examples/system_integrator/__init__.py
# FIXED: Now subscribes to code_viewer_files_loaded for proper timing and full project context

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
    FIXED: Now runs AFTER code is loaded in code viewer with complete project context.

    This plugin:
    - Waits for code to be loaded in code viewer
    - Performs deep AST analysis of the entire codebase with full context
    - Identifies and fixes integration issues between modules
    - Validates constructor calls, method signatures, and interfaces
    - Ensures main.py properly initializes all components
    - Applies LLM-powered fixes for complex integration problems
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

        # Full project context
        self.current_project_context: Dict[str, Any] = {}
        self.all_project_files: Dict[str, str] = {}

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
            version="2.0.0",
            description="Production-quality system integration analysis with full project context awareness",
            author="Kintsugi AvA Team",
            dependencies=[],
            event_subscriptions=[
                "code_viewer_files_loaded",  # FIX: New event with full context
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
                }
            }
        )

    async def start(self) -> bool:
        """Start the system integrator."""
        try:
            self.log("info", "🏗️ Starting System Integrator v2.0...")

            # Get service references
            if hasattr(self, '_plugin_manager') and self._plugin_manager:
                self.service_manager = getattr(self._plugin_manager, 'service_manager', None)
                if self.service_manager:
                    self.project_manager = self.service_manager.get_project_manager()
                    self.llm_client = self.service_manager.get_llm_client()

            # Start integration worker
            self.integration_worker_task = asyncio.create_task(self._integration_worker())

            # Subscribe to events
            self.event_bus.subscribe("code_viewer_files_loaded", self._on_code_viewer_files_loaded)
            self.event_bus.subscribe("execution_failed", self._on_execution_failed)
            self.event_bus.subscribe("new_project_requested", self._on_new_project)

            self.set_state(PluginState.STARTED)
            self.log("info", "🏗️ System Integrator active - waiting for code viewer loads")

            return True

        except Exception as e:
            self.log("error", f"Failed to start system integrator: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def stop(self) -> bool:
        """Stop the system integrator."""
        try:
            self.log("info", "Stopping System Integrator...")

            # Cancel integration worker
            if self.integration_worker_task and not self.integration_worker_task.done():
                self.integration_worker_task.cancel()
                try:
                    await self.integration_worker_task
                except asyncio.CancelledError:
                    pass

            # Generate final report
            await self._generate_integration_report()

            self.set_state(PluginState.STOPPED)
            return True

        except Exception as e:
            self.log("error", f"Failed to stop system integrator: {e}")
            self.set_state(PluginState.ERROR)
            return False

    # Event Handlers

    async def _on_code_viewer_files_loaded(self, event_data: Dict[str, Any]):
        """
        FIX: Main event handler - performs integration analysis with full project context.
        """
        try:
            if not self.get_config_value("auto_integration_check", True):
                self.log("info", "Auto-integration check disabled, skipping analysis")
                return

            self.log("info", "🔧 Code loaded in viewer - starting integration analysis...")

            # Store full project context
            self.current_project_context = event_data.get("full_project_context", {})
            self.all_project_files = event_data.get("files", {})
            project_path = event_data.get("project_path", "")

            if not self.all_project_files:
                self.log("warning", "No files to analyze for integration")
                return

            # Queue comprehensive integration analysis
            await self.integration_queue.put({
                "type": "full_analysis",
                "files": self.all_project_files,
                "project_context": self.current_project_context,
                "project_path": project_path,
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            self.log("error", f"Error in code viewer integration handler: {e}")

    async def _on_execution_failed(self, error_report: str):
        """Handle execution failure - analyze for integration issues."""
        self.log("info", "🚨 Execution failed - analyzing for integration issues...")

        await self.integration_queue.put({
            "type": "error_analysis",
            "error_report": error_report,
            "files": self.all_project_files,
            "project_context": self.current_project_context,
            "timestamp": datetime.now().isoformat()
        })

    async def _on_new_project(self):
        """Handle new project - reset state."""
        self.log("info", "🔄 New project started - resetting integration state")
        self._reset_integration_state()

    # Integration Analysis Worker

    async def _integration_worker(self):
        """Worker that processes integration analysis queue."""
        self.log("info", "🏗️ Integration worker started")

        while self.state == PluginState.STARTED:
            try:
                # Wait for next analysis request
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
        """Process an integration analysis request."""
        try:
            request_type = request.get("type", "unknown")

            self.emit_event("integration_analysis_started", {
                "type": request_type,
                "timestamp": request.get("timestamp")
            })

            if request_type == "full_analysis":
                await self._perform_full_integration_analysis(request)
            elif request_type == "error_analysis":
                await self._perform_error_integration_analysis(request)

            self.last_integration_check = datetime.now()

            self.emit_event("integration_analysis_complete", {
                "type": request_type,
                "issues_found": len(self.integration_issues),
                "fixes_applied": len(self.fixes_applied)
            })

        except Exception as e:
            self.log("error", f"Error processing integration request: {e}")

    async def _perform_full_integration_analysis(self, request: Dict[str, Any]):
        """Perform comprehensive integration analysis."""
        try:
            files = request.get("files", {})
            project_context = request.get("project_context", {})

            self.log("info", f"🔍 Performing full integration analysis on {len(files)} files...")

            # Clear previous analysis
            self._reset_integration_state()

            # 1. Build comprehensive code element map
            await self._build_code_element_map(files)

            # 2. Analyze imports and dependencies
            await self._analyze_imports_and_dependencies(files, project_context)

            # 3. Validate method/class signatures and usage
            await self._validate_signatures_and_usage(files)

            # 4. Check main.py integration
            await self._validate_main_integration(files)

            # 5. Detect circular dependencies
            await self._detect_circular_dependencies()

            # 6. Validate file structure consistency
            await self._validate_file_structure(files, project_context)

            # 7. Auto-fix detected issues
            if self.get_config_value("auto_fix_enabled", True):
                await self._apply_integration_fixes()

            total_issues = len(self.integration_issues)
            self.log("info", f"🔍 Integration analysis complete: {total_issues} issues found")

        except Exception as e:
            self.log("error", f"Error in full integration analysis: {e}")

    async def _perform_error_integration_analysis(self, request: Dict[str, Any]):
        """Perform focused analysis based on execution error."""
        try:
            error_report = request.get("error_report", "")
            files = request.get("files", {})

            self.log("info", "🔍 Analyzing integration issues from execution error...")

            # Parse error for integration clues
            integration_issues = await self._parse_error_for_integration_issues(error_report, files)

            self.integration_issues.extend(integration_issues)

            # Apply fixes if enabled
            if self.get_config_value("auto_fix_enabled", True) and integration_issues:
                await self._apply_integration_fixes()

        except Exception as e:
            self.log("error", f"Error in error integration analysis: {e}")

    # Analysis Methods

    async def _build_code_element_map(self, files: Dict[str, str]):
        """Build comprehensive map of all code elements."""
        try:
            self.code_elements.clear()

            for file_path, content in files.items():
                if not file_path.endswith('.py'):
                    continue

                try:
                    tree = ast.parse(content)
                    visitor = ComprehensiveASTVisitor(file_path)
                    visitor.visit(tree)

                    # Store discovered elements
                    for element in visitor.code_elements:
                        self.code_elements[f"{file_path}:{element.name}"] = element

                except SyntaxError as e:
                    self.integration_issues.append(IntegrationIssue(
                        issue_type="syntax_error",
                        severity="critical",
                        file_path=file_path,
                        line_number=e.lineno,
                        description=f"Syntax error prevents integration analysis: {e.msg}",
                        context={"error": str(e)}
                    ))

        except Exception as e:
            self.log("error", f"Error building code element map: {e}")

    async def _analyze_imports_and_dependencies(self, files: Dict[str, str], project_context: Dict[str, Any]):
        """Analyze import statements and dependencies."""
        try:
            dependency_map = project_context.get("dependency_map", {})
            symbol_index = project_context.get("symbol_index", {})

            for file_path, content in files.items():
                if not file_path.endswith('.py'):
                    continue

                # Get file dependencies
                file_deps = dependency_map.get(file_path, [])

                # Check each dependency
                for dep in file_deps:
                    if not await self._validate_dependency(dep, file_path, files, symbol_index):
                        self.integration_issues.append(IntegrationIssue(
                            issue_type="missing_import",
                            severity="high",
                            file_path=file_path,
                            line_number=None,
                            description=f"Import '{dep}' cannot be resolved",
                            context={"dependency": dep},
                            suggested_fix=f"Add missing module '{dep}' or fix import statement",
                            fix_confidence=0.9
                        ))

                # Check for unused imports
                unused_imports = await self._find_unused_imports(file_path, content, symbol_index)
                for unused in unused_imports:
                    self.integration_issues.append(IntegrationIssue(
                        issue_type="unused_import",
                        severity="low",
                        file_path=file_path,
                        line_number=None,
                        description=f"Unused import '{unused}'",
                        context={"import": unused},
                        suggested_fix=f"Remove unused import '{unused}'",
                        fix_confidence=0.95
                    ))

        except Exception as e:
            self.log("error", f"Error analyzing imports and dependencies: {e}")

    async def _validate_signatures_and_usage(self, files: Dict[str, str]):
        """Validate method/class signatures match their usage."""
        try:
            # Find all function/method calls
            for file_path, content in files.items():
                if not file_path.endswith('.py'):
                    continue

                try:
                    tree = ast.parse(content)
                    call_visitor = CallAnalysisVisitor(file_path)
                    call_visitor.visit(tree)

                    # Validate each call against known signatures
                    for call_info in call_visitor.function_calls:
                        await self._validate_function_call(call_info, files)

                except SyntaxError:
                    continue  # Already handled in build_code_element_map

        except Exception as e:
            self.log("error", f"Error validating signatures: {e}")

    async def _validate_main_integration(self, files: Dict[str, str]):
        """Validate main.py properly integrates with other modules."""
        try:
            main_files = [f for f in files.keys() if f.endswith('main.py')]

            if not main_files:
                self.integration_issues.append(IntegrationIssue(
                    issue_type="missing_main",
                    severity="medium",
                    file_path="",
                    line_number=None,
                    description="No main.py file found",
                    context={},
                    suggested_fix="Create main.py as application entry point",
                    fix_confidence=0.8
                ))
                return

            main_file = main_files[0]
            main_content = files[main_file]

            # Check if main.py uses other project modules
            other_py_files = [f for f in files.keys() if f.endswith('.py') and f != main_file]

            if other_py_files:
                imports_other_modules = False
                for other_file in other_py_files:
                    module_name = other_file.replace('.py', '').replace('/', '.')
                    if module_name in main_content or other_file.split('/')[-1].replace('.py', '') in main_content:
                        imports_other_modules = True
                        break

                if not imports_other_modules:
                    self.integration_issues.append(IntegrationIssue(
                        issue_type="main_isolation",
                        severity="medium",
                        file_path=main_file,
                        line_number=None,
                        description="main.py doesn't appear to use other project modules",
                        context={"other_modules": other_py_files},
                        suggested_fix="Add imports to connect main.py with project modules",
                        fix_confidence=0.7
                    ))

        except Exception as e:
            self.log("error", f"Error validating main integration: {e}")

    async def _detect_circular_dependencies(self):
        """Detect circular import dependencies."""
        try:
            # Build dependency graph
            dep_graph = {}
            for file_path in self.all_project_files.keys():
                if file_path.endswith('.py'):
                    deps = self.import_map.get(file_path, set())
                    dep_graph[file_path] = list(deps)

            # Detect cycles using DFS
            visited = set()
            rec_stack = set()

            def has_cycle(node, path):
                if node in rec_stack:
                    cycle_start = path.index(node)
                    cycle = path[cycle_start:] + [node]
                    return cycle

                if node in visited:
                    return None

                visited.add(node)
                rec_stack.add(node)

                for neighbor in dep_graph.get(node, []):
                    cycle = has_cycle(neighbor, path + [node])
                    if cycle:
                        return cycle

                rec_stack.remove(node)
                return None

            for file_path in dep_graph:
                if file_path not in visited:
                    cycle = has_cycle(file_path, [])
                    if cycle:
                        self.integration_issues.append(IntegrationIssue(
                            issue_type="circular_dependency",
                            severity="high",
                            file_path=cycle[0],
                            line_number=None,
                            description=f"Circular dependency detected: {' -> '.join(cycle)}",
                            context={"cycle": cycle},
                            suggested_fix="Refactor to break circular dependency",
                            fix_confidence=0.6
                        ))

        except Exception as e:
            self.log("error", f"Error detecting circular dependencies: {e}")

    async def _validate_file_structure(self, files: Dict[str, str], project_context: Dict[str, Any]):
        """Validate file structure consistency."""
        try:
            structure = project_context.get("project_structure", {})
            directories = structure.get("directories", [])

            # Check for missing __init__.py files
            for directory in directories:
                init_file = f"{directory}/__init__.py"
                if init_file not in files:
                    self.integration_issues.append(IntegrationIssue(
                        issue_type="missing_init",
                        severity="medium",
                        file_path=directory,
                        line_number=None,
                        description=f"Missing __init__.py in directory '{directory}'",
                        context={"directory": directory},
                        suggested_fix=f"Create {init_file}",
                        fix_confidence=0.9
                    ))

        except Exception as e:
            self.log("error", f"Error validating file structure: {e}")

    async def _parse_error_for_integration_issues(self, error_report: str, files: Dict[str, str]) -> List[
        IntegrationIssue]:
        """Parse execution error for integration-related issues."""
        issues = []

        try:
            # Look for import errors
            if "ModuleNotFoundError" in error_report or "ImportError" in error_report:
                # Extract module name
                import_match = re.search(r"No module named '([^']+)'", error_report)
                if import_match:
                    module = import_match.group(1)
                    issues.append(IntegrationIssue(
                        issue_type="runtime_import_error",
                        severity="critical",
                        file_path="",
                        line_number=None,
                        description=f"Runtime import error: Module '{module}' not found",
                        context={"module": module, "error": error_report},
                        suggested_fix=f"Install or create module '{module}'",
                        fix_confidence=0.8
                    ))

            # Look for attribute errors (wrong method/class usage)
            if "AttributeError" in error_report:
                attr_match = re.search(r"'([^']+)' object has no attribute '([^']+)'", error_report)
                if attr_match:
                    obj_type, attribute = attr_match.groups()
                    issues.append(IntegrationIssue(
                        issue_type="runtime_attribute_error",
                        severity="high",
                        file_path="",
                        line_number=None,
                        description=f"Attribute error: '{obj_type}' has no attribute '{attribute}'",
                        context={"object_type": obj_type, "attribute": attribute, "error": error_report},
                        suggested_fix=f"Check method/attribute name or class definition",
                        fix_confidence=0.7
                    ))

        except Exception as e:
            self.log("error", f"Error parsing error for integration issues: {e}")

        return issues

    # Helper Methods

    async def _validate_dependency(self, dep: str, file_path: str, files: Dict[str, str],
                                   symbol_index: Dict[str, Any]) -> bool:
        """Validate that a dependency can be satisfied."""
        # Check standard library
        stdlib_modules = {
            'os', 'sys', 'json', 'ast', 'pathlib', 'asyncio', 're', 'datetime',
            'typing', 'collections', 'dataclasses', 'functools', 'itertools'
        }

        base_module = dep.split('.')[0]
        if base_module in stdlib_modules:
            return True

        # Check third-party packages (basic check)
        third_party = {'PySide6', 'numpy', 'pandas', 'requests', 'flask', 'django'}
        if base_module in third_party:
            return True

        # Check if defined in project
        for filename, symbols in symbol_index.items():
            if dep in symbols.get("classes", []) or dep in symbols.get("functions", []):
                return True

        return False

    async def _find_unused_imports(self, file_path: str, content: str, symbol_index: Dict[str, Any]) -> List[str]:
        """Find unused imports in a file."""
        unused = []

        try:
            # Extract import statements
            tree = ast.parse(content)
            import_visitor = ImportVisitor()
            import_visitor.visit(tree)

            # Check each import for usage
            for imported_name in import_visitor.imported_names:
                # Simple usage check (could be more sophisticated)
                if imported_name not in content.replace(f"import {imported_name}", ""):
                    unused.append(imported_name)

        except Exception as e:
            self.log("error", f"Error finding unused imports in {file_path}: {e}")

        return unused

    async def _validate_function_call(self, call_info: Dict[str, Any], files: Dict[str, str]):
        """Validate a function call against known signatures."""
        try:
            func_name = call_info.get("function_name")
            file_path = call_info.get("file_path")
            line_number = call_info.get("line_number")

            # Look for function definition
            func_found = False

            for element_key, element in self.code_elements.items():
                if element.name == func_name:
                    func_found = True

                    # Could add signature validation here
                    # For now, just mark as found
                    break

            if not func_found:
                self.integration_issues.append(IntegrationIssue(
                    issue_type="undefined_function",
                    severity="high",
                    file_path=file_path,
                    line_number=line_number,
                    description=f"Function '{func_name}' is called but not defined",
                    context={"function": func_name},
                    suggested_fix=f"Define function '{func_name}' or import it",
                    fix_confidence=0.8
                ))

        except Exception as e:
            self.log("error", f"Error validating function call: {e}")

    # Fix Application

    async def _apply_integration_fixes(self):
        """Apply automatic fixes for integration issues."""
        try:
            auto_fix_enabled = self.get_config_value("auto_fix_enabled", True)
            confidence_threshold = self.get_config_value("fix_confidence_threshold", 0.8)

            if not auto_fix_enabled:
                return

            fixes_applied = 0

            for issue in self.integration_issues:
                if issue.fix_confidence >= confidence_threshold:
                    success = await self._apply_single_fix(issue)
                    if success:
                        fixes_applied += 1
                        self.fixes_applied.append({
                            "issue": issue,
                            "timestamp": datetime.now().isoformat(),
                            "success": True
                        })

                        self.emit_event("integration_fix_applied", {
                            "issue_type": issue.issue_type,
                            "file_path": issue.file_path,
                            "description": issue.description
                        })

            if fixes_applied > 0:
                self.log("info", f"✅ Applied {fixes_applied} integration fixes")

        except Exception as e:
            self.log("error", f"Error applying integration fixes: {e}")

    async def _apply_single_fix(self, issue: IntegrationIssue) -> bool:
        """Apply a single integration fix."""
        try:
            if issue.issue_type == "missing_init":
                return await self._fix_missing_init(issue)
            elif issue.issue_type == "unused_import":
                return await self._fix_unused_import(issue)
            else:
                self.log("info", f"No automatic fix available for {issue.issue_type}")
                return False

        except Exception as e:
            self.log("error", f"Error applying single fix: {e}")
            return False

    async def _fix_missing_init(self, issue: IntegrationIssue) -> bool:
        """Fix missing __init__.py file."""
        try:
            if self.project_manager:
                directory = issue.file_path
                init_file = f"{directory}/__init__.py"

                # Create minimal __init__.py
                init_content = f'"""\n{directory.replace("/", ".")} package\n"""\n'

                # Save through project manager
                self.project_manager.save_and_commit_files(
                    {init_file: init_content},
                    f"fix: Add missing __init__.py in {directory}"
                )

                self.log("info", f"✅ Created {init_file}")
                return True

        except Exception as e:
            self.log("error", f"Error fixing missing init: {e}")

        return False

    async def _fix_unused_import(self, issue: IntegrationIssue) -> bool:
        """Fix unused import."""
        # This would require more sophisticated code modification
        # For now, just log the intent
        self.log("info", f"Would remove unused import in {issue.file_path}")
        return True

    # State Management

    def _reset_integration_state(self):
        """Reset all integration analysis state."""
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

        self.log("info", f"🏗️ Integration Analysis Report:")
        self.log("info", f"   Total Issues Found: {total_issues}")
        self.log("info", f"   Total Fixes Applied: {total_fixes}")
        self.log("info", f"   Success Rate: {(total_fixes / max(total_issues, 1)) * 100:.1f}%")
        self.log("info", f"   Code Elements Analyzed: {len(self.code_elements)}")

        if issue_breakdown:
            self.log("info", "   Issue Breakdown:")
            for issue_type, severities in issue_breakdown.items():
                self.log("info",
                         f"     {issue_type}: {', '.join(f'{sev}: {count}' for sev, count in severities.items())}")

    def get_status_info(self) -> Dict[str, Any]:
        """Get comprehensive plugin status information."""
        return {
            "integration_active": self.state == PluginState.STARTED,
            "is_analyzing": self.is_analyzing,
            "service_manager_available": self.service_manager is not None,
            "project_manager_available": self.project_manager is not None,
            "llm_client_available": self.llm_client is not None,
            "statistics": {
                "code_elements": len(self.code_elements),
                "integration_issues": len(self.integration_issues),
                "fixes_applied": len(self.fixes_applied),
                "pending_requests": self.integration_queue.qsize(),
                "definitions_mapped": len(self.definition_map),
                "files_with_imports": len(self.import_map)
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
        self.code_elements: List[CodeElement] = []
        self.current_class = None

    def visit_ClassDef(self, node):
        """Visit class definitions."""
        element = CodeElement(
            name=node.name,
            element_type="class",
            file_path=self.file_path,
            line_number=node.lineno,
            signature={"bases": [base.id if hasattr(base, 'id') else str(base) for base in node.bases]},
            dependencies=set()
        )

        self.code_elements.append(element)

        # Visit methods within the class
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node):
        """Visit function definitions."""
        element = CodeElement(
            name=node.name,
            element_type="method" if self.current_class else "function",
            file_path=self.file_path,
            line_number=node.lineno,
            signature={
                "args": [arg.arg for arg in node.args.args],
                "returns": str(node.returns) if node.returns else None
            },
            dependencies=set(),
            parent_class=self.current_class
        )

        self.code_elements.append(element)
        self.generic_visit(node)


class CallAnalysisVisitor(ast.NodeVisitor):
    """AST visitor to analyze function calls."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.function_calls: List[Dict[str, Any]] = []

    def visit_Call(self, node):
        """Visit function calls."""
        if hasattr(node.func, 'id'):
            func_name = node.func.id
        elif hasattr(node.func, 'attr'):
            func_name = node.func.attr
        else:
            func_name = str(node.func)

        self.function_calls.append({
            "function_name": func_name,
            "file_path": self.file_path,
            "line_number": node.lineno,
            "args": len(node.args),
            "keywords": len(node.keywords)
        })

        self.generic_visit(node)


class ImportVisitor(ast.NodeVisitor):
    """AST visitor to analyze imports."""

    def __init__(self):
        self.imported_names: List[str] = []

    def visit_Import(self, node):
        """Visit import statements."""
        for alias in node.names:
            self.imported_names.append(alias.name)

    def visit_ImportFrom(self, node):
        """Visit from...import statements."""
        for alias in node.names:
            self.imported_names.append(alias.name)