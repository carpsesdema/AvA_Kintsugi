# kintsugi_ava/core/plugins/examples/living_design_agent/__init__.py
# Living Design Document Agent - Maintains comprehensive project documentation

import asyncio
import json
import ast
import re
from pathlib import Path
from typing import Dict, Any, List, Set
from datetime import datetime
from collections import defaultdict
from core.plugins import PluginBase, PluginMetadata, PluginState


class LivingDesignAgentPlugin(PluginBase):
    """
    An autonomous agent that maintains living project documentation.

    This plugin:
    - Monitors code changes and updates architecture documentation
    - Generates UML-style diagrams from code structure
    - Tracks design decisions and their evolution
    - Maintains API contracts and dependencies
    - Creates impact analysis for changes
    """

    def __init__(self, event_bus, plugin_config: Dict[str, Any]):
        super().__init__(event_bus, plugin_config)

        # Document state
        self.project_structure = {}
        self.design_decisions = []
        self.api_contracts = {}
        self.dependency_graph = defaultdict(set)
        self.architecture_overview = ""

        # Monitoring state
        self.monitored_files = set()
        self.last_analysis_time = None

        # Task management
        self._periodic_task = None

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="living_design_agent",
            version="1.0.0",
            description="Autonomous agent that maintains living project documentation and architecture overview",
            author="Kintsugi AvA Team",
            dependencies=[],
            event_subscriptions=[
                "code_generation_complete",
                "prepare_for_generation",
                "new_project_requested",
                "load_project_requested"
            ],
            event_emissions=[
                "design_document_updated",
                "architecture_analysis_complete",
                "design_decision_logged"
            ],
            config_schema={
                "auto_update_frequency": {
                    "type": "int",
                    "default": 300,
                    "description": "How often to automatically analyze the project (seconds)"
                },
                "generate_diagrams": {
                    "type": "bool",
                    "default": True,
                    "description": "Whether to generate UML-style diagrams"
                },
                "track_api_changes": {
                    "type": "bool",
                    "default": True,
                    "description": "Track API contract changes"
                },
                "detailed_logging": {
                    "type": "bool",
                    "default": True,
                    "description": "Log detailed analysis information"
                }
            },
            enabled_by_default=False
        )

    async def load(self) -> bool:
        try:
            self.log("info", "Loading Living Design Agent...")

            # Initialize document state
            self._reset_documentation_state()

            self.set_state(PluginState.LOADED)
            self.log("success", "Living Design Agent loaded")
            return True

        except Exception as e:
            self.log("error", f"Failed to load Living Design Agent: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def start(self) -> bool:
        try:
            self.log("info", "Starting Living Design Agent...")

            # Subscribe to events
            self.subscribe_to_event("code_generation_complete", self._on_code_generated)
            self.subscribe_to_event("prepare_for_generation", self._on_generation_prepared)
            self.subscribe_to_event("new_project_requested", self._on_new_project)
            self.subscribe_to_event("load_project_requested", self._on_project_loaded)

            # FIXED: Schedule periodic analysis task to start after startup completes
            # Instead of creating the task immediately, schedule it for the next event loop iteration
            if self.get_config_value("auto_update_frequency", 300) > 0:
                # Use call_soon to avoid the task conflict during startup
                loop = asyncio.get_event_loop()
                loop.call_soon(self._schedule_periodic_analysis)

            self.set_state(PluginState.STARTED)
            self.log("info", "🏗️ Living Design Agent active - monitoring project architecture")

            return True

        except Exception as e:
            self.log("error", f"Failed to start Living Design Agent: {e}")
            self.set_state(PluginState.ERROR)
            return False

    def _schedule_periodic_analysis(self):
        """Schedule the periodic analysis task to start after startup completes."""
        try:
            if self.state == PluginState.STARTED:
                self._periodic_task = asyncio.create_task(self._start_periodic_analysis())
                self.log("info", "📅 Periodic analysis task scheduled")
        except Exception as e:
            self.log("error", f"Failed to schedule periodic analysis: {e}")

    async def stop(self) -> bool:
        try:
            self.log("info", "Stopping Living Design Agent...")

            # Cancel periodic task if running
            if self._periodic_task and not self._periodic_task.done():
                self._periodic_task.cancel()
                try:
                    await self._periodic_task
                except asyncio.CancelledError:
                    pass
                self.log("info", "Periodic analysis task stopped")

            # Generate final documentation
            await self._generate_final_documentation()

            self.set_state(PluginState.STOPPED)
            return True

        except Exception as e:
            self.log("error", f"Failed to stop Living Design Agent: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def unload(self) -> bool:
        try:
            self.log("info", "Unloading Living Design Agent...")

            # Ensure task is cancelled
            if self._periodic_task and not self._periodic_task.done():
                self._periodic_task.cancel()

            # Clear state
            self._reset_documentation_state()
            self._periodic_task = None

            self.set_state(PluginState.UNLOADED)
            self.log("info", "Living Design Agent unloaded")
            return True

        except Exception as e:
            self.log("error", f"Failed to unload Living Design Agent: {e}")
            self.set_state(PluginState.ERROR)
            return False

    # Event Handlers
    def _on_code_generated(self, files: Dict[str, str]):
        """Handle code generation completion."""
        self.log("info", f"📝 Code generated for {len(files)} files - updating documentation")

        # Track new files
        for filename in files.keys():
            self.monitored_files.add(filename)

        # FIXED: Use call_soon to avoid task creation conflicts
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(lambda: asyncio.create_task(self._update_documentation(files)))

    def _on_generation_prepared(self, filenames: List[str], project_path: str = None):
        """Handle preparation for generation."""
        if self.get_config_value("detailed_logging", True):
            self.log("info", f"🔄 Generation prepared for {len(filenames)} files")

        # Log design decision
        decision = {
            "timestamp": datetime.now().isoformat(),
            "type": "generation_prepared",
            "description": f"Preparing to generate {len(filenames)} files",
            "files": filenames,
            "context": "Automated code generation"
        }
        self.design_decisions.append(decision)
        self.emit_event("design_decision_logged", decision)

    def _on_new_project(self):
        """Handle new project creation."""
        self.log("info", "🆕 New project detected - resetting documentation")
        self._reset_documentation_state()

    def _on_project_loaded(self):
        """Handle project loading."""
        self.log("info", "📁 Project loaded - analyzing existing structure")
        asyncio.create_task(self._analyze_existing_project())

    # Core Documentation Methods
    async def _update_documentation(self, files: Dict[str, str]):
        """Update documentation for changed files."""
        try:
            self.log("info", f"📋 Updating documentation for {len(files)} files")

            # Analyze each changed file
            for filename, content in files.items():
                self._analyze_file_structure(filename, content)

            # Update dependency graph
            self._update_dependency_graph(files)

            # Track API changes if enabled
            if self.get_config_value("track_api_changes", True):
                await self._track_api_changes(files)

            # Generate updated overview
            await self._generate_architecture_overview()

            # Log the update
            decision = {
                "timestamp": datetime.now().isoformat(),
                "type": "documentation_updated",
                "description": f"Updated documentation for {len(files)} files",
                "files": list(files.keys()),
                "context": "Automated documentation update"
            }
            self.design_decisions.append(decision)

            self.emit_event("design_document_updated", {
                "files_updated": list(files.keys()),
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            self.log("error", f"Failed to update documentation: {e}")

    def _analyze_file_structure(self, filename: str, content: str):
        """Analyze the structure of a single file."""
        try:
            file_info = {
                "filename": filename,
                "type": self._determine_file_type(filename),
                "size": len(content),
                "classes": [],
                "functions": [],
                "imports": [],
                "exports": [],
                "complexity_score": 0
            }

            if filename.endswith('.py'):
                file_info.update(self._analyze_python_file(content))
            elif filename.endswith(('.js', '.ts')):
                file_info.update(self._analyze_javascript_file(content))
            elif filename.endswith(('.html', '.css')):
                file_info.update(self._analyze_frontend_file(content))

            self.project_structure[filename] = file_info

        except Exception as e:
            self.log("warning", f"Could not analyze structure of {filename}: {e}")

    def _analyze_python_file(self, content: str) -> Dict[str, Any]:
        """Analyze Python file structure using AST."""
        try:
            tree = ast.parse(content)

            classes = []
            functions = []
            imports = []
            complexity = 0

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_info = {
                        "name": node.name,
                        "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
                        "inheritance": [base.id for base in node.bases if isinstance(base, ast.Name)],
                        "line": node.lineno
                    }
                    classes.append(class_info)
                    complexity += len(class_info["methods"]) * 2

                elif isinstance(node, ast.FunctionDef):
                    if not any(node.lineno >= cls["line"] for cls in classes):
                        func_info = {
                            "name": node.name,
                            "args": [arg.arg for arg in node.args.args],
                            "is_async": isinstance(node, ast.AsyncFunctionDef),
                            "line": node.lineno
                        }
                        functions.append(func_info)
                        complexity += len(func_info["args"]) + 1

                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        imports.extend([alias.name for alias in node.names])
                    else:
                        module = node.module or ""
                        imports.extend([f"{module}.{alias.name}" for alias in node.names])

            return {
                "classes": classes,
                "functions": functions,
                "imports": list(set(imports)),
                "complexity_score": complexity
            }

        except SyntaxError:
            return {"classes": [], "functions": [], "imports": [], "complexity_score": 0}

    def _analyze_javascript_file(self, content: str) -> Dict[str, Any]:
        """Basic analysis of JavaScript/TypeScript files."""
        classes = re.findall(r'class\s+(\w+)', content)
        functions = re.findall(r'function\s+(\w+)', content)
        imports = re.findall(r'import.*from\s+["\'](.+?)["\']', content)

        return {
            "classes": [{"name": cls} for cls in classes],
            "functions": [{"name": func} for func in functions],
            "imports": imports,
            "complexity_score": len(classes) * 3 + len(functions) * 2
        }

    def _analyze_frontend_file(self, content: str) -> Dict[str, Any]:
        """Basic analysis of HTML/CSS files."""
        if content.strip().startswith('<!DOCTYPE') or '<html' in content:
            components = re.findall(r'<(\w+)', content)
            return {
                "type": "html",
                "components": list(set(components)),
                "complexity_score": len(set(components))
            }
        else:
            selectors = re.findall(r'\.(\w+)', content)
            return {
                "type": "css",
                "selectors": list(set(selectors)),
                "complexity_score": len(set(selectors))
            }

    def _update_dependency_graph(self, files: Dict[str, str]):
        """Update the project dependency graph."""
        for filename, file_info in self.project_structure.items():
            if filename in files:
                self.dependency_graph[filename] = set()

                for import_item in file_info.get("imports", []):
                    for other_file in self.project_structure.keys():
                        if self._is_dependency_match(import_item, other_file):
                            self.dependency_graph[filename].add(other_file)

    def _is_dependency_match(self, import_item: str, filename: str) -> bool:
        """Check if an import matches a project file."""
        import_name = import_item.split('.')[-1]
        file_name = Path(filename).stem
        return import_name.lower() == file_name.lower()

    async def _generate_architecture_overview(self):
        """Generate a comprehensive architecture overview."""
        try:
            overview_lines = [
                "# Project Architecture Overview",
                f"Generated: {datetime.now().isoformat()}",
                f"Files analyzed: {len(self.project_structure)}",
                "",
                "## File Structure"
            ]

            # Organize files by type
            file_types = defaultdict(list)
            for filename, info in self.project_structure.items():
                file_types[info.get("type", "unknown")].append(filename)

            for file_type, files in sorted(file_types.items()):
                overview_lines.append(f"### {file_type.title()} Files ({len(files)})")
                for filename in sorted(files):
                    overview_lines.append(f"- {filename}")
                overview_lines.append("")

            # Add complexity analysis
            overview_lines.append("## Complexity Analysis")
            total_complexity = sum(info.get("complexity_score", 0) for info in self.project_structure.values())
            overview_lines.append(f"Total complexity score: {total_complexity}")

            # Add dependency information
            if self.dependency_graph:
                overview_lines.extend([
                    "",
                    "## Dependencies",
                    "Key interdependencies:"
                ])
                for file, deps in self.dependency_graph.items():
                    if deps:
                        overview_lines.append(f"- {file} depends on: {', '.join(deps)}")

            self.architecture_overview = "\n".join(overview_lines)
            self.log("info", "📐 Architecture overview generated")

        except Exception as e:
            self.log("error", f"Failed to generate architecture overview: {e}")

    async def _track_api_changes(self, files: Dict[str, str]):
        """Track API changes in the updated files."""
        try:
            for filename in files.keys():
                if filename in self.project_structure:
                    file_info = self.project_structure[filename]

                    # Build current API signature
                    current_api = []
                    for cls in file_info.get("classes", []):
                        current_api.append({
                            "type": "class",
                            "name": cls.get("name", ""),
                            "methods": cls.get("methods", [])
                        })

                    for func in file_info.get("functions", []):
                        current_api.append({
                            "type": "function",
                            "name": func.get("name", ""),
                            "args": func.get("args", [])
                        })

                    # Check for changes if we have previous API data
                    if filename in self.api_contracts:
                        old_api = self.api_contracts[filename]
                        changes = self._compare_api_signatures(old_api, current_api)

                        if changes:
                            self.log("info", f"🔄 API changes detected in {filename}: {len(changes)} changes")
                            decision = {
                                "timestamp": datetime.now().isoformat(),
                                "type": "api_change",
                                "description": f"API changes in {filename}",
                                "file": filename,
                                "changes": changes,
                                "context": "Automated API tracking"
                            }
                            self.design_decisions.append(decision)

                    # Store current API
                    self.api_contracts[filename] = current_api

        except Exception as e:
            self.log("error", f"Failed to track API changes: {e}")

    def _compare_api_signatures(self, old_api: List[Dict], new_api: List[Dict]) -> List[str]:
        """Compare two API signatures and return list of changes."""
        changes = []

        old_names = {item["name"] for item in old_api}
        new_names = {item["name"] for item in new_api}

        added = new_names - old_names
        removed = old_names - new_names

        for name in added:
            changes.append(f"Added: {name}")

        for name in removed:
            changes.append(f"Removed: {name}")

        for old_item in old_api:
            for new_item in new_api:
                if old_item["name"] == new_item["name"]:
                    if old_item.get("args") != new_item.get("args"):
                        changes.append(f"Modified signature: {old_item['name']}")

        return changes

    async def _start_periodic_analysis(self):
        """Start periodic analysis of the project."""
        frequency = self.get_config_value("auto_update_frequency", 300)

        while self.state == PluginState.STARTED:
            try:
                await asyncio.sleep(frequency)

                if self.state == PluginState.STARTED:
                    await self._perform_periodic_analysis()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log("error", f"Error in periodic analysis: {e}")

    async def _perform_periodic_analysis(self):
        """Perform scheduled analysis of the project."""
        self.log("info", "🔍 Performing periodic architecture analysis")

        await self._generate_architecture_overview()

        self.emit_event("architecture_analysis_complete", {
            "timestamp": datetime.now().isoformat(),
            "files_count": len(self.project_structure),
            "decisions_count": len(self.design_decisions)
        })

    async def _analyze_existing_project(self):
        """Analyze an existing project structure."""
        self.log("info", "🔍 Analyzing existing project structure")
        self._reset_documentation_state()

    async def _generate_final_documentation(self):
        """Generate final documentation before stopping."""
        if self.project_structure:
            await self._generate_architecture_overview()

            summary = {
                "analysis_duration": str(datetime.now() - (self.last_analysis_time or datetime.now())),
                "files_analyzed": len(self.project_structure),
                "design_decisions": len(self.design_decisions),
                "api_contracts": len(self.api_contracts)
            }

            self.log("info", f"📋 Final documentation: {summary}")

    # Utility Methods
    def _reset_documentation_state(self):
        """Reset all documentation state."""
        self.project_structure = {}
        self.design_decisions = []
        self.api_contracts = {}
        self.dependency_graph = defaultdict(set)
        self.architecture_overview = ""
        self.monitored_files = set()

    def _determine_file_type(self, filename: str) -> str:
        """Determine the type/category of a file."""
        if filename.endswith('.py'):
            return "python"
        elif filename.endswith(('.js', '.ts')):
            return "javascript"
        elif filename.endswith('.html'):
            return "html"
        elif filename.endswith('.css'):
            return "css"
        elif filename.endswith(('.json', '.yaml', '.yml')):
            return "config"
        elif filename.endswith(('.md', '.txt')):
            return "documentation"
        else:
            return "other"