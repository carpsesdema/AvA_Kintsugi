# kintsugi_ava/gui/code_viewer.py
# V3: Now supports real-time streaming of code into its editors.

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter,
    QTabWidget, QTextEdit, QTreeWidget, QTreeWidgetItem, QLabel
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QTextCursor

from .components import Colors, Typography
from .code_viewer_helpers import PythonHighlighter


class CodeViewerWindow(QMainWindow):
    """
    A window for displaying a file tree and tabbed code editors,
    now with support for real-time streaming updates.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kintsugi AvA - Code Viewer")
        self.setGeometry(150, 150, 1000, 700)
        self.setStyleSheet(f"background-color: {Colors.PRIMARY_BG.name()};")

        self.editors = {}  # A dictionary to track open editors by filename

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

    @Slot(dict)
    def display_code(self, files: dict):
        """(Legacy) Displays a completed dictionary of files."""
        self._setup_new_project_view(list(files.keys()))
        for filename, content in files.items():
            if filename in self.editors:
                self.editors[filename].setPlainText(content)

    @Slot(list)
    def prepare_for_generation(self, filenames: list):
        """Prepares the viewer by creating empty tabs for upcoming files."""
        self._setup_new_project_view(filenames)

    @Slot(str, str)
    def stream_code_chunk(self, filename: str, chunk: str):
        """Streams a chunk of code into the correct editor tab."""
        if filename in self.editors:
            editor = self.editors[filename]
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(chunk)
            editor.ensureCursorVisible()

    def _setup_new_project_view(self, filenames: list):
        """Clears the old project and sets up tabs for the new one."""
        self.file_tree.clear()
        self.editors.clear()
        while self.tab_widget.count() > 0:
            self.tab_widget.removeTab(0)

        for filename in filenames:
            file_item = QTreeWidgetItem(self.file_tree, [filename])

            editor = QTextEdit()
            editor.setFont(Typography.get_font(11, family="JetBrains Mono"))
            highlighter = PythonHighlighter(editor.document())

            tab_index = self.tab_widget.addTab(editor, filename)
            self.editors[filename] = editor

        self.show_window()

    def _close_tab(self, index):
        widget = self.tab_widget.widget(index)
        if widget and isinstance(widget, QTextEdit):
            filename_to_remove = next((name for name, editor in self.editors.items() if editor == widget), None)
            if filename_to_remove:
                del self.editors[filename_to_remove]
        self.tab_widget.removeTab(index)

    def show_window(self):
        if not self.isVisible():
            self.show()
        else:
            self.activateWindow(); self.raise_()