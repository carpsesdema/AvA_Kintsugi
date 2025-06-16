# gui/code_viewer.py
# FIXED: Added code_viewer_files_loaded event for proper plugin timing

import sys
import os
from pathlib import Path
from PySide6.QtWidgets import (QMainWindow, QVBoxLayout, QWidget, QSplitter,
                               QTreeWidget, QTabWidget)
from PySide6.QtCore import Qt

from gui.project_context_manager import ProjectContextManager
from gui.file_tree_manager import FileTreeManager
from gui.editor_tab_manager import EditorTabManager
from gui.integrated_terminal import IntegratedTerminal


class CodeViewerWindow(QMainWindow):
    """
    Modernized code viewer with plugin-friendly event timing.
    FIXED: Now emits code_viewer_files_loaded for autonomous plugins.
    """

    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        self.project_context = ProjectContextManager()
        self.editor_manager = None
        self.file_tree_manager = None
        self.terminal = None

        self.setWindowTitle("Kintsugi AvA - Code Viewer")
        self.setGeometry(100, 100, 1400, 900)
        self._init_ui()
        self._connect_events()

    def _init_ui(self):
        """Initialize the main UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Create main splitter (file tree | editor+terminal)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: File tree
        file_tree_panel = self._create_file_tree_panel()
        main_splitter.addWidget(file_tree_panel)

        # Right panel: Editor and terminal
        editor_terminal_splitter = self._create_editor_terminal_splitter()
        main_splitter.addWidget(editor_terminal_splitter)

        main_splitter.setSizes([300, 1100])
        main_layout.addWidget(main_splitter)

    def _create_file_tree_panel(self) -> QWidget:
        """Creates the file tree panel."""
        from PySide6.QtWidgets import QTreeWidget
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        tree_widget = QTreeWidget()
        self.file_tree_manager = FileTreeManager(tree_widget)
        self.file_tree_manager.set_file_selection_callback(self._on_file_selected)

        layout.addWidget(tree_widget)
        return panel

    def _create_editor_terminal_splitter(self) -> QSplitter:
        """Creates the editor and terminal panel."""
        from PySide6.QtWidgets import QTabWidget
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Editor tabs
        tab_widget = QTabWidget()
        tab_widget.setTabsClosable(True)
        tab_widget.setMovable(True)
        tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)
        self.editor_manager = EditorTabManager(tab_widget)

        # Terminal
        self.terminal = IntegratedTerminal(self.event_bus)

        right_splitter.addWidget(tab_widget)
        right_splitter.addWidget(self.terminal)
        right_splitter.setSizes([600, 200])

        return right_splitter

    def _connect_events(self):
        """Connects to event bus events."""
        self.event_bus.subscribe("terminal_output_received", self.terminal.append_output)

    def get_active_file_path(self) -> str | None:
        """Returns the path of the currently active editor tab."""
        return self.editor_manager.get_active_file_path()

    def prepare_for_new_project_session(self):
        """Resets for a new project session."""
        self.project_context.clear_context()
        self.file_tree_manager.clear_tree()
        self.editor_manager.prepare_for_new_project()
        self.terminal.clear_output()
        print("[CodeViewer] Prepared for new project session")

    def prepare_for_generation(self, filenames: list, project_path: str = None):
        """Prepares the UI for code generation."""
        self.terminal.clear_output()

        if project_path and self.project_context.set_new_project_context(project_path):
            self.file_tree_manager.setup_new_project_tree(
                self.project_context.project_root, filenames
            )
            print(f"[CodeViewer] Prepared for new project generation: {len(filenames)} files")
            self.show_window()
        elif self.project_context.validate_existing_context():
            self._prepare_tabs_for_modification(filenames)
            print(f"[CodeViewer] Prepared for modification: {len(filenames)} files")
            self.show_window()

    def _prepare_tabs_for_modification(self, filenames: list):
        """Opens tabs for files that will be modified."""
        if self.project_context.is_valid:
            for filename in filenames:
                abs_path = self.project_context.get_absolute_path(filename)
                if abs_path and abs_path.is_file():
                    self.editor_manager.open_file_in_tab(abs_path)

    def stream_code_chunk(self, filename: str, chunk: str):
        """Streams a chunk of code to the appropriate editor."""
        if self.project_context.is_valid:
            abs_path = self.project_context.get_absolute_path(filename)
            if abs_path:
                self.editor_manager.stream_content_to_editor(str(abs_path.resolve()), chunk)

    def display_code(self, files: dict):
        """
        Displays completed code files in editors.
        FIXED: Now emits code_viewer_files_loaded for autonomous plugins.
        """
        for filename, content in files.items():
            if self.project_context.is_valid:
                abs_path = self.project_context.get_absolute_path(filename)
                if abs_path:
                    path_key = str(abs_path.resolve())
                    self.editor_manager.create_or_update_tab(path_key, content)

        # FIX: Emit new event for autonomous plugins with full project context
        if files and self.project_context.is_valid:
            print(f"[CodeViewer] Files loaded in viewer, triggering autonomous analysis...")

            # Get full project context for plugins
            project_context = self._build_full_project_context(files)

            # This is the NEW event that autonomous plugins should subscribe to
            self.event_bus.emit("code_viewer_files_loaded", {
                "files": files,
                "project_path": str(self.project_context.project_root),
                "full_project_context": project_context
            })

    def _build_full_project_context(self, new_files: dict) -> dict:
        """Build comprehensive project context for autonomous plugins."""
        try:
            if not self.project_context.is_valid:
                return {}

            project_root = self.project_context.project_root

            # Get all Python files in project (existing + new)
            all_files = {}

            # Add existing files
            for py_file in project_root.rglob("*.py"):
                if py_file.is_file():
                    try:
                        rel_path = py_file.relative_to(project_root).as_posix()
                        all_files[rel_path] = py_file.read_text(encoding='utf-8')
                    except Exception as e:
                        print(f"[CodeViewer] Could not read {py_file}: {e}")

            # Add/update with new files
            all_files.update(new_files)

            # Build dependency map
            dependency_map = self._analyze_dependencies(all_files)

            # Build class/function index
            symbol_index = self._build_symbol_index(all_files)

            return {
                "all_files": all_files,
                "dependency_map": dependency_map,
                "symbol_index": symbol_index,
                "project_structure": self._analyze_project_structure(all_files)
            }

        except Exception as e:
            print(f"[CodeViewer] Error building project context: {e}")
            return {}

    def _analyze_dependencies(self, files: dict) -> dict:
        """Analyze import dependencies between files."""
        import re

        dependency_map = {}

        for filename, content in files.items():
            if not filename.endswith('.py'):
                continue

            dependencies = set()

            # Find import statements
            import_patterns = [
                r'^from\s+(\w+(?:\.\w+)*)\s+import',
                r'^import\s+(\w+(?:\.\w+)*)'
            ]

            for line in content.split('\n'):
                line = line.strip()
                for pattern in import_patterns:
                    match = re.match(pattern, line)
                    if match:
                        module = match.group(1)
                        dependencies.add(module)

            dependency_map[filename] = list(dependencies)

        return dependency_map

    def _build_symbol_index(self, files: dict) -> dict:
        """Build index of classes and functions in each file."""
        import re

        symbol_index = {}

        for filename, content in files.items():
            if not filename.endswith('.py'):
                continue

            symbols = {
                "classes": [],
                "functions": []
            }

            # Find class definitions
            class_pattern = r'^class\s+(\w+)(?:\([^)]*\))?:'
            for line in content.split('\n'):
                match = re.match(class_pattern, line.strip())
                if match:
                    symbols["classes"].append(match.group(1))

            # Find function definitions
            func_pattern = r'^def\s+(\w+)\s*\('
            for line in content.split('\n'):
                match = re.match(func_pattern, line.strip())
                if match:
                    symbols["functions"].append(match.group(1))

            symbol_index[filename] = symbols

        return symbol_index

    def _analyze_project_structure(self, files: dict) -> dict:
        """Analyze overall project structure."""
        structure = {
            "total_files": len(files),
            "python_files": len([f for f in files.keys() if f.endswith('.py')]),
            "directories": set(),
            "main_modules": []
        }

        for filename in files.keys():
            # Track directories
            if '/' in filename:
                directory = '/'.join(filename.split('/')[:-1])
                structure["directories"].add(directory)

            # Identify main modules
            if filename == 'main.py' or filename.endswith('/main.py'):
                structure["main_modules"].append(filename)

        structure["directories"] = list(structure["directories"])

        return structure

    def load_project(self, project_path_str: str):
        """Loads an existing project into the viewer."""
        project_path = Path(project_path_str)
        if self.project_context.set_new_project_context(project_path_str):
            self.file_tree_manager.load_existing_project_tree(project_path)
            print(f"[CodeViewer] Loaded project: {project_path.name}")

    def _on_file_selected(self, file_path: Path):
        """Handles file selection from the tree."""
        self.editor_manager.open_file_in_tab(file_path)

    def _on_tab_close_requested(self, index: int):
        """Handles tab close requests."""
        self.editor_manager.close_tab(index)

    def show_window(self):
        """Shows the window and brings it to front."""
        if not self.isVisible():
            self.show()
        self.activateWindow()
        self.raise_()

    def show_fix_button(self):
        if self.terminal:
            self.terminal.show_fix_button()

    def hide_fix_button(self):
        if self.terminal:
            self.terminal.hide_fix_button()

    def highlight_error_in_editor(self, file_path: Path, line_number: int):
        """Delegates error highlighting to the editor manager."""
        if self.editor_manager:
            self.editor_manager.highlight_error(str(file_path), line_number)

    def clear_all_error_highlights(self):
        """Delegates clearing error highlights to the editor manager."""
        if self.editor_manager:
            self.editor_manager.clear_all_error_highlights()