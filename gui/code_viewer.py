# kintsugi_ava/gui/code_viewer.py
# V2: Now can programmatically display generated code.

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter,
    QTabWidget, QTextEdit, QTreeWidget, QTreeWidgetItem, QLabel
)
from PySide6.QtCore import Qt, Slot
from .components import Colors, Typography
from .code_viewer_helpers import PythonHighlighter  # <-- Import from our new helper file


class CodeViewerWindow(QMainWindow):
    """A window for displaying a file tree and tabbed code editors."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kintsugi AvA - Code Viewer")
        self.setGeometry(150, 150, 1000, 700)
        self.setStyleSheet(f"background-color: {Colors.PRIMARY_BG.name()};")

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(main_splitter)

        # --- File Tree Panel (Left) ---
        file_tree_panel = QWidget()
        file_tree_layout = QVBoxLayout(file_tree_panel)
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("Project Files")
        file_tree_panel.setStyleSheet("background-color: transparent; border: none;")
        file_tree_layout.addWidget(self.file_tree)

        # --- Editor Tabs (Right) ---
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        # Add a placeholder welcome tab
        welcome_label = QLabel("Code will appear here when generated.")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setFont(Typography.get_font(18))
        welcome_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")
        self.tab_widget.addTab(welcome_label, "Welcome")

        main_splitter.addWidget(file_tree_panel)
        main_splitter.addWidget(self.tab_widget)
        main_splitter.setSizes([250, 750])  # Initial size ratio

    @Slot(dict)
    def display_code(self, files: dict):
        """
        Receives a dictionary of {filename: content} and displays each
        file in its own tab, populating the file tree.
        """
        print(f"[CodeViewer] Received code to display: {list(files.keys())}")
        self.file_tree.clear()

        # Clear any existing file tabs
        while self.tab_widget.count() > 0:
            self.tab_widget.removeTab(0)

        for filename, content in files.items():
            # Add to file tree
            file_item = QTreeWidgetItem(self.file_tree, [filename])

            # Add file to a new editor tab
            editor = QTextEdit()
            editor.setFont(Typography.get_font(11, family="JetBrains Mono"))
            editor.setPlainText(content)

            # This is the magic: apply syntax highlighting to the document
            highlighter = PythonHighlighter(editor.document())

            self.tab_widget.addTab(editor, filename)

        # Auto-show the window if it's hidden
        self.show_window()

    def show_window(self):
        """Helper method to show and activate the window."""
        if not self.isVisible():
            self.show()
        else:
            self.activateWindow()
            self.raise_()  # Bring to the very front