# src/ava/gui/code_viewer.py
from pathlib import Path
from PySide6.QtWidgets import (QMainWindow, QVBoxLayout, QWidget, QSplitter,
                               QTabWidget, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut, QCloseEvent
import qasync

from src.ava.core.event_bus import EventBus
from src.ava.core.project_manager import ProjectManager
from src.ava.gui.project_context_manager import ProjectContextManager
from src.ava.gui.file_tree_manager import FileTreeManager
from src.ava.gui.editor_tab_manager import EditorTabManager
from src.ava.gui.integrated_terminal import IntegratedTerminal
from src.ava.gui.find_replace_dialog import FindReplaceDialog
from src.ava.gui.quick_file_finder import QuickFileFinder
from src.ava.gui.status_bar import StatusBar
from src.ava.services.lsp_client_service import LSPClientService # <-- NEW


class CodeViewerWindow(QMainWindow):
    """
    The main code viewing and interaction window with enhanced IDE features.
    """

    def __init__(self, event_bus: EventBus, project_manager: ProjectManager, lsp_client: LSPClientService): # <-- Add lsp_client
        super().__init__()
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.lsp_client = lsp_client # <-- Store lsp_client
        self.project_context = ProjectContextManager()
        self.editor_manager: EditorTabManager = None
        self.file_tree_manager: FileTreeManager = None
        self.terminal: IntegratedTerminal = None

        self.find_replace_dialog: FindReplaceDialog = None
        self.quick_file_finder: QuickFileFinder = None

        self.setWindowTitle("Kintsugi AvA - Code Viewer")
        self.setGeometry(100, 100, 1400, 900)
        self._init_ui()
        self._create_menus()
        self._setup_shortcuts()
        self._connect_events()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        file_tree_panel_widget = QWidget()
        file_tree_panel_layout = QVBoxLayout(file_tree_panel_widget)
        file_tree_panel_layout.setContentsMargins(0, 0, 0, 0)

        self.file_tree_manager = FileTreeManager(file_tree_panel_widget, self.project_manager, self.event_bus)
        self.file_tree_manager.set_file_selection_callback(self._on_file_selected)

        file_tree_panel_layout.addWidget(self.file_tree_manager.get_widget())

        main_splitter.addWidget(file_tree_panel_widget)

        editor_terminal_splitter = self._create_editor_terminal_splitter()
        main_splitter.addWidget(editor_terminal_splitter)
        main_splitter.setSizes([300, 1100])
        main_layout.addWidget(main_splitter)
        self.status_bar = StatusBar(self.event_bus)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _create_editor_terminal_splitter(self) -> QSplitter:
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        tab_widget = QTabWidget()
        tab_widget.setTabsClosable(True)
        tab_widget.setMovable(True)
        tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)
        self.editor_manager = EditorTabManager(tab_widget, self.event_bus, self.project_manager)
        self.editor_manager.set_lsp_client(self.lsp_client) # <-- Pass LSP client to the manager
        self.terminal = IntegratedTerminal(self.event_bus, self.project_manager)
        right_splitter.addWidget(tab_widget)
        right_splitter.addWidget(self.terminal)
        right_splitter.setSizes([600, 300])
        return right_splitter

    def _create_menus(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_current_file)
        file_menu.addAction(save_action)
        save_all_action = QAction("Save All", self)
        save_all_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_all_action.triggered.connect(self._save_all_files)
        file_menu.addAction(save_all_action)
        file_menu.addSeparator()
        close_tab_action = QAction("Close Tab", self)
        close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        close_tab_action.triggered.connect(self._close_current_tab)
        file_menu.addAction(close_tab_action)
        edit_menu = menubar.addMenu("Edit")
        find_action = QAction("Find/Replace", self)
        find_action.setShortcut(QKeySequence.StandardKey.Find)
        find_action.triggered.connect(self._show_find_replace)
        edit_menu.addAction(find_action)
        go_menu = menubar.addMenu("Go")
        quick_open_action = QAction("Go to File...", self)
        quick_open_action.setShortcut(QKeySequence("Ctrl+P"))
        quick_open_action.triggered.connect(self._show_quick_file_finder)
        go_menu.addAction(quick_open_action)

    def _setup_shortcuts(self):
        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self._save_current_file)
        find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        find_shortcut.activated.connect(self._show_find_replace)
        quick_open_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        quick_open_shortcut.activated.connect(self._show_quick_file_finder)

    def _connect_events(self):
        self.terminal.command_entered.connect(
            lambda cmd, sid: self.event_bus.emit("terminal_command_entered", cmd, sid)
        )
        self.event_bus.subscribe("code_generation_complete", self._on_code_generation_complete)

    def _on_code_generation_complete(self, files: dict):
        """When code generation is done, refresh the file tree."""
        if self.file_tree_manager:
            self.file_tree_manager.refresh_tree_from_disk()
        self.display_code(files) # Also update the editor tabs

    def _save_current_file(self):
        if self.editor_manager:
            if self.editor_manager.save_current_file():
                self.status_bar.showMessage("File saved", 2000)

    def _save_all_files(self):
        if self.editor_manager:
            if self.editor_manager.save_all_files():
                self.status_bar.showMessage("All files saved", 2000)

    def _close_current_tab(self):
        if self.editor_manager:
            current_index = self.editor_manager.tab_widget.currentIndex()
            if current_index >= 0:
                self.editor_manager.close_tab(current_index)

    def _show_find_replace(self):
        if not self.find_replace_dialog:
            self.find_replace_dialog = FindReplaceDialog(self)
        current_editor = self._get_current_editor()
        if current_editor:
            self.find_replace_dialog.set_editor(current_editor)
            cursor = current_editor.textCursor()
            if cursor.hasSelection():
                self.find_replace_dialog.set_find_text(cursor.selectedText())
        self.find_replace_dialog.show_and_focus()

    def _show_quick_file_finder(self):
        if not self.project_context.is_valid:
            self.status_bar.showMessage("No project loaded to search.", 2000)
            return
        if not self.quick_file_finder:
            self.quick_file_finder = QuickFileFinder(self)
            self.quick_file_finder.set_file_open_callback(self._open_file_from_finder)
        self.quick_file_finder.set_project_root(self.project_context.project_root)
        self.quick_file_finder.show_and_focus()

    def _open_file_from_finder(self, file_path: str):
        file_path_obj = Path(file_path)
        if file_path_obj.exists():
            self.editor_manager.open_file_in_tab(file_path_obj)
            self.status_bar.showMessage(f"Opened {file_path_obj.name}", 2000)

    def _get_current_editor(self):
        if self.editor_manager:
            current_path = self.editor_manager.get_active_file_path()
            if current_path and current_path in self.editor_manager.editors:
                return self.editor_manager.editors[current_path]
        return None

    def get_active_file_path(self) -> str | None:
        return self.editor_manager.get_active_file_path() if self.editor_manager else None

    def prepare_for_new_project_session(self):
        if self.editor_manager:
            self.editor_manager.prepare_for_new_project()
        self.project_context.clear_context()
        if self.file_tree_manager: self.file_tree_manager.clear_tree()
        print("[CodeViewer] Prepared for new project session")

    def load_project(self, project_path_str: str):
        project_path = Path(project_path_str)
        if self.project_context.set_new_project_context(project_path_str):
            self.file_tree_manager.load_existing_project_tree(project_path)
            self.terminal.set_project_manager(self.project_manager)
            if self.quick_file_finder:
                self.quick_file_finder.set_project_root(project_path)
            print(f"[CodeViewer] Loaded project: {project_path.name}")
            self.status_bar.showMessage(f"Loaded project: {project_path.name}", 3000)

    def prepare_for_generation(self, filenames: list, project_path: str = None, is_modification: bool = False):
        if not is_modification:
            is_new_project = project_path and self.project_context.set_new_project_context(project_path)
            if is_new_project:
                self.file_tree_manager.setup_new_project_tree(
                    self.project_context.project_root, filenames
                )
                print(f"[CodeViewer] Prepared for new project generation: {len(filenames)} files")
                self.show_window()
        else:
            if self.project_context.validate_existing_context():
                self.file_tree_manager.add_placeholders_for_new_files(filenames)
                self._prepare_tabs_for_modification(filenames)
                print(f"[CodeViewer] Prepared for modification: {len(filenames)} files")
                self.show_window()
            else:
                print("[CodeViewer] ERROR: Modification requested, but existing project context is invalid.")

    def _prepare_tabs_for_modification(self, filenames: list):
        if self.project_context.is_valid:
            for filename in filenames:
                abs_path = self.project_context.get_absolute_path(filename)
                if abs_path and abs_path.is_file():
                    self.editor_manager.open_file_in_tab(abs_path)

    def stream_code_chunk(self, filename: str, chunk: str):
        if self.project_context.is_valid:
            abs_path = self.project_context.get_absolute_path(filename)
            if abs_path:
                self.editor_manager.stream_content_to_editor(str(abs_path.resolve()), chunk)

    @qasync.Slot(dict)
    def display_code(self, files: dict):
        print(f"[CodeViewer] Displaying {len(files)} file(s) and refreshing UI.")
        for filename, content in files.items():
            if self.project_context.is_valid:
                abs_path = self.project_context.get_absolute_path(filename)
                if abs_path:
                    path_key = str(abs_path.resolve())
                    self.editor_manager.create_or_update_tab(path_key, content)
                else:
                    print(f"[CodeViewer] Warning: Could not resolve absolute path for '{filename}'.")
            else:
                print("[CodeViewer] Warning: Project context is invalid, cannot display code.")
        # The tree refresh is now handled by the _on_code_generation_complete slot.
        # This prevents a double refresh.

    def _on_file_selected(self, file_path: Path):
        self.editor_manager.open_file_in_tab(file_path)

    def _on_tab_close_requested(self, index: int):
        self.editor_manager.close_tab(index)

    def show_window(self):
        if not self.isVisible():
            self.show()
        self.activateWindow()
        self.raise_()

    def highlight_error_in_editor(self, file_path: Path, line_number: int):
        if self.editor_manager:
            self.editor_manager.highlight_error(str(file_path), line_number)

    def clear_all_error_highlights(self):
        if self.editor_manager:
            self.editor_manager.clear_all_error_highlights()
        self.hide_fix_button()

    def show_fix_button(self):
        if self.terminal:
            self.terminal.show_fix_button()

    def hide_fix_button(self):
        if self.terminal:
            self.terminal.hide_fix_button()

    def closeEvent(self, event: QCloseEvent):
        if self.editor_manager and self.editor_manager.has_unsaved_changes():
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         "You have unsaved changes. Save all before exiting?",
                                         QMessageBox.StandardButton.SaveAll | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.SaveAll:
                if not self.editor_manager.save_all_files():
                    event.ignore()
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        event.accept()