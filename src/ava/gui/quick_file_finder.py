from pathlib import Path
from typing import List, Callable
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLineEdit, QListWidget,
                               QListWidgetItem, QLabel, QFrame)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QKeySequence, QShortcut

from .components import Colors, Typography


class QuickFileFinder(QDialog):
    """
    A quick file finder dialog similar to VS Code's Ctrl+P functionality.
    """

    file_selected = Signal(str)  # Emitted when a file is selected

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Open")
        self.setModal(True)
        self.setFixedSize(600, 400)

        self.project_root = None
        self.file_paths = []
        self.file_open_callback = None

        # Debounce timer for search
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)

        self.setup_ui()
        self.setup_shortcuts()
        self.setup_connections()

    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.PRIMARY_BG.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
            }}
            QLineEdit {{
                background-color: {Colors.SECONDARY_BG.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                padding: 12px;
                border-radius: 4px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {Colors.ACCENT_BLUE.name()};
            }}
            QListWidget {{
                background-color: {Colors.PRIMARY_BG.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: none;
                outline: none;
                font-size: 13px;
            }}
            QListWidget::item {{
                padding: 8px 12px;
                border-bottom: 1px solid {Colors.BORDER_DEFAULT.name()};
            }}
            QListWidget::item:selected {{
                background-color: {Colors.ACCENT_BLUE.name()};
                color: white;
            }}
            QListWidget::item:hover {{
                background-color: {Colors.ELEVATED_BG.name()};
            }}
            QLabel {{
                color: {Colors.TEXT_SECONDARY.name()};
                font-size: 12px;
                padding: 8px 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Search input
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Type to search files...")
        layout.addWidget(self.search_edit)

        # Results list
        self.results_list = QListWidget()
        layout.addWidget(self.results_list)

        # Status label
        self.status_label = QLabel("No project loaded")
        layout.addWidget(self.status_label)

    def setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        close_shortcut = QShortcut(Qt.Key.Key_Escape, self)
        close_shortcut.activated.connect(self.close)

    def setup_connections(self):
        """Connect signals."""
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.search_edit.returnPressed.connect(self._open_selected_file)
        self.results_list.itemDoubleClicked.connect(self._on_item_double_clicked)

    def set_project_root(self, project_root: Path):
        """Set the project root and scan for files."""
        if self.project_root != project_root:
            self.project_root = project_root
            self._scan_project_files()

    def set_file_open_callback(self, callback: Callable[[str], None]):
        """Set the callback to call when a file is selected."""
        self.file_open_callback = callback

    def show_and_focus(self):
        """Show the dialog and focus the search field."""
        if not self.project_root:
            self.status_label.setText("No project loaded")
            return

        self.show()
        self.raise_()
        self.activateWindow()
        self.search_edit.clear()
        self.search_edit.setFocus()
        self._perform_search()

    def _scan_project_files(self):
        if not self.project_root or not self.project_root.is_dir():
            self.file_paths = []
            return

        self.file_paths = []
        exclude_patterns = {
            '.git', '__pycache__', '.pytest_cache', 'node_modules',
            '.venv', 'venv', '.env', 'dist', 'build', '.idea',
            '.vscode', '*.pyc', '*.pyo', '*.pyd', '.DS_Store', 'rag_db'
        }

        def should_exclude(path: Path) -> bool:
            return any(part in exclude_patterns for part in path.parts)

        try:
            for file_path in self.project_root.rglob('*'):
                if file_path.is_file() and not should_exclude(file_path):
                    relative_path = file_path.relative_to(self.project_root)
                    self.file_paths.append(str(relative_path))
        except Exception as e:
            print(f"[QuickFileFinder] Error scanning project: {e}")

        self.status_label.setText(f"Found {len(self.file_paths)} files")

    def _on_search_text_changed(self, text: str):
        self.search_timer.stop()
        self.search_timer.start(150)

    def _perform_search(self):
        search_text = self.search_edit.text().lower()
        self.results_list.clear()

        if not self.file_paths: return

        matches = []
        if not search_text:
            matches = [(100, fp) for fp in self.file_paths]
        else:
            for file_path in self.file_paths:
                score = self._calculate_match_score(file_path, search_text)
                if score > 0:
                    matches.append((score, file_path))

        matches.sort(key=lambda x: x[0], reverse=True)

        for score, file_path in matches[:50]:
            item = QListWidgetItem(file_path)
            item.setData(Qt.ItemDataRole.UserRole, file_path)
            self.results_list.addItem(item)

        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)

        total_matches = len(matches)
        shown = min(total_matches, 50)
        self.status_label.setText(f"Showing {shown} of {total_matches} files")

    def _calculate_match_score(self, file_path: str, search_text: str) -> int:
        file_lower = file_path.lower()
        filename = Path(file_path).name.lower()
        if search_text in filename: return 800
        if search_text in file_lower: return 600
        if self._fuzzy_match(file_lower, search_text): return 100
        return 0

    def _fuzzy_match(self, text: str, pattern: str) -> bool:
        pattern_idx = 0
        for char in text:
            if pattern_idx < len(pattern) and char == pattern[pattern_idx]:
                pattern_idx += 1
        return pattern_idx == len(pattern)

    def _open_selected_file(self):
        current_item = self.results_list.currentItem()
        if current_item:
            file_path = current_item.data(Qt.ItemDataRole.UserRole)
            if file_path and self.project_root:
                full_path = self.project_root / file_path
                if self.file_open_callback:
                    self.file_open_callback(str(full_path))
                self.file_selected.emit(str(full_path))
                self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Down:
            current_row = self.results_list.currentRow()
            if current_row < self.results_list.count() - 1:
                self.results_list.setCurrentRow(current_row + 1)
        elif event.key() == Qt.Key.Key_Up:
            current_row = self.results_list.currentRow()
            if current_row > 0:
                self.results_list.setCurrentRow(current_row - 1)
        else:
            super().keyPressEvent(event)