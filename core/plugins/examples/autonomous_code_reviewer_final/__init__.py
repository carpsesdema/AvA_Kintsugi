# kintsugi_ava/core/plugins/examples/autonomous_code_reviewer/__init__.py
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
    An autonomous agent that continuously monitors code quality and fixes issues.
    This plugin:
    - Monitors terminal output for errors and traces them to source
    - Proactively analyzes code for potential issues
    - Automatically generates and applies fixes
    - Performs deep code quality analysis
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

        # Learning system
        self.successful_fixes = []
        self.failed_fixes = []
        self.pattern_library = {
            "common_python_errors": self._get_python_error_patterns(),
            "security_patterns": self._get_security_patterns(),
            "performance_patterns": self._get_performance_patterns()
        }

        # Auto-fix worker
        self.auto_fix_worker = None
        self.is_processing_fixes = False

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="autonomous_code_reviewer",
            version="1.0.0",
            description="Autonomous agent that monitors, analyzes, and fixes code issues proactively",
            author="Kintsugi AvA Team",
            dependencies=[],
            event_subscriptions=[
                "terminal_output_received",
                "execution_failed",
                "code_generation_complete",
                "stream_code_chunk"
            ],
            event_emissions=[
                "error_detected_and_analyzed",
                "auto_fix_applied",
                "code_quality_issue_found",
                "review_analysis_complete"
            ],
            config_schema={
                "auto_fix_enabled": {
                    "type": "bool",
                    "default": True,
                    "description": "Enable automatic fixing of detected issues"
                },
                "proactive_analysis": {
                    "type": "bool",
                    "default": True,
                    "description": "Continuously analyze code for potential issues"
                },
                "error_monitoring": {
                    "type": "bool",
                    "default": True,
                    "description": "Monitor terminal output for errors"
                },
                "security_analysis": {
                    "type": "bool",
                    "default": True,
                    "description": "Analyze code for security vulnerabilities"
                },
                "performance_analysis": {
                    "type": "bool",
                    "default": False,
                    "description": "Analyze code for performance issues"
                },
                "learning_enabled": {
                    "type": "bool",
                    "default": True,
                    "description": "Learn from successful and failed fixes"
                },
                "auto_commit_fixes": {
                    "type": "bool",
                    "default": False,
                    "description": "Automatically commit successful fixes"
                },
                "analysis_frequency": {
                    "type": "int",
                    "default": 600,
                    "description": "How often to perform proactive analysis (seconds)"
                }
            },
            enabled_by_default=False
        )

    async def load(self) -> bool:
        try:
            self.log("info", "Loading Autonomous Code Reviewer...")

            # Initialize state
            self._reset_analysis_state()

            # Load learned patterns
            await self._load_learned_patterns()

            self.set_state(PluginState.LOADED)
            self.log("success", "Autonomous Code Reviewer loaded")
            return True

        except Exception as e:
            self.log("error", f"Failed to load Autonomous Code Reviewer: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def start(self) -> bool:
        try:
            self.log("info", "Starting Autonomous Code Reviewer...")

            # Subscribe to events
            self.subscribe_to_event("terminal_output_received", self._on_terminal_output)
            self.subscribe_to_event("execution_failed", self._on_execution_failed)
            self.subscribe_to_event("code_generation_complete", self._on_code_generated)
            self.subscribe_to_event("stream_code_chunk", self._on_code_streaming)

            # Start auto-fix worker
            if self.get_config_value("auto_fix_enabled", True):
                self.auto_fix_worker = asyncio.create_task(self._auto_fix_worker())

            # Start proactive analysis
            if self.get_config_value("proactive_analysis", True):
                asyncio.create_task(self._start_proactive_analysis())

            self.set_state(PluginState.STARTED)
            self.log("info", "🔍 Autonomous Code Reviewer active - monitoring for issues")

            return True

        except Exception as e:
            self.log("error", f"Failed to start Autonomous Code Reviewer: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def stop(self) -> bool:
        try:
            self.log("info", "Stopping Autonomous Code Reviewer...")

            # Stop auto-fix worker
            if self.auto_fix_worker:
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
            self.log("error", f"Failed to stop Autonomous Code Reviewer: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def unload(self) -> bool:
        try:
            self.log("info", "Unloading Autonomous Code Reviewer...")

            # Save learned patterns
            await self._save_learned_patterns()

            # Clear state
            self._reset_analysis_state()

            self.set_state(PluginState.UNLOADED)
            self.log("info", "Autonomous Code Reviewer unloaded")
            return True

        except Exception as e:
            self.log("error", f"Failed to unload Autonomous Code Reviewer: {e}")
            self.set_state(PluginState.ERROR)
            return False

    # Event Handlers
    def _on_terminal_output(self, output: str):
        """Monitor terminal output for errors."""
        if not self.get_config_value("error_monitoring", True):
            return

        # Check for error patterns
        if self._contains_error_indicators(output):
            self.log("warning", "🚨 Error detected in terminal output")
            asyncio.create_task(self._analyze_terminal_error(output))

    def _on_execution_failed(self, error_report: str):
        """Handle execution failures."""
        self.log("error", f"💥 Execution failure detected - analyzing...")
        asyncio.create_task(self._handle_execution_error(error_report))

    def _on_code_generated(self, files: Dict[str, str]):
        """Analyze newly generated code."""
        self.log("info", f"📝 Analyzing {len(files)} generated files for issues")
        asyncio.create_task(self._analyze_generated_code(files))

    def _on_code_streaming(self, filename: str, chunk: str):
        """Analyze code as it's being streamed."""
        if self.get_config_value("proactive_analysis", True):
            # Queue for analysis (don't block streaming)
            asyncio.create_task(self._analyze_code_chunk(filename, chunk))

    # Core Analysis Methods
    async def _analyze_terminal_error(self, output: str):
        """Analyze error from terminal output."""
        try:
            error_info = self._parse_error_output(output)
            if not error_info:
                return

            # Store error for analysis
            error_record = {
                "timestamp": datetime.now().isoformat(),
                "type": "terminal_error",
                "raw_output": output,
                "parsed_info": error_info,
                "status": "detected"
            }

            self.detected_errors.append(error_record)

            # Queue for auto-fix if enabled
            if self.get_config_value("auto_fix_enabled", True):
                await self.auto_fix_queue.put(error_record)

            # Emit event
            self.emit_event("error_detected_and_analyzed", error_record)

        except Exception as e:
            self.log("error", f"Failed to analyze terminal error: {e}")

    async def _handle_execution_error(self, error_report: str):
        """Handle execution failures with detailed analysis."""
        try:
            # Parse the error report
            error_info = self._parse_execution_error(error_report)

            error_record = {
                "timestamp": datetime.now().isoformat(),
                "type": "execution_error",
                "error_report": error_report,
                "parsed_info": error_info,
                "severity": "high",
                "status": "detected"
            }

            self.detected_errors.append(error_record)

            # High priority for auto-fix
            if self.get_config_value("auto_fix_enabled", True):
                # Put at front of queue (high priority)
                await self.auto_fix_queue.put(error_record)

            # Emit event
            self.emit_event("error_detected_and_analyzed", error_record)

            self.log("info", f"🔬 Execution error analyzed and queued for fixing")

        except Exception as e:
            self.log("error", f"Failed to handle execution error: {e}")

    async def _analyze_generated_code(self, files: Dict[str, str]):
        """Analyze newly generated code for potential issues."""
        try:
            issues_found = []

            for filename, content in files.items():
                file_issues = await self._analyze_single_file(filename, content)
                if file_issues:
                    issues_found.extend(file_issues)
                    self.code_quality_issues[filename].extend(file_issues)

            if issues_found:
                self.log("warning", f"⚠️ Found {len(issues_found)} potential issues in generated code")

                # Queue high-severity issues for auto-fix
                for issue in issues_found:
                    if issue.get("severity") in ["high", "critical"]:
                        await self.auto_fix_queue.put({
                            "timestamp": datetime.now().isoformat(),
                            "type": "code_quality_issue",
                            "issue": issue,
                            "status": "detected"
                        })

            # Emit analysis complete event
            self.emit_event("review_analysis_complete", {
                "files_analyzed": len(files),
                "issues_found": len(issues_found),
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            self.log("error", f"Failed to analyze generated code: {e}")

    async def _analyze_single_file(self, filename: str, content: str) -> List[Dict[str, Any]]:
        """Analyze a single file for issues."""
        issues = []

        try:
            # Basic syntax check
            if filename.endswith('.py'):
                issues.extend(self._analyze_python_file(filename, content))
            elif filename.endswith(('.js', '.ts')):
                issues.extend(self._analyze_javascript_file(filename, content))

            # Security analysis
            if self.get_config_value("security_analysis", True):
                issues.extend(self._analyze_security_issues(filename, content))

            # Performance analysis
            if self.get_config_value("performance_analysis", False):
                issues.extend(self._analyze_performance_issues(filename, content))

            return issues

        except Exception as e:
            self.log("warning", f"Could not analyze {filename}: {e}")
            return []

    def _analyze_python_file(self, filename: str, content: str) -> List[Dict[str, Any]]:
        """Analyze Python file for issues."""
        issues = []

        try:
            # Check syntax
            try:
                ast.parse(content)
            except SyntaxError as e:
                issues.append({
                    "type": "syntax_error",
                    "severity": "critical",
                    "line": e.lineno,
                    "message": str(e),
                    "filename": filename,
                    "auto_fixable": True
                })
                return issues  # Don't continue if syntax is broken

            # Check for common issues using patterns
            for pattern_name, pattern_data in self.pattern_library["common_python_errors"].items():
                if re.search(pattern_data["regex"], content, re.MULTILINE):
                    issues.append({
                        "type": "code_pattern",
                        "pattern": pattern_name,
                        "severity": pattern_data["severity"],
                        "message": pattern_data["message"],
                        "filename": filename,
                        "auto_fixable": pattern_data.get("fixable", False),
                        "fix_suggestion": pattern_data.get("fix", "")
                    })

            # Check for unused imports (basic)
            lines = content.split('\n')
            imports = []
            for i, line in enumerate(lines):
                if line.strip().startswith(('import ', 'from ')):
                    imports.append((i + 1, line.strip()))

            for line_num, import_line in imports:
                # Simple heuristic: if import name doesn't appear elsewhere
                import_name = self._extract_import_name(import_line)
                if import_name and import_name not in content.replace(import_line, ''):
                    issues.append({
                        "type": "unused_import",
                        "severity": "low",
                        "line": line_num,
                        "message": f"Unused import: {import_name}",
                        "filename": filename,
                        "auto_fixable": True,
                        "fix_suggestion": f"Remove line {line_num}: {import_line}"
                    })

        except Exception as e:
            self.log("warning", f"Error analyzing Python file {filename}: {e}")

        return issues

    def _analyze_javascript_file(self, filename: str, content: str) -> List[Dict[str, Any]]:
        """Basic analysis of JavaScript/TypeScript files."""
        issues = []

        # Check for common issues using simple patterns
        js_patterns = {
            "console_log": {
                "regex": r"console\.log\(",
                "severity": "low",
                "message": "Console.log statement found - consider removing for production"
            },
            "var_usage": {
                "regex": r"\bvar\s+\w+",
                "severity": "medium",
                "message": "Use 'let' or 'const' instead of 'var'"
            },
            "eval_usage": {
                "regex": r"\beval\s*\(",
                "severity": "high",
                "message": "Avoid using eval() - security risk"
            }
        }

        for pattern_name, pattern_data in js_patterns.items():
            matches = list(re.finditer(pattern_data["regex"], content))
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                issues.append({
                    "type": "code_pattern",
                    "pattern": pattern_name,
                    "severity": pattern_data["severity"],
                    "line": line_num,
                    "message": pattern_data["message"],
                    "filename": filename,
                    "auto_fixable": False
                })

        return issues

    def _analyze_security_issues(self, filename: str, content: str) -> List[Dict[str, Any]]:
        """Analyze for security vulnerabilities."""
        issues = []

        for pattern_name, pattern_data in self.pattern_library["security_patterns"].items():
            if re.search(pattern_data["regex"], content, re.MULTILINE | re.IGNORECASE):
                issues.append({
                    "type": "security_issue",
                    "pattern": pattern_name,
                    "severity": pattern_data["severity"],
                    "message": pattern_data["message"],
                    "filename": filename,
                    "auto_fixable": pattern_data.get("fixable", False),
                    "fix_suggestion": pattern_data.get("fix", "")
                })

        return issues

    def _analyze_performance_issues(self, filename: str, content: str) -> List[Dict[str, Any]]:
        """Analyze for performance issues."""
        issues = []

        for pattern_name, pattern_data in self.pattern_library["performance_patterns"].items():
            if re.search(pattern_data["regex"], content, re.MULTILINE):
                issues.append({
                    "type": "performance_issue",
                    "pattern": pattern_name,
                    "severity": pattern_data["severity"],
                    "message": pattern_data["message"],
                    "filename": filename,
                    "auto_fixable": pattern_data.get("fixable", False),
                    "fix_suggestion": pattern_data.get("fix", "")
                })

        return issues

    async def _analyze_code_chunk(self, filename: str, chunk: str):
        """Analyze streaming code chunks."""
        # Simple analysis for streaming chunks
        if self._contains_obvious_errors(chunk):
            issue = {
                "type": "streaming_issue",
                "severity": "medium",
                "message": "Potential issue detected in streaming code",
                "filename": filename,
                "chunk": chunk[:100] + "..." if len(chunk) > 100 else chunk
            }

            await self.auto_fix_queue.put({
                "timestamp": datetime.now().isoformat(),
                "type": "streaming_issue",
                "issue": issue,
                "status": "detected"
            })

    # Auto-Fix System
    async def _auto_fix_worker(self):
        """Worker that processes the auto-fix queue."""
        self.log("info", "🤖 Auto-fix worker started")

        while self.state == PluginState.STARTED:
            try:
                # Wait for next item to fix
                error_record = await asyncio.wait_for(self.auto_fix_queue.get(), timeout=1.0)

                self.is_processing_fixes = True
                await self._attempt_auto_fix(error_record)
                self.is_processing_fixes = False

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log("error", f"Error in auto-fix worker: {e}")
                self.is_processing_fixes = False

    async def _attempt_auto_fix(self, error_record: Dict[str, Any]):
        """Attempt to automatically fix an error."""
        try:
            self.log("info", f"🔧 Attempting auto-fix for {error_record['type']}")

            fix_result = None

            if error_record["type"] == "execution_error":
                fix_result = await self._fix_execution_error(error_record)
            elif error_record["type"] == "code_quality_issue":
                fix_result = await self._fix_code_quality_issue(error_record)
            elif error_record["type"] == "terminal_error":
                fix_result = await self._fix_terminal_error(error_record)

            if fix_result and fix_result["success"]:
                # Record successful fix
                self.fixed_errors.append({
                    **error_record,
                    "fix_result": fix_result,
                    "fixed_at": datetime.now().isoformat(),
                    "status": "fixed"
                })

                if self.get_config_value("learning_enabled", True):
                    self.successful_fixes.append({
                        "error_type": error_record["type"],
                        "fix_method": fix_result["method"],
                        "timestamp": datetime.now().isoformat()
                    })

                # Emit success event
                self.emit_event("auto_fix_applied", {
                    "error_record": error_record,
                    "fix_result": fix_result,
                    "timestamp": datetime.now().isoformat()
                })

                self.log("success", f"✅ Successfully auto-fixed {error_record['type']}")

            else:
                # Record failed fix
                if self.get_config_value("learning_enabled", True):
                    self.failed_fixes.append({
                        "error_type": error_record["type"],
                        "failure_reason": fix_result.get("reason", "Unknown") if fix_result else "No fix attempted",
                        "timestamp": datetime.now().isoformat()
                    })

                self.log("warning", f"❌ Failed to auto-fix {error_record['type']}")

        except Exception as e:
            self.log("error", f"Error attempting auto-fix: {e}")

    async def _fix_execution_error(self, error_record: Dict[str, Any]) -> Dict[str, Any]:
        """Fix execution errors using LLM."""
        try:
            # This would integrate with your existing LLM infrastructure
            # For now, return a simulation of the fix process

            error_info = error_record.get("parsed_info", {})
            filename = error_info.get("filename")

            if not filename:
                return {"success": False, "reason": "Could not identify source file"}

            # Simulate LLM-based fix generation
            fix_suggestion = await self._generate_llm_fix(error_record)

            if fix_suggestion:
                # Apply the fix (this would integrate with your project manager)
                success = await self._apply_fix_to_file(filename, fix_suggestion)

                if success:
                    return {
                        "success": True,
                        "method": "llm_generated_fix",
                        "filename": filename,
                        "fix_applied": fix_suggestion
                    }

            return {"success": False, "reason": "Could not generate valid fix"}

        except Exception as e:
            return {"success": False, "reason": f"Fix attempt failed: {e}"}

    async def _fix_code_quality_issue(self, error_record: Dict[str, Any]) -> Dict[str, Any]:
        """Fix code quality issues."""
        try:
            issue = error_record.get("issue", {})

            if not issue.get("auto_fixable", False):
                return {"success": False, "reason": "Issue not auto-fixable"}

            filename = issue.get("filename")
            fix_suggestion = issue.get("fix_suggestion", "")

            if fix_suggestion and filename:
                success = await self._apply_simple_fix(filename, issue, fix_suggestion)

                if success:
                    return {
                        "success": True,
                        "method": "pattern_based_fix",
                        "filename": filename,
                        "fix_applied": fix_suggestion
                    }

            return {"success": False, "reason": "No fix suggestion available"}

        except Exception as e:
            return {"success": False, "reason": f"Fix attempt failed: {e}"}

    async def _fix_terminal_error(self, error_record: Dict[str, Any]) -> Dict[str, Any]:
        """Fix terminal errors."""
        try:
            # Simple fixes for common terminal errors
            error_info = error_record.get("parsed_info", {})
            error_type = error_info.get("type", "")

            if error_type == "module_not_found":
                module_name = error_info.get("module", "")
                if module_name:
                    # Suggest pip install (this would integrate with terminal service)
                    return {
                        "success": True,
                        "method": "pip_install_suggestion",
                        "suggestion": f"pip install {module_name}"
                    }

            return {"success": False, "reason": "No automatic fix available for terminal error"}

        except Exception as e:
            return {"success": False, "reason": f"Fix attempt failed: {e}"}

    async def _generate_llm_fix(self, error_record: Dict[str, Any]) -> Optional[str]:
        """Generate fix using LLM (integrates with existing LLM infrastructure)."""
        # This would use your existing LLM client and prompt system
        # For now, return a placeholder
        return "# LLM-generated fix would be here"

    async def _apply_fix_to_file(self, filename: str, fix_content: str) -> bool:
        """Apply fix to a file (integrates with project manager)."""
        # This would integrate with your project manager to apply fixes
        # For now, just log the action
        self.log("info", f"Would apply fix to {filename}: {fix_content[:50]}...")
        return True

    async def _apply_simple_fix(self, filename: str, issue: Dict[str, Any], fix_suggestion: str) -> bool:
        """Apply simple pattern-based fixes."""
        # This would apply simple fixes like removing unused imports
        self.log("info", f"Would apply simple fix to {filename}: {fix_suggestion}")
        return True

    # Proactive Analysis
    async def _start_proactive_analysis(self):
        """Start proactive code analysis."""
        frequency = self.get_config_value("analysis_frequency", 600)

        while self.state == PluginState.STARTED:
            try:
                await asyncio.sleep(frequency)

                if self.state == PluginState.STARTED:
                    await self._perform_proactive_analysis()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log("error", f"Error in proactive analysis: {e}")

    async def _perform_proactive_analysis(self):
        """Perform scheduled proactive analysis."""
        self.log("info", "🔍 Performing proactive code analysis")

        # This would integrate with project manager to get current files
        # For now, just analyze tracked issues

        total_issues = sum(len(issues) for issues in self.code_quality_issues.values())

        if total_issues > 0:
            self.log("info", f"📊 Proactive analysis found {total_issues} ongoing issues")

            # Emit analysis event
            self.emit_event("review_analysis_complete", {
                "type": "proactive",
                "total_issues": total_issues,
                "timestamp": datetime.now().isoformat()
            })

    # Pattern Management
    def _get_python_error_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Get common Python error patterns."""
        return {
            "undefined_variable": {
                "regex": r"NameError: name '(\w+)' is not defined",
                "severity": "high",
                "message": "Undefined variable used",
                "fixable": True,
                "fix": "Define the variable or check for typos"
            },
            "import_error": {
                "regex": r"ImportError|ModuleNotFoundError",
                "severity": "high",
                "message": "Import or module not found",
                "fixable": True,
                "fix": "Check import path or install missing package"
            },
            "indentation_error": {
                "regex": r"IndentationError",
                "severity": "critical",
                "message": "Indentation error",
                "fixable": True,
                "fix": "Fix indentation to use consistent spaces/tabs"
            },
            "syntax_error": {
                "regex": r"SyntaxError",
                "severity": "critical",
                "message": "Syntax error in code",
                "fixable": True,
                "fix": "Fix syntax according to Python grammar"
            }
        }

    def _get_security_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Get security vulnerability patterns."""
        return {
            "sql_injection": {
                "regex": r"execute\s*\(\s*['\"].*%.*['\"]",
                "severity": "critical",
                "message": "Potential SQL injection vulnerability",
                "fixable": True,
                "fix": "Use parameterized queries instead of string formatting"
            },
            "hardcoded_password": {
                "regex": r"password\s*=\s*['\"][^'\"]{4,}['\"]",
                "severity": "high",
                "message": "Hardcoded password detected",
                "fixable": True,
                "fix": "Use environment variables or secure credential storage"
            },
            "unsafe_eval": {
                "regex": r"\beval\s*\(",
                "severity": "high",
                "message": "Unsafe use of eval()",
                "fixable": True,
                "fix": "Avoid eval() or use ast.literal_eval() for safe evaluation"
            }
        }

    def _get_performance_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Get performance issue patterns."""
        return {
            "inefficient_loop": {
                "regex": r"for\s+\w+\s+in\s+range\s*\(\s*len\s*\(",
                "severity": "medium",
                "message": "Inefficient loop pattern",
                "fixable": True,
                "fix": "Use 'for item in collection' instead of 'for i in range(len(collection))'"
            },
            "string_concatenation": {
                "regex": r"(\w+)\s*\+=\s*['\"].*['\"]",
                "severity": "medium",
                "message": "Inefficient string concatenation",
                "fixable": True,
                "fix": "Use join() or f-strings for better performance"
            }
        }

    # Utility Methods
    def _contains_error_indicators(self, output: str) -> bool:
        """Check if output contains error indicators."""
        error_indicators = [
            "error:", "Error:", "ERROR:",
            "exception:", "Exception:", "EXCEPTION:",
            "traceback", "Traceback", "TRACEBACK",
            "failed", "Failed", "FAILED",
            "syntax error", "Syntax Error", "SYNTAX ERROR"
        ]

        return any(indicator in output for indicator in error_indicators)

    def _contains_obvious_errors(self, chunk: str) -> bool:
        """Check if code chunk contains obvious errors."""
        # Simple checks for obvious issues
        obvious_issues = [
            "undefined", "not defined",
            "syntax error", "indentation error",
            "import error", "module not found"
        ]

        chunk_lower = chunk.lower()
        return any(issue in chunk_lower for issue in obvious_issues)

    def _parse_error_output(self, output: str) -> Optional[Dict[str, Any]]:
        """Parse error information from terminal output."""
        try:
            # Extract file and line information
            file_match = re.search(r'File "([^"]+)", line (\d+)', output)

            error_info = {
                "raw_output": output,
                "timestamp": datetime.now().isoformat()
            }

            if file_match:
                error_info["filename"] = file_match.group(1)
                error_info["line"] = int(file_match.group(2))

            # Extract error type
            error_type_match = re.search(r'(\w+Error|Exception):', output)
            if error_type_match:
                error_info["error_type"] = error_type_match.group(1)

            # Extract error message
            lines = output.strip().split('\n')
            if lines:
                error_info["message"] = lines[-1]

            return error_info

        except Exception as e:
            self.log("warning", f"Could not parse error output: {e}")
            return None

    def _parse_execution_error(self, error_report: str) -> Dict[str, Any]:
        """Parse execution error report."""
        # Use similar parsing to your existing validation service
        error_info = {
            "error_report": error_report,
            "timestamp": datetime.now().isoformat()
        }

        # Extract filename and line number from traceback
        traceback_lines = re.findall(r'File "(.+?)", line (\d+)', error_report)
        if traceback_lines:
            # Get the last (most relevant) file from traceback
            filename, line_num = traceback_lines[-1]
            error_info["filename"] = filename
            error_info["line"] = int(line_num)

        # Extract error type and message
        lines = error_report.strip().split('\n')
        if lines:
            last_line = lines[-1]
            if ':' in last_line:
                error_type, message = last_line.split(':', 1)
                error_info["error_type"] = error_type.strip()
                error_info["message"] = message.strip()

        return error_info

    def _extract_import_name(self, import_line: str) -> Optional[str]:
        """Extract the main import name from an import line."""
        try:
            if import_line.startswith('import '):
                # import module
                parts = import_line[7:].split(' as ')
                return parts[-1].split('.')[0].strip()
            elif import_line.startswith('from '):
                # from module import name
                parts = import_line.split(' import ')
                if len(parts) == 2:
                    imported = parts[1].split(' as ')
                    return imported[-1].split(',')[0].strip()
            return None
        except:
            return None

    async def _load_learned_patterns(self):
        """Load previously learned patterns."""
        # This would load from persistent storage
        # For now, just initialize empty
        pass

    async def _save_learned_patterns(self):
        """Save learned patterns for future use."""
        # This would save to persistent storage
        # For now, just log the intent
        if self.successful_fixes or self.failed_fixes:
            self.log("info",
                     f"💾 Saving learning data: {len(self.successful_fixes)} successes, {len(self.failed_fixes)} failures")

    def _reset_analysis_state(self):
        """Reset all analysis state."""
        self.detected_errors = []
        self.fixed_errors = []
        self.code_quality_issues = defaultdict(list)
        self.analysis_history = []
        self.successful_fixes = []
        self.failed_fixes = []

    async def _generate_final_report(self):
        """Generate final analysis report."""
        total_detected = len(self.detected_errors)
        total_fixed = len(self.fixed_errors)
        success_rate = (total_fixed / max(total_detected, 1)) * 100

        report = {
            "total_errors_detected": total_detected,
            "total_errors_fixed": total_fixed,
            "fix_success_rate": success_rate,
            "learning_data": {
                "successful_fixes": len(self.successful_fixes),
                "failed_fixes": len(self.failed_fixes)
            },
            "code_quality_issues": {
                filename: len(issues)
                for filename, issues in self.code_quality_issues.items()
            }
        }

        self.log("info", f"📊 Final Report: {total_fixed}/{total_detected} errors fixed ({success_rate:.1f}% success rate)")

    def get_status_info(self) -> Dict[str, Any]:
        """Get plugin status information."""
        return {
            "monitoring_active": self.state == PluginState.STARTED,
            "auto_fix_enabled": self.get_config_value("auto_fix_enabled", True),
            "is_processing_fixes": self.is_processing_fixes,
            "errors_detected": len(self.detected_errors),
            "errors_fixed": len(self.fixed_errors),
            "pending_fixes": self.auto_fix_queue.qsize(),
            "code_quality_issues": sum(len(issues) for issues in self.code_quality_issues.values()),
            "learning_data": {
                "successful_fixes": len(self.successful_fixes),
                "failed_fixes": len(self.failed_fixes)
            }
        }