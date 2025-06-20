# src/ava/gui/code_viewer.py
# V2: All QMessageBox popups have been removed.

from pathlib import Path
from PySide6.QtWidgets import (QMainWindow, QVBoxLayout, QWidget, QSplitter, QInputDialog, QMessageBox)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut, QCloseEvent
import qasync

from ava.gui.project_context_manager import ProjectContextManager
from ava.gui.file_tree_manager import FileTreeManager
from ava.gui.editor_tab_manager import EditorTabManager
from ava.gui.integrated_terminal import IntegratedTerminal
from ava.gui.find_replace_dialog import FindReplaceDialog
from ava.gui.quick_file_finder import QuickFileFinder
from ava.core.project_manager import ProjectManager
from .status_bar import StatusBar


class CodeViewerWindow(QMainWindow):
    """
    The main code viewing and interaction window with enhanced IDE features.
    """

    def __init__(self, event_bus, project_manager: ProjectManager):
        super().__init__()
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.project_context = ProjectContextManager()
        self.editor_manager = None
        self.file_tree_manager = None
        self.terminal = None

        # Enhanced IDE features
        self.find_replace_dialog = None
        self.quick_file_finder = None
        self.auto_save_timer = QTimer()

        self.setWindowTitle("Avakin - Code Viewer")
        self.setGeometry(100, 100, 1400, 900)
        self._init_ui()
        self._create_menus()
        self._setup_shortcuts()
        self._connect_events()
        self._setup_auto_save()

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

        # Use our event-driven status bar
        self.status_bar = StatusBar(self.event_bus)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _create_file_tree_panel(self) -> QWidget:
        from PySide6.QtWidgets import QTreeWidget
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        tree_widget = QTreeWidget()
        self.file_tree_manager = FileTreeManager(tree_widget)
        self.file_tree_manager.set_file_selection_callback(self._on_file_selected)
        self.file_tree_manager.file_rename_requested.connect(self._on_file_rename_requested)
        self.file_tree_manager.file_delete_requested.connect(self._on_file_delete_requested)
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

    def _create_menus(self):
        """Create menu bar with file operations."""
        menubar = self.menuBar()

        # File menu
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

        # Edit menu
        edit_menu = menubar.addMenu("Edit")

        find_action = QAction("Find/Replace", self)
        find_action.setShortcut(QKeySequence.StandardKey.Find)
        find_action.triggered.connect(self._show_find_replace)
        edit_menu.addAction(find_action)

        # Go menu
        go_menu = menubar.addMenu("Go")

        quick_open_action = QAction("Go to File...", self)
        quick_open_action.setShortcut(QKeySequence("Ctrl+P"))
        quick_open_action.triggered.connect(self._show_quick_file_finder)
        go_menu.addAction(quick_open_action)

    def _setup_shortcuts(self):
        """Set up additional keyboard shortcuts."""
        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self._save_current_file)

        find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        find_shortcut.activated.connect(self._show_find_replace)

        quick_open_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        quick_open_shortcut.activated.connect(self._show_quick_file_finder)

    def _setup_auto_save(self):
        """Set up auto-save functionality."""
        self.auto_save_timer.timeout.connect(self._auto_save)
        self.auto_save_timer.start(30000)

    def _connect_events(self):
        """Connects signals to the event bus."""
        self.terminal.command_entered.connect(
            lambda cmd, sid: self.event_bus.emit("terminal_command_entered", cmd, sid)
        )

    # === File Operations ===

    def _on_file_rename_requested(self, path_to_rename: Path):
        if not self.project_context.is_valid or not self.project_manager.active_project_path:
            self.status_bar.showMessage("Cannot rename: No active project.", 3000)
            return

        is_dir = path_to_rename.is_dir()
        item_type = "directory" if is_dir else "file"
        old_name = path_to_rename.name

        new_name, ok = QInputDialog.getText(self, f"Rename {item_type}", f"Enter new name for {old_name}:",
                                            text=old_name)

        if not (ok and new_name and new_name != old_name):
            return

        if '/' in new_name or '\\' in new_name:
            self.status_bar.showMessage("Error: New name cannot contain path separators.", 3000)
            return

        old_relative_path = path_to_rename.relative_to(self.project_manager.active_project_path)
        new_relative_path = old_relative_path.parent / new_name

        success = self.project_manager.rename_file(str(old_relative_path), str(new_relative_path))

        if success:
            new_absolute_path = self.project_manager.active_project_path / new_relative_path
            old_absolute_path_str = str(path_to_rename.resolve())

            if is_dir:
                new_absolute_path_str = str(new_absolute_path.resolve())
                for open_file_path_str in list(self.editor_manager.editors.keys()):
                    if open_file_path_str.startswith(old_absolute_path_str):
                        new_child_path_str = open_file_path_str.replace(old_absolute_path_str, new_absolute_path_str, 1)
                        self.editor_manager.handle_file_rename(open_file_path_str, new_child_path_str)
            else:
                self.editor_manager.handle_file_rename(old_absolute_path_str, str(new_absolute_path.resolve()))

            self.file_tree_manager.load_existing_project_tree(self.project_manager.active_project_path)
            self.status_bar.showMessage(f"Renamed to {new_name}", 2000)
        else:
            self.status_bar.showMessage(f"Failed to rename {old_name}", 3000)

    def _on_file_delete_requested(self, path_to_delete: Path):
        if not self.project_context.is_valid or not self.project_manager.active_project_path:
            self.status_bar.showMessage("Cannot delete: No active project.", 3000)
            return

        item_type = "directory" if path_to_delete.is_dir() else "file"

        reply = QMessageBox.question(
            self,
            f"Confirm Deletion",
            f"Are you sure you want to permanently delete this {item_type}?\n\n'{path_to_delete.name}'",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        relative_path = path_to_delete.relative_to(self.project_manager.active_project_path)
        success = self.project_manager.delete_path(str(relative_path))

        if success:
            self.editor_manager.handle_file_delete(str(path_to_delete.resolve()))
            self.file_tree_manager.load_existing_project_tree(self.project_manager.active_project_path)
            self.status_bar.showMessage(f"Deleted {path_to_delete.name}", 2000)
        else:
            self.status_bar.showMessage(f"Failed to delete {path_to_delete.name}", 3000)

    def _save_current_file(self):
        if self.editor_manager:
            if self.editor_manager.save_current_file():
                self.status_bar.showMessage("File saved", 2000)

    def _save_all_files(self):
        if self.editor_manager:
            if self.editor_manager.save_all_files():
                self.status_bar.showMessage("All files saved", 2000)

    def _auto_save(self):
        if self.editor_manager and self.editor_manager.has_unsaved_changes():
            self._save_all_files()
            self.status_bar.showMessage("Auto-saved all changes", 1500)

    def _close_current_tab(self):
        if self.editor_manager:
            current_index = self.editor_manager.tab_widget.currentIndex()
            if current_index >= 0:
                self.editor_manager.close_tab(current_index)

    # === Search and Navigation ===

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

    # === Project and Code Generation Handlers ===

    def get_active_file_path(self) -> str | None:
        return self.editor_manager.get_active_file_path() if self.editor_manager else None

    def prepare_for_new_project_session(self):
        # --- FIX: No longer prompt, just save everything ---
        if self.editor_manager and self.editor_manager.has_unsaved_changes():
            self.editor_manager.save_all_files()

        self.project_context.clear_context()
        self.file_tree_manager.clear_tree()
        self.editor_manager.prepare_for_new_project()
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

    def prepare_for_generation(self, filenames: list, project_path: str = None):
        is_new_project = project_path and self.project_context.set_new_project_context(project_path)

        if is_new_project:
            self.file_tree_manager.setup_new_project_tree(
                self.project_context.project_root, filenames
            )
            print(f"[CodeViewer] Prepared for new project generation: {len(filenames)} files")
            self.show_window()
        elif self.project_context.validate_existing_context():
            self.file_tree_manager.add_placeholders_for_new_files(filenames)
            self._prepare_tabs_for_modification(filenames)
            print(f"[CodeViewer] Prepared for modification: {len(filenames)} files")
            self.show_window()

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

        if self.project_context.is_valid and self.project_context.project_root:
            print("[CodeViewer] Forcing file tree refresh from disk.")
            self.file_tree_manager.load_existing_project_tree(self.project_context.project_root)

    # === Event Handlers ===

    def _on_file_selected(self, file_path: Path):
        self.editor_manager.open_file_in_tab(file_path)

    def _on_tab_close_requested(self, index: int):
        self.editor_manager.close_tab(index)

    def show_window(self):
        if not self.isVisible():
            self.show()
        self.activateWindow()
        self.raise_()

    # === Error Handling & Highlighting ===

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

    # === Window Management ===

    def closeEvent(self, event: QCloseEvent):
        """Handle window close event - save all changes silently."""
        if self.editor_manager and self.editor_manager.has_unsaved_changes():
            self.editor_manager.save_all_files()
        event.accept()