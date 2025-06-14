# kintsugi_ava/gui/code_viewer.py
# V18: Corrected to use absolute imports and fixed crash on code_generation_complete.

from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QSplitter, QWidget, QVBoxLayout
from PySide6.QtCore import Qt

# --- IMPORT FIX: Using absolute paths from project root ---
from gui.components import Colors
from gui.project_context_manager import ProjectContextManager
from gui.editor_tab_manager import EditorTabManager
from gui.file_tree_manager import FileTreeManager
from gui.integrated_terminal import IntegratedTerminal
from gui.status_bar import StatusBar


class CodeViewerWindow(QMainWindow):
    """
    Clean, focused code viewer using SRP-based managers.
    Single responsibility: Orchestrate the code viewing experience.
    """

    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        self.setWindowTitle("Kintsugi AvA - Code Viewer & Terminal")
        self.setGeometry(150, 150, 1200, 800)
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {Colors.PRIMARY_BG.name()}; }}
            QSplitter::handle {{ background-color: {Colors.BORDER_DEFAULT.name()}; }}
            QSplitter::handle:horizontal {{ width: 1px; }}
            QSplitter::handle:vertical {{ height: 1px; }}
        """)

        # Initialize managers
        self.project_context = ProjectContextManager()
        self.editor_manager: EditorTabManager | None = None
        self.file_tree_manager: FileTreeManager | None = None
        self.terminal: IntegratedTerminal | None = None

        self._setup_ui()
        self._connect_events()

    def _setup_ui(self):
        """Sets up the user interface layout."""
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(main_splitter)

        file_tree_panel = self._create_file_tree_panel()
        right_splitter = self._create_editor_terminal_splitter()

        main_splitter.addWidget(file_tree_panel)
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([250, 950])

        self.setStatusBar(StatusBar(self.event_bus))

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
        tab_widget = QTabWidget()
        tab_widget.setTabsClosable(True)
        tab_widget.setMovable(True)
        tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)
        self.editor_manager = EditorTabManager(tab_widget)
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
        Displays completed code files in editors. This is the fix for the crash.
        """
        for filename, content in files.items():
            if self.project_context.is_valid:
                abs_path = self.project_context.get_absolute_path(filename)
                if abs_path:
                    path_key = str(abs_path.resolve())
                    self.editor_manager.create_or_update_tab(path_key, content)

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