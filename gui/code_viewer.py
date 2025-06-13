# kintsugi_ava/gui/code_viewer.py
# V10: Makes generation prep context-aware and fixes diff highlighting bugs.

from pathlib import Path
from unidiff import PatchSet

from PySide6.QtGui import QTextCursor, QTextBlockFormat, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter,
    QTabWidget, QTextEdit, QTreeWidget, QTreeWidgetItem, QLabel
)
from PySide6.QtCore import Qt, Slot

from .components import Colors, Typography
from .code_viewer_helpers import PythonHighlighter
from .integrated_terminal import IntegratedTerminal
from .status_bar import StatusBar


class CodeViewerWindow(QMainWindow):
    """
    A window for displaying a file tree, tabbed code editors, and an
    integrated terminal, styled for a seamless IDE-like experience.
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
        self.editors = {}
        self.project_root_for_load = None

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(main_splitter)
        file_tree_panel = self._create_file_tree_panel()
        right_splitter = self._create_editor_terminal_splitter()
        main_splitter.addWidget(file_tree_panel)
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([250, 950])
        self.setStatusBar(StatusBar(self.event_bus))

    def get_active_file_path(self) -> str | None:
        """Returns the path key of the currently visible editor tab."""
        current_index = self.tab_widget.currentIndex()
        if current_index == -1:
            return None
        return self.tab_widget.tabToolTip(current_index)

    def _create_file_tree_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("Project Files")
        self.file_tree.setStyleSheet(f"""
            QTreeWidget {{ border: none; background-color: {Colors.SECONDARY_BG.name()}; }}
            QHeaderView::section {{ background-color: {Colors.SECONDARY_BG.name()}; color: {Colors.TEXT_SECONDARY.name()}; border: none; padding: 4px; }}
        """)
        self.file_tree.itemDoubleClicked.connect(self._on_file_selected)
        layout.addWidget(self.file_tree)
        return panel

    def _create_editor_terminal_splitter(self) -> QSplitter:
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab)
        welcome_label = QLabel("Code will appear here when generated.")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setFont(Typography.get_font(18))
        welcome_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")
        self.tab_widget.addTab(welcome_label, "Welcome")
        self.terminal = IntegratedTerminal(self.event_bus)
        self.terminal.command_entered.connect(lambda cmd: self.event_bus.emit("terminal_command_entered", cmd))
        self.event_bus.subscribe("terminal_output_received", self.terminal.append_output)
        right_splitter.addWidget(self.tab_widget)
        right_splitter.addWidget(self.terminal)
        right_splitter.setSizes([600, 200])
        return right_splitter

    def _setup_new_project_view(self, filenames: list):
        self.file_tree.clear()
        self.editors.clear()
        self.project_root_for_load = None
        while self.tab_widget.count() > 0: self.tab_widget.removeTab(0)
        project_root_item = QTreeWidgetItem(["generated_project"])
        self.file_tree.addTopLevelItem(project_root_item)
        for filename in filenames:
            self._add_file_to_tree(project_root_item, filename.split('/'))
            self._create_editor_tab(filename)
        self.show_window()

    def _add_file_to_tree(self, parent_item, path_parts):
        if not path_parts: return
        part = path_parts[0]
        child_item = next(
            (parent_item.child(i) for i in range(parent_item.childCount()) if parent_item.child(i).text(0) == part),
            None)
        if not child_item:
            child_item = QTreeWidgetItem([part])
            parent_item.addChild(child_item)
        self._add_file_to_tree(child_item, path_parts[1:])

    @Slot(dict)
    def display_code(self, files: dict):
        self._setup_new_project_view(list(files.keys()))
        for filename, content in files.items():
            if filename in self.editors: self.editors[filename].setPlainText(content)

    def _prepare_tabs_for_modification(self, filenames: list):
        """Prepares editor tabs for files that will be modified by opening them if not already open."""
        for filename in filenames:
            if not self.project_root_for_load: continue  # Safety check

            # The key for editors is the absolute path string.
            abs_path_str = str(self.project_root_for_load / filename)

            # Check if a tab for this file is already open.
            is_open = False
            for i in range(self.tab_widget.count()):
                if self.tab_widget.tabToolTip(i) == abs_path_str:
                    self.tab_widget.setCurrentIndex(i)  # Bring it to front.
                    is_open = True
                    break

            if not is_open:
                # If not open, create a new tab for it, simulating a user double-click.
                file_path = Path(abs_path_str)
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        self._create_editor_tab(abs_path_str)
                        self.editors[abs_path_str].setPlainText(content)
                        self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)
                    except Exception as e:
                        print(f"[CodeViewer] Error opening file tab for modification: {e}")
        self.show_window()

    @Slot(str, str, str)
    def apply_diff_highlighting(self, filename: str, new_content: str, patch_content: str):
        """Receives patched code, updates the editor, and highlights the changes."""
        # Convert the relative filename from the event into the absolute path key used by the editor dict.
        if not self.project_root_for_load: return
        abs_path_key = str(self.project_root_for_load / filename)

        if abs_path_key not in self.editors:
            return

        editor = self.editors[abs_path_key]
        document = editor.document()
        editor.setPlainText(new_content)

        add_block_format = QTextBlockFormat()
        add_block_format.setBackground(QColor(Colors.DIFF_ADD_BG))

        patch_str = f"--- a/{filename}\n+++ b/{filename}\n{patch_content}"
        try:
            patch_set = PatchSet(patch_str)
            if not patch_set: return

            patched_file = patch_set[0]
            cursor = QTextCursor(document)

            for hunk in patched_file:
                current_target_line = hunk.target_start
                for line in hunk:
                    if line.is_added:
                        cursor.movePosition(QTextCursor.MoveOperation.Start)
                        cursor.movePosition(QTextCursor.MoveOperation.NextBlock,
                                            QTextCursor.MoveMode.MoveAnchor,
                                            current_target_line - 1)
                        cursor.setBlockFormat(add_block_format)
                        current_target_line += 1
                    elif line.is_context:
                        current_target_line += 1
        except Exception as e:
            print(f"[CodeViewer] Error applying diff highlighting: {e}")

    @Slot(list)
    def prepare_for_generation(self, filenames: list):
        self.terminal.clear_output()
        # If project_root_for_load is None, it's a brand new, non-saved project.
        if self.project_root_for_load is None:
            self._setup_new_project_view(filenames)
        else:  # Otherwise, it's a modification on an existing, loaded project.
            self._prepare_tabs_for_modification(filenames)

    @Slot(str, str)
    def stream_code_chunk(self, filename: str, chunk: str):
        if filename in self.editors:
            editor = self.editors[filename]
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(chunk)
            editor.ensureCursorVisible()

    def _create_editor_tab(self, path_key: str):
        editor = QTextEdit()
        editor.setFont(Typography.get_font(11, family="JetBrains Mono"))
        PythonHighlighter(editor.document())
        tab_index = self.tab_widget.addTab(editor, Path(path_key).name)
        self.tab_widget.setTabToolTip(tab_index, path_key)
        self.editors[path_key] = editor

    @Slot(str)
    def load_project(self, project_path_str: str):
        self.file_tree.clear()
        project_path = Path(project_path_str)
        if not project_path.is_dir(): return
        self.project_root_for_load = project_path
        root_item = QTreeWidgetItem([project_path.name])
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(project_path))
        self.file_tree.addTopLevelItem(root_item)
        root_item.setExpanded(True)
        self._populate_tree_from_disk(root_item, project_path)

    def _populate_tree_from_disk(self, parent_item, path):
        ignore_list = {'.git', '__pycache__', 'venv', '.venv', 'node_modules', 'rag_db'}
        try:
            for p in sorted(path.iterdir()):
                if p.name in ignore_list: continue
                child_item = QTreeWidgetItem([p.name])
                child_item.setData(0, Qt.ItemDataRole.UserRole, str(p))
                parent_item.addChild(child_item)
                if p.is_dir(): self._populate_tree_from_disk(child_item, p)
        except PermissionError:
            pass

    @Slot(QTreeWidgetItem, int)
    def _on_file_selected(self, item: QTreeWidgetItem, column: int):
        abs_path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not abs_path_str: return
        file_path = Path(abs_path_str)
        if file_path.is_file():
            if abs_path_str in self.editors:
                for i in range(self.tab_widget.count()):
                    if self.tab_widget.tabToolTip(i) == abs_path_str:
                        self.tab_widget.setCurrentIndex(i)
                        return
                return
            try:
                content = file_path.read_text(encoding='utf-8')
                self._create_editor_tab(abs_path_str)
                self.editors[abs_path_str].setPlainText(content)
                self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")

    def _close_tab(self, index):
        tooltip = self.tab_widget.tabToolTip(index)
        if tooltip in self.editors: del self.editors[tooltip]
        self.tab_widget.removeTab(index)

    def show_window(self):
        if not self.isVisible():
            self.show()
        else:
            self.activateWindow(); self.raise_()