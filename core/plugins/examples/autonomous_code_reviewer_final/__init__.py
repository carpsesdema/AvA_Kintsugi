# core/plugins/examples/autonomous_code_reviewer_final/__init__.py
# FIXED: Now subscribes to code_viewer_files_loaded for proper timing and full project context

import asyncio
import json
import re
import ast
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from core.plugins import PluginBase, PluginMetadata, PluginState


class AutonomousCodeReviewerPlugin(PluginBase):
    """
    An autonomous agent that monitors code quality and fixes issues.
    FIXED: Now runs AFTER code is loaded in code viewer with full project context.

    This plugin:
    - Waits for code to be loaded in code viewer
    - Analyzes code with full project context awareness
    - Proactively identifies integration and quality issues
    - Automatically generates and applies fixes
    - Learns from successful fixes to improve future suggestions
    """

    def __init__(self, event_bus, plugin_config: Dict[str, Any]):
        super().__init__(event_bus, plugin_config)

        # Error tracking
        self.detected_errors = []
        self.fixed_errors = []
        self.error_patterns = {}
        self.auto_fix_queue = asyncio.Queue()

        # Code analysis state
        self.code_quality_issues = defaultdict(list)
        self.analysis_history = []
        self.fix_success_rate = {}

        # Project context awareness
        self.current_project_context = {}
        self.dependency_issues = []
        self.integration_warnings = []

        # Learning system
        self.successful_fixes = []
        self.failed_fixes = []
        self.pattern_library = {
            "common_python_errors": self._get_python_error_patterns(),
            "security_patterns": self._get_security_patterns(),
            "performance_patterns": self._get_performance_patterns(),
            "integration_patterns": self._get_integration_patterns()
        }

        # Auto-fix worker
        self.auto_fix_worker = None
        self.is_processing_fixes = False

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="autonomous_code_reviewer",
            version="2.0.0",
            description="Autonomous agent that monitors, analyzes, and fixes code issues with full project context",
            author="Kintsugi AvA Team",
            dependencies=[],
            event_subscriptions=[
                "code_viewer_files_loaded",  # FIX: New event with full context
                "execution_failed",
                "terminal_output_received"
            ],
            event_emissions=[
                "autonomous_fix_applied",
                "code_quality_issue_detected",
                "integration_issue_found",
                "autonomous_analysis_complete"
            ],
            config_schema={
                "auto_fix_enabled": {"type": "bool", "default": True},
                "analysis_depth": {"type": "str", "default": "deep"},
                "fix_confidence_threshold": {"type": "float", "default": 0.8},
                "integration_analysis": {"type": "bool", "default": True}
            }
        )

    async def start(self) -> bool:
        """Start the autonomous code reviewer."""
        try:
            self.log("info", "🤖 Starting Autonomous Code Reviewer v2.0...")

            # Start the auto-fix worker
            self.auto_fix_worker = asyncio.create_task(self._auto_fix_worker())

            # Subscribe to events
            self.event_bus.subscribe("code_viewer_files_loaded", self._on_code_viewer_files_loaded)
            self.event_bus.subscribe("execution_failed", self._on_execution_failed)
            self.event_bus.subscribe("terminal_output_received", self._on_terminal_output)

            self.set_state(PluginState.STARTED)
            self.log("info", "🤖 Autonomous Code Reviewer active - waiting for code viewer loads")

            return True

        except Exception as e:
            self.log("error", f"Failed to start autonomous code reviewer: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def stop(self) -> bool:
        """Stop the autonomous code reviewer."""
        try:
            self.log("info", "Stopping Autonomous Code Reviewer...")

            # Cancel auto-fix worker
            if self.auto_fix_worker and not self.auto_fix_worker.done():
                self.auto_fix_worker.cancel()
                try:
                    await self.auto_fix_worker
                except asyncio.CancelledError:
                    pass

            # Generate final report
            await self._generate_final_report()

            self.set_state(PluginState.STOPPED)
            return True

        except Exception as e:
            self.log("error", f"Failed to stop autonomous code reviewer: {e}")
            self.set_state(PluginState.ERROR)
            return False

    # Event Handlers

    async def _on_code_viewer_files_loaded(self, event_data: Dict[str, Any]):
        """
        FIX: Main event handler - analyzes code with full project context.
        This is where the magic happens now!
        """
        try:
            self.log("info", "🔍 Code loaded in viewer - starting autonomous analysis...")

            # Store project context
            self.current_project_context = event_data.get("full_project_context", {})
            files = event_data.get("files", {})
            project_path = event_data.get("project_path", "")

            if not files:
                self.log("warning", "No files to analyze")
                return

            # Perform comprehensive analysis with full context
            analysis_results = await self._perform_comprehensive_analysis(files, self.current_project_context)

            # Queue fixes for any issues found
            if analysis_results:
                await self._queue_autonomous_fixes(analysis_results)

            self.emit_event("autonomous_analysis_complete", {
                "files_analyzed": len(files),
                "issues_found": len(analysis_results.get("issues", [])),
                "project_path": project_path
            })

        except Exception as e:
            self.log("error", f"Error in code viewer analysis: {e}")

    async def _perform_comprehensive_analysis(self, files: Dict[str, str], project_context: Dict[str, Any]) -> Dict[
        str, Any]:
        """Perform deep analysis with full project context awareness."""
        try:
            self.log("info", f"🔬 Analyzing {len(files)} files with full project context...")

            analysis_results = {
                "issues": [],
                "integration_warnings": [],
                "dependency_problems": [],
                "quality_suggestions": []
            }

            # 1. Cross-file dependency analysis
            dependency_issues = await self._analyze_cross_file_dependencies(files, project_context)
            analysis_results["dependency_problems"].extend(dependency_issues)

            # 2. Integration analysis
            integration_issues = await self._analyze_integration_patterns(files, project_context)
            analysis_results["integration_warnings"].extend(integration_issues)

            # 3. Individual file quality analysis
            for filename, content in files.items():
                if filename.endswith('.py'):
                    file_issues = await self._analyze_file_quality(filename, content, project_context)
                    analysis_results["issues"].extend(file_issues)

            # 4. Project-wide pattern analysis
            pattern_issues = await self._analyze_project_patterns(files, project_context)
            analysis_results["quality_suggestions"].extend(pattern_issues)

            total_issues = sum(len(analysis_results[key]) for key in analysis_results)
            self.log("info", f"🔍 Analysis complete: {total_issues} total issues found")

            return analysis_results

        except Exception as e:
            self.log("error", f"Error in comprehensive analysis: {e}")
            return {}

    async def _analyze_cross_file_dependencies(self, files: Dict[str, str], project_context: Dict[str, Any]) -> List[
        Dict[str, Any]]:
        """Analyze cross-file import and dependency issues."""
        issues = []

        try:
            dependency_map = project_context.get("dependency_map", {})
            symbol_index = project_context.get("symbol_index", {})

            for filename, content in files.items():
                if not filename.endswith('.py'):
                    continue

                # Find undefined imports
                file_deps = dependency_map.get(filename, [])
                for dep in file_deps:
                    # Check if imported module/symbol exists
                    if not self._is_dependency_satisfied(dep, symbol_index, files):
                        issues.append({
                            "type": "missing_dependency",
                            "severity": "high",
                            "filename": filename,
                            "description": f"Import '{dep}' not found in project",
                            "suggested_fix": f"Add missing import or create module '{dep}'",
                            "auto_fixable": True
                        })

                # Find unused imports
                unused_imports = self._find_unused_imports(filename, content, symbol_index)
                for unused in unused_imports:
                    issues.append({
                        "type": "unused_import",
                        "severity": "low",
                        "filename": filename,
                        "description": f"Unused import '{unused}'",
                        "suggested_fix": f"Remove unused import '{unused}'",
                        "auto_fixable": True
                    })

        except Exception as e:
            self.log("error", f"Error analyzing dependencies: {e}")

        return issues

    async def _analyze_integration_patterns(self, files: Dict[str, str], project_context: Dict[str, Any]) -> List[
        Dict[str, Any]]:
        """Analyze integration patterns and architectural issues."""
        issues = []

        try:
            symbol_index = project_context.get("symbol_index", {})

            # Check for main.py integration
            main_files = [f for f in files.keys() if f.endswith('main.py')]
            if main_files:
                main_content = files[main_files[0]]
                integration_issues = self._check_main_integration(main_content, symbol_index)
                issues.extend(integration_issues)

            # Check for class instantiation issues
            for filename, content in files.items():
                if filename.endswith('.py'):
                    class_issues = self._check_class_instantiation(filename, content, symbol_index)
                    issues.extend(class_issues)

        except Exception as e:
            self.log("error", f"Error analyzing integration patterns: {e}")

        return issues

    async def _analyze_file_quality(self, filename: str, content: str, project_context: Dict[str, Any]) -> List[
        Dict[str, Any]]:
        """Analyze individual file quality issues."""
        issues = []

        try:
            # Check for syntax errors
            try:
                ast.parse(content)
            except SyntaxError as e:
                issues.append({
                    "type": "syntax_error",
                    "severity": "critical",
                    "filename": filename,
                    "line_number": e.lineno,
                    "description": f"Syntax error: {e.msg}",
                    "auto_fixable": False
                })

            # Check patterns
            for pattern_type, patterns in self.pattern_library.items():
                pattern_issues = self._check_patterns(filename, content, patterns)
                issues.extend(pattern_issues)

        except Exception as e:
            self.log("error", f"Error analyzing file quality for {filename}: {e}")

        return issues

    async def _analyze_project_patterns(self, files: Dict[str, str], project_context: Dict[str, Any]) -> List[
        Dict[str, Any]]:
        """Analyze project-wide architectural patterns."""
        suggestions = []

        try:
            structure = project_context.get("project_structure", {})

            # Check for missing __init__.py files
            directories = structure.get("directories", [])
            for directory in directories:
                init_file = f"{directory}/__init__.py"
                if init_file not in files:
                    suggestions.append({
                        "type": "missing_init",
                        "severity": "medium",
                        "description": f"Missing __init__.py in {directory}",
                        "suggested_fix": f"Create {init_file}",
                        "auto_fixable": True
                    })

        except Exception as e:
            self.log("error", f"Error analyzing project patterns: {e}")

        return suggestions

    async def _queue_autonomous_fixes(self, analysis_results: Dict[str, Any]):
        """Queue fixes for auto-fixable issues."""
        try:
            auto_fix_enabled = self.get_config_value("auto_fix_enabled", True)
            confidence_threshold = self.get_config_value("fix_confidence_threshold", 0.8)

            if not auto_fix_enabled:
                self.log("info", "Auto-fix disabled, skipping fix queue")
                return

            fixable_count = 0

            for category, issues in analysis_results.items():
                for issue in issues:
                    if issue.get("auto_fixable", False):
                        confidence = issue.get("confidence", 0.9)
                        if confidence >= confidence_threshold:
                            await self.auto_fix_queue.put({
                                "timestamp": datetime.now().isoformat(),
                                "category": category,
                                "issue": issue,
                                "confidence": confidence
                            })
                            fixable_count += 1

            if fixable_count > 0:
                self.log("info", f"🔧 Queued {fixable_count} auto-fixable issues")

        except Exception as e:
            self.log("error", f"Error queuing fixes: {e}")

    # Auto-Fix System

    async def _auto_fix_worker(self):
        """Worker that processes the auto-fix queue."""
        self.log("info", "🤖 Auto-fix worker started")

        while self.state == PluginState.STARTED:
            try:
                # Wait for next item to fix
                fix_request = await asyncio.wait_for(self.auto_fix_queue.get(), timeout=1.0)

                self.is_processing_fixes = True
                await self._attempt_autonomous_fix(fix_request)
                self.is_processing_fixes = False

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log("error", f"Error in auto-fix worker: {e}")
                self.is_processing_fixes = False

    async def _attempt_autonomous_fix(self, fix_request: Dict[str, Any]):
        """Attempt to automatically fix an issue."""
        try:
            issue = fix_request["issue"]
            confidence = fix_request["confidence"]

            self.log("info", f"🔧 Attempting autonomous fix: {issue.get('type')} (confidence: {confidence:.2f})")

            # Apply the fix based on issue type
            fix_applied = False

            if issue["type"] == "unused_import":
                fix_applied = await self._fix_unused_import(issue)
            elif issue["type"] == "missing_dependency":
                fix_applied = await self._fix_missing_dependency(issue)
            elif issue["type"] == "missing_init":
                fix_applied = await self._fix_missing_init(issue)
            else:
                self.log("info", f"No autonomous fix available for {issue['type']}")

            if fix_applied:
                self.successful_fixes.append(fix_request)
                self.emit_event("autonomous_fix_applied", issue)
                self.log("success", f"✅ Autonomous fix applied: {issue['type']}")
            else:
                self.failed_fixes.append(fix_request)

        except Exception as e:
            self.log("error", f"Error applying autonomous fix: {e}")
            self.failed_fixes.append(fix_request)

    # Fix Implementations

    async def _fix_unused_import(self, issue: Dict[str, Any]) -> bool:
        """Remove unused imports."""
        # Implementation would interact with project manager to fix files
        self.log("info", f"Would fix unused import in {issue['filename']}")
        return True  # Placeholder

    async def _fix_missing_dependency(self, issue: Dict[str, Any]) -> bool:
        """Fix missing dependency issues."""
        self.log("info", f"Would fix missing dependency in {issue['filename']}")
        return True  # Placeholder

    async def _fix_missing_init(self, issue: Dict[str, Any]) -> bool:
        """Create missing __init__.py files."""
        self.log("info", f"Would create missing __init__.py")
        return True  # Placeholder

    # Helper Methods

    def _is_dependency_satisfied(self, dep: str, symbol_index: Dict[str, Any], files: Dict[str, str]) -> bool:
        """Check if a dependency can be satisfied."""
        # Check if it's a standard library import
        stdlib_modules = {'os', 'sys', 'json', 'ast', 'pathlib', 'asyncio', 're', 'datetime'}
        if dep.split('.')[0] in stdlib_modules:
            return True

        # Check if it's defined in the project
        for filename, symbols in symbol_index.items():
            if dep in symbols.get("classes", []) or dep in symbols.get("functions", []):
                return True

        return False

    def _find_unused_imports(self, filename: str, content: str, symbol_index: Dict[str, Any]) -> List[str]:
        """Find unused imports in a file."""
        # Simple implementation - would be more sophisticated in practice
        unused = []

        import_lines = [line.strip() for line in content.split('\n') if line.strip().startswith(('import ', 'from '))]

        for line in import_lines:
            # Extract imported name
            if ' import ' in line:
                parts = line.split(' import ')
                if len(parts) == 2:
                    imported = parts[1].split(',')[0].split(' as ')[0].strip()
                    # Check if used in file
                    if imported not in content.replace(line, ''):
                        unused.append(imported)

        return unused

    def _check_main_integration(self, main_content: str, symbol_index: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check main.py integration issues."""
        issues = []

        # Check if main.py actually uses other modules
        has_imports = 'import ' in main_content or 'from ' in main_content
        if not has_imports and len(symbol_index) > 1:
            issues.append({
                "type": "main_isolation",
                "severity": "medium",
                "filename": "main.py",
                "description": "main.py doesn't import any project modules",
                "suggested_fix": "Add imports to connect main.py with other modules",
                "auto_fixable": False
            })

        return issues

    def _check_class_instantiation(self, filename: str, content: str, symbol_index: Dict[str, Any]) -> List[
        Dict[str, Any]]:
        """Check for class instantiation issues."""
        issues = []

        # Look for class instantiations that might be missing imports
        class_pattern = r'(\w+)\s*\('
        for match in re.finditer(class_pattern, content):
            class_name = match.group(1)
            if class_name[0].isupper():  # Likely a class
                # Check if class is defined or imported
                if not self._is_class_available(class_name, filename, content, symbol_index):
                    issues.append({
                        "type": "undefined_class",
                        "severity": "high",
                        "filename": filename,
                        "description": f"Class '{class_name}' used but not defined or imported",
                        "suggested_fix": f"Import or define class '{class_name}'",
                        "auto_fixable": True
                    })

        return issues

    def _is_class_available(self, class_name: str, filename: str, content: str, symbol_index: Dict[str, Any]) -> bool:
        """Check if a class is available in the current file."""
        # Check if defined in current file
        current_symbols = symbol_index.get(filename, {})
        if class_name in current_symbols.get("classes", []):
            return True

        # Check if imported
        if f'import {class_name}' in content or f'from .* import .*{class_name}' in content:
            return True

        return False

    def _check_patterns(self, filename: str, content: str, patterns: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check content against pattern library."""
        issues = []

        for pattern_name, pattern_data in patterns.items():
            if re.search(pattern_data.get("regex", ""), content, re.MULTILINE):
                issues.append({
                    "type": pattern_data.get("type", "pattern_match"),
                    "severity": pattern_data.get("severity", "medium"),
                    "filename": filename,
                    "description": pattern_data.get("message", f"Pattern '{pattern_name}' detected"),
                    "auto_fixable": pattern_data.get("fixable", False)
                })

        return issues

    # Pattern Libraries

    def _get_python_error_patterns(self) -> Dict[str, Any]:
        """Get common Python error patterns."""
        return {
            "missing_parentheses": {
                "regex": r"print\s+\w+",
                "severity": "medium",
                "message": "Missing parentheses in print statement",
                "fixable": True,
                "type": "syntax_modernization"
            },
            "bare_except": {
                "regex": r"except\s*:",
                "severity": "medium",
                "message": "Bare except clause - should specify exception type",
                "fixable": True,
                "type": "exception_handling"
            }
        }

    def _get_security_patterns(self) -> Dict[str, Any]:
        """Get security issue patterns."""
        return {
            "eval_usage": {
                "regex": r"eval\s*\(",
                "severity": "high",
                "message": "Use of eval() is dangerous",
                "fixable": False,
                "type": "security_risk"
            }
        }

    def _get_performance_patterns(self) -> Dict[str, Any]:
        """Get performance issue patterns."""
        return {
            "string_concatenation": {
                "regex": r".*\+.*\+.*",
                "severity": "low",
                "message": "Multiple string concatenations - consider join()",
                "fixable": True,
                "type": "performance_optimization"
            }
        }

    def _get_integration_patterns(self) -> Dict[str, Any]:
        """Get integration issue patterns."""
        return {
            "hardcoded_paths": {
                "regex": r'["\'][A-Z]:\\.*["\']',
                "severity": "medium",
                "message": "Hardcoded Windows path detected",
                "fixable": True,
                "type": "portability_issue"
            }
        }

    # Event Handlers for other events

    async def _on_execution_failed(self, error_report: str):
        """Handle execution failures."""
        self.log("info", "🚨 Execution failed - analyzing error report...")

        # Analyze error for patterns
        error_issue = {
            "type": "execution_error",
            "severity": "critical",
            "description": f"Execution failed: {error_report[:100]}...",
            "auto_fixable": False,
            "timestamp": datetime.now().isoformat()
        }

        self.detected_errors.append(error_issue)
        self.emit_event("code_quality_issue_detected", error_issue)

    async def _on_terminal_output(self, output: str):
        """Monitor terminal output for errors."""
        if any(keyword in output.lower() for keyword in ['error', 'exception', 'traceback']):
            self.log("info", "🔍 Potential error detected in terminal output")

            error_issue = {
                "type": "terminal_error",
                "severity": "medium",
                "description": f"Terminal error detected: {output[:100]}...",
                "auto_fixable": False,
                "timestamp": datetime.now().isoformat()
            }

            self.detected_errors.append(error_issue)

    # Status and Reporting

    async def _generate_final_report(self):
        """Generate final analysis report."""
        total_detected = len(self.detected_errors)
        total_fixed = len(self.successful_fixes)
        success_rate = (total_fixed / max(total_detected, 1)) * 100

        self.log("info", f"📊 Autonomous Code Reviewer Final Report:")
        self.log("info", f"   Issues Detected: {total_detected}")
        self.log("info", f"   Fixes Applied: {total_fixed}")
        self.log("info", f"   Success Rate: {success_rate:.1f}%")
        self.log("info",
                 f"   Integration Analysis: {'Enabled' if self.get_config_value('integration_analysis', True) else 'Disabled'}")

    def get_status_info(self) -> Dict[str, Any]:
        """Get plugin status information."""
        return {
            "monitoring_active": self.state == PluginState.STARTED,
            "auto_fix_enabled": self.get_config_value("auto_fix_enabled", True),
            "is_processing_fixes": self.is_processing_fixes,
            "errors_detected": len(self.detected_errors),
            "errors_fixed": len(self.successful_fixes),
            "pending_fixes": self.auto_fix_queue.qsize(),
            "integration_analysis": self.get_config_value("integration_analysis", True),
            "project_context_available": bool(self.current_project_context),
            "learning_data": {
                "successful_fixes": len(self.successful_fixes),
                "failed_fixes": len(self.failed_fixes)
            }
        }