# kintsugi_ava/gui/code_viewer.py
# V4: Can now load a project directory into the file tree.

from pathlib import Path

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter,
    QTabWidget, QTextEdit, QTreeWidget, QTreeWidgetItem, QLabel
)
from PySide6.QtCore import Qt, Slot
from .components import Colors, Typography
from .code_viewer_helpers import PythonHighlighter

class CodeViewerWindow(QMainWindow):
    """
    A window for displaying a file tree and tabbed code editors.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kintsugi AvA - Code Viewer")
        self.setGeometry(150, 150, 1000, 700)
        self.setStyleSheet(f"background-color: {Colors.PRIMARY_BG.name()};")
        self.editors = {}
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(main_splitter)
        file_tree_panel = QWidget()
        file_tree_layout = QVBoxLayout(file_tree_panel)
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("Project Files")
        file_tree_panel.setStyleSheet("background-color: transparent; border: none;")
        file_tree_layout.addWidget(self.file_tree)
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        welcome_label = QLabel("Code will appear here when generated.")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setFont(Typography.get_font(18))
        welcome_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")
        self.tab_widget.addTab(welcome_label, "Welcome")
        main_splitter.addWidget(file_tree_panel)
        main_splitter.addWidget(self.tab_widget)
        main_splitter.setSizes([250, 750])
        self.tab_widget.tabCloseRequested.connect(self._close_tab)
        self.file_tree.itemDoubleClicked.connect(self._on_file_selected)

    @Slot(dict)
    def display_code(self, files: dict):
        self._setup_new_project_view(list(files.keys()))
        for filename, content in files.items():
            if filename in self.editors:
                self.editors[filename].setPlainText(content)

    @Slot(list)
    def prepare_for_generation(self, filenames: list):
        self._setup_new_project_view(filenames)

    @Slot(str, str)
    def stream_code_chunk(self, filename: str, chunk: str):
        if filename in self.editors:
            editor = self.editors[filename]
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(chunk)
            editor.ensureCursorVisible()

    def _setup_new_project_view(self, filenames: list):
        self.file_tree.clear()
        self.editors.clear()
        while self.tab_widget.count() > 0: self.tab_widget.removeTab(0)
        for filename in filenames:
            self._add_file_to_tree(filename)
            self._create_editor_tab(filename)
        self.show_window()

    def _add_file_to_tree(self, filename: str):
        """Adds a single file to the tree, creating parent folders as needed."""
        parts = Path(filename).parts
        current_item = self.file_tree.invisibleRootItem()
        for i, part in enumerate(parts):
            # Check if this part already exists at this level
            child_item = None
            for j in range(current_item.childCount()):
                if current_item.child(j).text(0) == part:
                    child_item = current_item.child(j)
                    break
            if child_item is None:
                child_item = QTreeWidgetItem([part])
                child_item.setData(0, Qt.ItemDataRole.UserRole, str(Path(*parts[:i+1])))
                current_item.addChild(child_item)
            current_item = child_item
        return current_item

    def _create_editor_tab(self, filename: str):
        editor = QTextEdit()
        editor.setFont(Typography.get_font(11, family="JetBrains Mono"))
        highlighter = PythonHighlighter(editor.document())
        tab_index = self.tab_widget.addTab(editor, Path(filename).name)
        self.tab_widget.setTabToolTip(tab_index, filename)
        self.editors[filename] = editor

    @Slot(str)
    def load_project(self, project_path_str: str):
        """Loads an entire project directory into the file tree."""
        self.file_tree.clear()
        project_path = Path(project_path_str)
        if not project_path.is_dir(): return

        root_item = QTreeWidgetItem([project_path.name])
        self.file_tree.addTopLevelItem(root_item)

        for file_path in sorted(project_path.rglob('*')):
            if any(part in ['.git', '__pycache__', 'venv', '.venv'] for part in file_path.parts):
                continue
            if file_path.is_file():
                # This logic is a bit complex, might simplify later
                relative_path = file_path.relative_to(project_path.parent)
                self._add_file_to_tree(str(relative_path))

    @Slot(QTreeWidgetItem, int)
    def _on_file_selected(self, item: QTreeWidgetItem, column: int):
        """Handles opening a file when double-clicked in the tree."""
        file_path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if file_path_str and Path(file_path_str).is_file():
            # Check if tab is already open
            for i in range(self.tab_widget.count()):
                if self.tab_widget.tabToolTip(i) == file_path_str:
                    self.tab_widget.setCurrentIndex(i)
                    return
            # If not, create new tab and load content
            self._create_editor_tab(file_path_str)
            content = Path(file_path_str).read_text(encoding='utf-8')
            self.editors[file_path_str].setPlainText(content)

    def _close_tab(self, index):
        widget = self.tab_widget.widget(index)
        if widget and isinstance(widget, QTextEdit):
            filename_to_remove = next((name for name, editor in self.editors.items() if editor == widget), None)
            if filename_to_remove:
                del self.editors[filename_to_remove]
        self.tab_widget.removeTab(index)

    def show_window(self):
        if not self.isVisible(): self.show()
        else: self.activateWindow(); self.raise_()