# kintsugi_ava/gui/code_viewer.py
# V5: Now includes an integrated terminal in a split view.

from pathlib import Path

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter,
    QTabWidget, QTextEdit, QTreeWidget, QTreeWidgetItem, QLabel
)
from PySide6.QtCore import Qt, Slot
from .components import Colors, Typography
from .code_viewer_helpers import PythonHighlighter
from .integrated_terminal import IntegratedTerminal


class CodeViewerWindow(QMainWindow):
    """
    A window for displaying a file tree, tabbed code editors, and an
    integrated terminal for project interaction.
    """

    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        self.setWindowTitle("Kintsugi AvA - Code Viewer & Terminal")
        self.setGeometry(150, 150, 1200, 800)
        self.setStyleSheet(f"background-color: {Colors.PRIMARY_BG.name()};")
        self.editors = {}

        # Main horizontal splitter (File Tree | Editor/Terminal)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(main_splitter)

        # Left side: File Tree
        file_tree_panel = self._create_file_tree_panel()
        main_splitter.addWidget(file_tree_panel)

        # Right side: Vertical splitter (Editor Tabs / Terminal)
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top-right: Tabbed code editors
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        welcome_label = QLabel("Code will appear here when generated.")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setFont(Typography.get_font(18))
        welcome_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")
        self.tab_widget.addTab(welcome_label, "Welcome")
        right_splitter.addWidget(self.tab_widget)

        # Bottom-right: Integrated Terminal
        self.terminal = IntegratedTerminal(self.event_bus)
        right_splitter.addWidget(self.terminal)

        # Add right-side splitter to the main splitter
        main_splitter.addWidget(right_splitter)

        # Set initial sizes
        main_splitter.setSizes([250, 950])
        right_splitter.setSizes([600, 200])

        # Connect signals
        self.tab_widget.tabCloseRequested.connect(self._close_tab)
        self.file_tree.itemDoubleClicked.connect(self._on_file_selected)

        # Connect terminal events
        self.terminal.command_entered.connect(
            lambda cmd: self.event_bus.emit("terminal_command_entered", cmd)
        )
        self.event_bus.subscribe("terminal_output_received", self.terminal.append_output)

    def _create_file_tree_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("Project Files")
        panel.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(self.file_tree)
        return panel

    @Slot(dict)
    def display_code(self, files: dict):
        self._setup_new_project_view(list(files.keys()))
        for filename, content in files.items():
            if filename in self.editors:
                self.editors[filename].setPlainText(content)

    @Slot(list)
    def prepare_for_generation(self, filenames: list):
        self.terminal.clear_output()
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
        parts = Path(filename).parts
        current_item = self.file_tree.invisibleRootItem()
        for i, part in enumerate(parts):
            child_item = None
            for j in range(current_item.childCount()):
                if current_item.child(j).text(0) == part:
                    child_item = current_item.child(j)
                    break
            if child_item is None:
                child_item = QTreeWidgetItem([part])
                item_path = Path(*parts[:i + 1])
                # Store full path relative to project root for opening later
                child_item.setData(0, Qt.ItemDataRole.UserRole, str(item_path))
                current_item.addChild(child_item)
            current_item = child_item
        return current_item

    def _create_editor_tab(self, filename: str):
        editor = QTextEdit()
        editor.setFont(Typography.get_font(11, family="JetBrains Mono"))
        PythonHighlighter(editor.document())
        tab_index = self.tab_widget.addTab(editor, Path(filename).name)
        self.tab_widget.setTabToolTip(tab_index, filename)
        self.editors[filename] = editor

    @Slot(str)
    def load_project(self, project_path_str: str):
        self.file_tree.clear()
        project_path = Path(project_path_str)
        if not project_path.is_dir(): return

        # Store the project root path for resolving file clicks
        self.project_root_for_load = project_path

        # Add root item
        root_item = QTreeWidgetItem([project_path.name])
        self.file_tree.addTopLevelItem(root_item)
        root_item.setExpanded(True)

        self._populate_tree(root_item, project_path)

    def _populate_tree(self, parent_item, path):
        """Recursively populates the file tree."""
        ignore_list = {'.git', '__pycache__', 'venv', '.venv', 'node_modules', 'rag_db'}
        for p in sorted(path.iterdir()):
            if p.name in ignore_list:
                continue

            child_item = QTreeWidgetItem([p.name])
            child_item.setData(0, Qt.ItemDataRole.UserRole, str(p))  # Store full absolute path
            parent_item.addChild(child_item)
            if p.is_dir():
                self._populate_tree(child_item, p)

    @Slot(QTreeWidgetItem, int)
    def _on_file_selected(self, item: QTreeWidgetItem, column: int):
        full_path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not full_path_str: return

        file_path = Path(full_path_str)
        if file_path.is_file():
            # Use relative path for editor mapping to stay consistent
            relative_path_str = str(file_path.relative_to(self.project_root_for_load))

            for i in range(self.tab_widget.count()):
                if self.tab_widget.tabToolTip(i) == relative_path_str:
                    self.tab_widget.setCurrentIndex(i)
                    return

            try:
                content = file_path.read_text(encoding='utf-8')
                self._create_editor_tab(relative_path_str)
                self.editors[relative_path_str].setPlainText(content)
                # Switch to the new tab
                self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")

    def _close_tab(self, index):
        widget = self.tab_widget.widget(index)
        if widget and isinstance(widget, QTextEdit):
            tooltip = self.tab_widget.tabToolTip(index)
            if tooltip in self.editors:
                del self.editors[tooltip]
        self.tab_widget.removeTab(index)

    def show_window(self):
        if not self.isVisible():
            self.show()
        else:
            self.activateWindow(); self.raise_()