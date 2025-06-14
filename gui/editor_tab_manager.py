# kintsugi_ava/gui/editor_tab_manager.py
# Manages editor tabs and their content for the Code Viewer.

from pathlib import Path
from typing import Dict, Optional
from PySide6.QtWidgets import QTabWidget, QTextEdit, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor

from .components import Colors, Typography
from .code_viewer_helpers import PythonHighlighter


class EditorTabManager:
    """
    Manages editor tabs and their content.
    Single responsibility: Handle tab creation, content management, and editor operations.
    """

    def __init__(self, tab_widget: QTabWidget):
        self.tab_widget = tab_widget
        self.editors: Dict[str, QTextEdit] = {}
        self._setup_initial_state()

    def _setup_initial_state(self):
        """Sets up the initial welcome tab."""
        self.clear_all_tabs()
        self._add_welcome_tab("Code will appear here when generated.")

    def _add_welcome_tab(self, message: str):
        """Adds a welcome/placeholder tab."""
        welcome_label = QLabel(message)
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setFont(Typography.get_font(18))
        welcome_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")
        self.tab_widget.addTab(welcome_label, "Welcome")

    def prepare_for_new_project(self):
        """Prepares the tab manager for a new project generation."""
        self.clear_all_tabs()
        self._add_welcome_tab("Ready for new project generation...")
        print("[EditorTabManager] State reset for new project session.")

    def clear_all_tabs(self):
        """Removes all tabs and clears the editor registry."""
        while self.tab_widget.count() > 0:
            self.tab_widget.removeTab(0)
        self.editors.clear()

    def get_active_file_path(self) -> Optional[str]:
        """Returns the path key of the currently visible editor tab."""
        current_index = self.tab_widget.currentIndex()
        if current_index == -1:
            return None
        return self.tab_widget.tabToolTip(current_index)

    def create_editor_tab(self, path_key: str) -> bool:
        """
        Creates a new editor tab for the given path.

        Args:
            path_key: Unique identifier/path for the editor

        Returns:
            True if tab was created successfully, False if it already exists
        """
        if path_key in self.editors:
            return False

        # Remove welcome tab if it's the only tab
        if self.tab_widget.count() == 1 and self.tab_widget.tabText(0) == "Welcome":
            self.tab_widget.removeTab(0)

        editor = QTextEdit()
        editor.setFont(Typography.get_font(11, family="JetBrains Mono"))

        # Add syntax highlighting for Python files
        if path_key.endswith('.py'):
            PythonHighlighter(editor.document())

        tab_index = self.tab_widget.addTab(editor, Path(path_key).name)
        self.tab_widget.setTabToolTip(tab_index, path_key)
        self.editors[path_key] = editor

        print(f"[EditorTabManager] Created tab for: {path_key}")
        return True

    def set_editor_content(self, path_key: str, content: str) -> bool:
        """
        Sets the complete content of an editor.

        Args:
            path_key: Path identifier for the editor
            content: Complete file content to set

        Returns:
            True if content was set successfully, False otherwise
        """
        if path_key not in self.editors:
            return False

        try:
            self.editors[path_key].setPlainText(content)
            print(f"[EditorTabManager] Set content for: {path_key}")
            return True
        except Exception as e:
            print(f"[EditorTabManager] Error setting content for {path_key}: {e}")
            return False

    def stream_content_to_editor(self, path_key: str, chunk: str) -> bool:
        """
        Streams a chunk of content to an editor (for live generation).

        Args:
            path_key: Path identifier for the editor
            chunk: Content chunk to append

        Returns:
            True if chunk was appended successfully, False otherwise
        """
        # Create tab if it doesn't exist
        if path_key not in self.editors:
            if not self.create_editor_tab(path_key):
                return False
            # Focus the newly created tab
            self.focus_tab(path_key)

        try:
            editor = self.editors[path_key]
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(chunk)
            editor.ensureCursorVisible()
            return True
        except Exception as e:
            print(f"[EditorTabManager] Error streaming to {path_key}: {e}")
            return False

    def focus_tab(self, path_key: str) -> bool:
        """
        Focuses (switches to) the tab with the given path key.

        Args:
            path_key: Path identifier for the tab to focus

        Returns:
            True if tab was focused successfully, False if not found
        """
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabToolTip(i) == path_key:
                self.tab_widget.setCurrentIndex(i)
                return True
        return False

    def open_file_in_tab(self, file_path: Path) -> bool:
        """
        Opens a file from disk in a new tab.

        Args:
            file_path: Path to the file to open

        Returns:
            True if file was opened successfully, False otherwise
        """
        if not file_path.is_file():
            return False

        path_key = str(file_path)

        # If already open, just focus it
        if path_key in self.editors:
            return self.focus_tab(path_key)

        try:
            content = file_path.read_text(encoding='utf-8')
            if self.create_editor_tab(path_key):
                self.set_editor_content(path_key, content)
                self.focus_tab(path_key)
                print(f"[EditorTabManager] Opened file: {file_path}")
                return True
        except Exception as e:
            print(f"[EditorTabManager] Error opening file {file_path}: {e}")

        return False

    def close_tab(self, index: int) -> bool:
        """
        Closes the tab at the given index.

        Args:
            index: Index of the tab to close

        Returns:
            True if tab was closed successfully, False otherwise
        """
        try:
            tooltip = self.tab_widget.tabToolTip(index)
            if tooltip in self.editors:
                del self.editors[tooltip]
            self.tab_widget.removeTab(index)

            # Add welcome tab if no tabs remain
            if self.tab_widget.count() == 0:
                self._add_welcome_tab("All tabs closed. Open a file or generate new code.")

            return True
        except Exception as e:
            print(f"[EditorTabManager] Error closing tab at index {index}: {e}")
            return False

    def has_open_editors(self) -> bool:
        """Returns True if there are any open editor tabs."""
        return len(self.editors) > 0

    def get_editor_content(self, path_key: str) -> Optional[str]:
        """
        Gets the current content of an editor.

        Args:
            path_key: Path identifier for the editor

        Returns:
            Current editor content or None if editor doesn't exist
        """
        if path_key not in self.editors:
            return None
        try:
            return self.editors[path_key].toPlainText()
        except Exception as e:
            print(f"[EditorTabManager] Error getting content for {path_key}: {e}")
            return None