# gui/code_viewer.py
# FINAL: Integrates the proper multi-tab terminal.

from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QSplitter
from PySide6.QtCore import Qt

from gui.project_context_manager import ProjectContextManager
from gui.file_tree_manager import FileTreeManager
from gui.editor_tab_manager import EditorTabManager
from gui.integrated_terminal import IntegratedTerminal
from core.project_manager import ProjectManager


class CodeViewerWindow(QMainWindow):
    """
    The main code viewing and interaction window.
    """

    def __init__(self, event_bus, project_manager: ProjectManager):
        super().__init__()
        self.event_bus = event_bus
        self.project_manager = project_manager
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

        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        file_tree_panel = self._create_file_tree_panel()
        main_splitter.addWidget(file_tree_panel)

        editor_terminal_splitter = self._create_editor_terminal_splitter()
        main_splitter.addWidget(editor_terminal_splitter)

        main_splitter.setSizes([300, 1100])
        main_layout.addWidget(main_splitter)

    def _create_file_tree_panel(self) -> QWidget:
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
        from PySide6.QtWidgets import QTabWidget
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        tab_widget = QTabWidget()
        tab_widget.setTabsClosable(True)
        tab_widget.setMovable(True)
        tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)
        self.editor_manager = EditorTabManager(tab_widget)

        self.terminal = IntegratedTerminal(self.event_bus, self.project_manager)

        right_splitter.addWidget(tab_widget)
        right_splitter.addWidget(self.terminal)
        right_splitter.setSizes([600, 300])

        return right_splitter

    def _connect_events(self):
        """Connects signals to the event bus."""
        # The terminal inside this window will emit a command, which we route to the TaskManager
        self.terminal.command_entered.connect(
            lambda cmd, sid: self.event_bus.emit("terminal_command_entered", cmd, sid)
        )

    def get_active_file_path(self) -> str | None:
        return self.editor_manager.get_active_file_path()

    def prepare_for_new_project_session(self):
        self.project_context.clear_context()
        self.file_tree_manager.clear_tree()
        self.editor_manager.prepare_for_new_project()
        # self.terminal.clear_output() # This needs to be handled per-tab
        print("[CodeViewer] Prepared for new project session")

    def load_project(self, project_path_str: str):
        """Loads an existing project into the viewer."""
        project_path = Path(project_path_str)
        if self.project_context.set_new_project_context(project_path_str):
            self.file_tree_manager.load_existing_project_tree(project_path)
            self.terminal.set_project_manager(self.project_manager)
            print(f"[CodeViewer] Loaded project: {project_path.name}")

    def _on_file_selected(self, file_path: Path):
        self.editor_manager.open_file_in_tab(file_path)

    def _on_tab_close_requested(self, index: int):
        self.editor_manager.close_tab(index)

    def show_window(self):
        if not self.isVisible():
            self.show()
        self.activateWindow()
        self.raise_()

    def show_fix_button(self):
        # This might need to be routed to a specific active terminal tab in the future
        pass

    def hide_fix_button(self):
        pass

    def highlight_error_in_editor(self, file_path: Path, line_number: int):
        if self.editor_manager:
            self.editor_manager.highlight_error(str(file_path), line_number)

    def clear_all_error_highlights(self):
        if self.editor_manager:
            self.editor_manager.clear_all_error_highlights()