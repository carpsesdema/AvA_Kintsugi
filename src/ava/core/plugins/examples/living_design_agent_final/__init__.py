# src/ava/core/plugins/examples/living_design_agent/__init__.py
# Living Design Document Agent - Maintains comprehensive project documentation

import asyncio
import ast
import re
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from collections import defaultdict
from ava.core.plugins import PluginBase, PluginMetadata, PluginState


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
                    "description": "How often to automatically analyze project (seconds)"
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

            # Start automatic analysis timer
            if self.get_config_value("auto_update_frequency", 300) > 0:
                asyncio.create_task(self._start_periodic_analysis())

            self.set_state(PluginState.STARTED)
            self.log("info", "🏗️ Living Design Agent active - monitoring project architecture")

            return True

        except Exception as e:
            self.log("error", f"Failed to start Living Design Agent: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def stop(self) -> bool:
        try:
            self.log("info", "Stopping Living Design Agent...")

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

            # Clear state
            self._reset_documentation_state()

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

        # Schedule documentation update
        asyncio.create_task(self._update_documentation(files))

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
        self.log("info", "🆕 New project detected - initializing documentation")
        self._reset_documentation_state()

        # Log major design decision
        decision = {
            "timestamp": datetime.now().isoformat(),
            "type": "project_creation",
            "description": "New project created with Kintsugi AvA",
            "rationale": "Fresh start with clean architecture",
            "impact": "Foundation for all future development"
        }
        self.design_decisions.append(decision)
        self.emit_event("design_decision_logged", decision)

    def _on_project_loaded(self):
        """Handle existing project loading."""
        self.log("info", "📂 Existing project loaded - analyzing structure")
        asyncio.create_task(self._analyze_existing_project())

    # Core Analysis Methods
    async def _update_documentation(self, files: Dict[str, str]):
        """Update documentation based on new/changed files."""
        try:
            # Analyze file structures
            for filename, content in files.items():
                await self._analyze_file_structure(filename, content)

            # Update dependency graph
            self._update_dependency_graph(files)

            # Generate architecture overview
            await self._generate_architecture_overview()

            # Track API changes if enabled
            if self.get_config_value("track_api_changes", True):
                self._track_api_changes(files)

            # Generate diagrams if enabled
            if self.get_config_value("generate_diagrams", True):
                await self._generate_diagrams()

            # Emit update event
            self.emit_event("design_document_updated", {
                "timestamp": datetime.now().isoformat(),
                "files_analyzed": list(files.keys()),
                "structure": self.project_structure
            })

            self.last_analysis_time = datetime.now()
            self.log("success", f"📋 Documentation updated for {len(files)} files")

        except Exception as e:
            self.log("error", f"Failed to update documentation: {e}")

    async def _analyze_file_structure(self, filename: str, content: str):
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
                        "methods": [n.name for n in node.body if
                                    isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))],
                        "inheritance": [base.id for base in node.bases if isinstance(base, ast.Name)],
                        "line": node.lineno
                    }
                    classes.append(class_info)
                    complexity += len(class_info["methods"]) * 2

                elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    # Check if it's a top-level function
                    is_top_level = not any(
                        isinstance(parent, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                        for parent in ast.walk(tree) if node in getattr(parent, 'body', []) and parent is not node
                    )

                    if is_top_level:
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

        except SyntaxError as e:
            self.log("error", f"Syntax error analyzing Python file: {e}")
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
        total_files = len(self.project_structure)
        total_complexity = sum(info.get("complexity_score", 0) for info in self.project_structure.values())

        file_categories = defaultdict(list)
        for filename, info in self.project_structure.items():
            category = self._categorize_file(filename, info)
            file_categories[category].append(filename)

        overview = f"""# Project Architecture Overview
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    Project Statistics

    Total Files: {total_files}
    Total Complexity Score: {total_complexity}
    Average Complexity: {total_complexity / max(total_files, 1):.1f}

    File Categories
    """
        for category, files in file_categories.items():
            overview += f"\n### {category.title()} ({len(files)} files)\n"
            for filename in sorted(files):
                info = self.project_structure[filename]
                complexity = info.get("complexity_score", 0)
                overview += f"- `{filename}` (complexity: {complexity})\n"

        if self.dependency_graph:
            overview += "\n## Key Dependencies\n"
            for file, deps in sorted(self.dependency_graph.items()):
                if deps:
                    overview += f"- `{file}` depends on: {', '.join(f'`{d}`' for d in sorted(deps))}\n"

        if self.design_decisions:
            overview += "\n## Recent Design Decisions\n"
            recent_decisions = sorted(self.design_decisions, key=lambda x: x["timestamp"], reverse=True)[:5]
            for decision in recent_decisions:
                overview += f"- **{decision['type']}** ({decision['timestamp'][:10]}): {decision['description']}\n"

        self.architecture_overview = overview
        self.log("info", f"📊 Architecture overview updated - {total_files} files analyzed")

    async def _generate_diagrams(self):
        """Generate UML-style diagrams from project structure."""
        try:
            diagram = "```mermaid\nclassDiagram\n"

            for filename, info in self.project_structure.items():
                if info.get("classes"):
                    for class_info in info["classes"]:
                        class_name = class_info["name"]
                        diagram += f"    class {class_name} {{\n"

                        for method in class_info.get("methods", []):
                            diagram += f"        +{method}()\n"

                        diagram += "    }\n"

                        for parent in class_info.get("inheritance", []):
                            diagram += f"    {parent} <|-- {class_name}\n"

            diagram += "```\n"

            self.log("info", "📈 Class diagram generated")
            return diagram

        except Exception as e:
            self.log("warning", f"Could not generate diagrams: {e}")
            return ""

    def _track_api_changes(self, files: Dict[str, str]):
        """Track changes to API contracts."""
        for filename, info in self.project_structure.items():
            if filename in files:
                api_elements = []

                for class_info in info.get("classes", []):
                    api_elements.append({
                        "type": "class",
                        "name": class_info["name"],
                        "methods": class_info.get("methods", [])
                    })

                for func_info in info.get("functions", []):
                    if not func_info["name"].startswith("_"):
                        api_elements.append({
                            "type": "function",
                            "name": func_info["name"],
                            "args": func_info.get("args", [])
                        })

                if filename in self.api_contracts:
                    changes = self._detect_api_changes(self.api_contracts[filename], api_elements)
                    if changes:
                        decision = {
                            "timestamp": datetime.now().isoformat(),
                            "type": "api_change",
                            "description": f"API changes detected in {filename}",
                            "changes": changes,
                            "impact": "Potential breaking changes for dependents"
                        }
                        self.design_decisions.append(decision)
                        self.emit_event("design_decision_logged", decision)
                        self.log("warning", f"⚠️ API changes detected in {filename}")

            self.api_contracts[filename] = api_elements

    def _detect_api_changes(self, old_api: List[Dict], new_api: List[Dict]) -> List[str]:
        """Detect changes between API versions."""
        changes = []

        old_map = {item["name"]: item for item in old_api}
        new_map = {item["name"]: item for item in new_api}

        old_names = set(old_map.keys())
        new_names = set(new_map.keys())

        added = new_names - old_names
        removed = old_names - new_names

        for name in added:
            changes.append(f"Added: {new_map[name]['type']} {name}")

        for name in removed:
            changes.append(f"Removed: {old_map[name]['type']} {name}")

        for name in old_names.intersection(new_names):
            old_item = old_map[name]
            new_item = new_map[name]
            if old_item != new_item:
                changes.append(f"Modified: {old_item['type']} {name}")

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
        ext = Path(filename).suffix.lower()

        type_mapping = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.html': 'html',
            '.css': 'css',
            '.json': 'config',
            '.toml': 'config',
            '.md': 'documentation',
            '.txt': 'documentation'
        }

        return type_mapping.get(ext, 'other')

    def _categorize_file(self, filename: str, info: Dict[str, Any]) -> str:
        """Categorize a file for architecture documentation."""
        if 'test' in filename.lower():
            return 'tests'
        elif filename.startswith('core/'):
            return 'core'
        elif filename.startswith('gui/'):
            return 'interface'
        elif filename.startswith('services/'):
            return 'services'
        elif filename.startswith('utils/'):
            return 'utilities'
        elif info.get("type") == 'config':
            return 'configuration'
        elif info.get("type") == 'documentation':
            return 'documentation'
        else:
            return 'application'

    def get_status_info(self) -> Dict[str, Any]:
        """Get plugin status information."""
        return {
            "monitoring_active": self.state == PluginState.STARTED,
            "files_monitored": len(self.monitored_files),
            "project_files": len(self.project_structure),
            "design_decisions": len(self.design_decisions),
            "api_contracts": len(self.api_contracts),
            "last_analysis": self.last_analysis_time.isoformat() if self.last_analysis_time else None,
            "auto_update_enabled": self.get_config_value("auto_update_frequency", 300) > 0
        }

    def get_current_documentation(self) -> Dict[str, Any]:
        """Get current state of all documentation."""
        return {
            "architecture_overview": self.architecture_overview,
            "project_structure": dict(self.project_structure),
            "design_decisions": list(self.design_decisions),
            "api_contracts": dict(self.api_contracts),
            "dependency_graph": {k: list(v) for k, v in self.dependency_graph.items()},
            "last_analysis": self.last_analysis_time.isoformat() if self.last_analysis_time else None,
            "monitored_files": list(self.monitored_files)
        }