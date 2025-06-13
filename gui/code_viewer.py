# kintsugi_ava/gui/code_viewer.py
# V6: Refined UI styling for a seamless look and improved file handling logic.

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
    integrated terminal, styled for a seamless IDE-like experience.
    """

    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        self.setWindowTitle("Kintsugi AvA - Code Viewer & Terminal")
        self.setGeometry(150, 150, 1200, 800)
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {Colors.PRIMARY_BG.name()};
            }}
            QSplitter::handle {{
                background-color: {Colors.BORDER_DEFAULT.name()};
            }}
            QSplitter::handle:horizontal {{
                width: 1px;
            }}
            QSplitter::handle:vertical {{
                height: 1px;
            }}
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
        self.terminal.command_entered.connect(
            lambda cmd: self.event_bus.emit("terminal_command_entered", cmd)
        )
        self.event_bus.subscribe("terminal_output_received", self.terminal.append_output)

        right_splitter.addWidget(self.tab_widget)
        right_splitter.addWidget(self.terminal)
        right_splitter.setSizes([600, 200])
        return right_splitter

    def _setup_new_project_view(self, filenames: list):
        """Clears and sets up the viewer for a new set of generated files."""
        self.file_tree.clear()
        self.editors.clear()
        self.project_root_for_load = None  # This is a generated project, not loaded
        while self.tab_widget.count() > 0: self.tab_widget.removeTab(0)

        # This is for display purposes only, doesn't represent a real path
        project_root_item = QTreeWidgetItem(["generated_project"])
        self.file_tree.addTopLevelItem(project_root_item)

        for filename in filenames:
            self._add_file_to_tree(project_root_item, filename.split('/'))
            self._create_editor_tab(filename)
        self.show_window()

    def _add_file_to_tree(self, parent_item, path_parts):
        """Recursively adds file/folder parts to the tree for display."""
        if not path_parts:
            return

        part = path_parts[0]
        child_item = None
        for i in range(parent_item.childCount()):
            if parent_item.child(i).text(0) == part:
                child_item = parent_item.child(i)
                break

        if not child_item:
            child_item = QTreeWidgetItem([part])
            parent_item.addChild(child_item)

        self._add_file_to_tree(child_item, path_parts[1:])

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

    def _create_editor_tab(self, path_key: str):
        """Creates a new tab for an editor. The key can be relative or absolute."""
        editor = QTextEdit()
        editor.setFont(Typography.get_font(11, family="JetBrains Mono"))
        PythonHighlighter(editor.document())
        tab_index = self.tab_widget.addTab(editor, Path(path_key).name)
        self.tab_widget.setTabToolTip(tab_index, path_key)
        self.editors[path_key] = editor

    @Slot(str)
    def load_project(self, project_path_str: str):
        """Loads a real project directory into the file tree."""
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
        """Recursively scans the disk and populates the file tree."""
        ignore_list = {'.git', '__pycache__', 'venv', '.venv', 'node_modules', 'rag_db'}
        try:
            for p in sorted(path.iterdir()):
                if p.name in ignore_list:
                    continue

                child_item = QTreeWidgetItem([p.name])
                child_item.setData(0, Qt.ItemDataRole.UserRole, str(p))  # Store full absolute path
                parent_item.addChild(child_item)
                if p.is_dir():
                    self._populate_tree_from_disk(child_item, p)
        except PermissionError:
            pass  # Ignore directories we can't access

    @Slot(QTreeWidgetItem, int)
    def _on_file_selected(self, item: QTreeWidgetItem, column: int):
        """Opens a file in a new tab when double-clicked in the tree."""
        abs_path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not abs_path_str: return

        file_path = Path(abs_path_str)
        if file_path.is_file():
            # Check if tab is already open using its absolute path as a key
            if abs_path_str in self.editors:
                for i in range(self.tab_widget.count()):
                    if self.tab_widget.tabToolTip(i) == abs_path_str:
                        self.tab_widget.setCurrentIndex(i)
                        return
                return

            try:
                content = file_path.read_text(encoding='utf-8')
                self._create_editor_tab(abs_path_str)  # Use absolute path as the key
                self.editors[abs_path_str].setPlainText(content)
                self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")

    def _close_tab(self, index):
        """Closes a tab and removes its corresponding editor instance."""
        tooltip = self.tab_widget.tabToolTip(index)
        if tooltip in self.editors:
            del self.editors[tooltip]
        self.tab_widget.removeTab(index)
        if self.tab_widget.count() == 0:
            # Optionally add a welcome message back if all tabs are closed
            pass

    def show_window(self):
        if not self.isVisible():
            self.show()
        else:
            self.activateWindow(); self.raise_()