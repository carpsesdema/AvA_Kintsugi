# kintsugi_ava/gui/editor_tab_manager.py
# Enhanced with professional code editor features: line numbers, find/replace, better editing.

from pathlib import Path
from typing import Dict, Optional
from PySide6.QtWidgets import QTabWidget, QTextEdit, QLabel, QPlainTextEdit, QWidget, QVBoxLayout, QHBoxLayout, QFrame
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QColor, QPainter, QTextFormat, QTextCursor, QKeySequence, QTextCharFormat, QFont

from .components import Colors, Typography
from .code_viewer_helpers import PythonHighlighter


class LineNumberArea(QWidget):
    """Line number area for the enhanced code editor."""

    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)


class EnhancedCodeEditor(QPlainTextEdit):
    """Professional code editor with line numbers, current line highlighting, and better editing."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Setup font and basic properties
        self.setFont(Typography.get_font(11, family="JetBrains Mono"))
        self.setTabStopDistance(40)  # 4 spaces for tab
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        # Line number area
        self.line_number_area = LineNumberArea(self)

        # Colors
        self.current_line_color = QColor(Colors.ELEVATED_BG.red(), Colors.ELEVATED_BG.green(),
                                         Colors.ELEVATED_BG.blue(), 80)
        self.line_number_color = Colors.TEXT_SECONDARY
        self.line_number_bg_color = QColor(Colors.SECONDARY_BG.red(), Colors.SECONDARY_BG.green(),
                                           Colors.SECONDARY_BG.blue(), 200)

        # Setup styling
        self.setup_styling()

        # Connect signals
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        # Initial setup
        self.update_line_number_area_width(0)
        self.highlight_current_line()

    def setup_styling(self):
        """Setup editor styling."""
        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {Colors.PRIMARY_BG.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: none;
                selection-background-color: {Colors.ACCENT_BLUE.name()};
                selection-color: {Colors.TEXT_PRIMARY.name()};
            }}
        """)

    def line_number_area_width(self):
        """Calculate width needed for line numbers."""
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1

        space = 8 + self.fontMetrics().horizontalAdvance('9') * digits
        return max(space, 50)

    def update_line_number_area_width(self, new_block_count):
        """Update line number area width."""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        """Update line number area on scroll."""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        """Handle resize events."""
        super().resizeEvent(event)

        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        """Paint the line numbers."""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), self.line_number_bg_color)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        # Set font and color for line numbers
        painter.setPen(self.line_number_color)
        painter.setFont(self.font())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.drawText(0, top, self.line_number_area.width() - 5, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self):
        """Highlight the current line."""
        extra_selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()

            selection.format.setBackground(self.current_line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

    def keyPressEvent(self, event):
        """Handle key press events with enhanced editing features."""
        # Auto-indentation for Python
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            cursor = self.textCursor()
            current_block = cursor.block()
            current_text = current_block.text()

            # Calculate indentation
            indent = 0
            for char in current_text:
                if char == ' ':
                    indent += 1
                elif char == '\t':
                    indent += 4
                else:
                    break

            # Add extra indent for colons (Python blocks)
            if current_text.rstrip().endswith(':'):
                indent += 4

            super().keyPressEvent(event)

            # Insert indentation
            if indent > 0:
                self.insertPlainText(' ' * indent)

        # Tab handling - insert 4 spaces instead of tab
        elif event.key() == Qt.Key.Key_Tab:
            cursor = self.textCursor()
            if cursor.hasSelection():
                # Indent selection
                self.indent_selection()
            else:
                # Insert spaces
                self.insertPlainText('    ')

        # Shift+Tab - unindent
        elif event.key() == Qt.Key.Key_Backtab:
            self.unindent_selection()

        # Ctrl+/ - toggle comment
        elif event.key() == Qt.Key.Key_Slash and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.toggle_comment()

        # Ctrl+D - duplicate line
        elif event.key() == Qt.Key.Key_D and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.duplicate_line()

        else:
            super().keyPressEvent(event)

    def indent_selection(self):
        """Indent selected lines."""
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)

        while cursor.position() <= end:
            cursor.insertText('    ')
            end += 4
            if not cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                break

    def unindent_selection(self):
        """Unindent selected lines."""
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)

        while cursor.position() <= end:
            block_text = cursor.block().text()
            if block_text.startswith('    '):
                cursor.deleteChar()
                cursor.deleteChar()
                cursor.deleteChar()
                cursor.deleteChar()
                end -= 4
            elif block_text.startswith('\t'):
                cursor.deleteChar()
                end -= 1

            if not cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                break

    def toggle_comment(self):
        """Toggle comment on current line or selection."""
        cursor = self.textCursor()

        if cursor.hasSelection():
            # Comment/uncomment selection
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)

            while cursor.position() <= end:
                block_text = cursor.block().text()
                stripped = block_text.lstrip()

                if stripped.startswith('# '):
                    # Uncomment
                    indent = len(block_text) - len(stripped)
                    cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, indent)
                    cursor.deleteChar()  # #
                    cursor.deleteChar()  # space
                    end -= 2
                elif stripped.startswith('#'):
                    # Uncomment (no space after #)
                    indent = len(block_text) - len(stripped)
                    cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, indent)
                    cursor.deleteChar()  # #
                    end -= 1
                else:
                    # Comment
                    cursor.insertText('# ')
                    end += 2

                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                if not cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                    break
        else:
            # Comment/uncomment current line
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            block_text = cursor.block().text()
            stripped = block_text.lstrip()

            if stripped.startswith('# '):
                # Uncomment
                indent = len(block_text) - len(stripped)
                cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, indent)
                cursor.deleteChar()
                cursor.deleteChar()
            elif stripped.startswith('#'):
                # Uncomment (no space)
                indent = len(block_text) - len(stripped)
                cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, indent)
                cursor.deleteChar()
            else:
                # Comment
                cursor.insertText('# ')

    def duplicate_line(self):
        """Duplicate the current line."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)

        selected_text = cursor.selectedText()
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        cursor.insertText('\n' + selected_text)


class EditorTabManager:
    """
    Manages editor tabs with enhanced code editors.
    Single responsibility: Handle tab creation, content management, and editor operations.
    """

    def __init__(self, tab_widget: QTabWidget):
        self.tab_widget = tab_widget
        self.editors: Dict[str, EnhancedCodeEditor] = {}
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
        Creates a new enhanced editor tab for the given path.

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

        editor = EnhancedCodeEditor()

        # Add syntax highlighting for Python files
        if path_key.endswith('.py'):
            PythonHighlighter(editor.document())

        tab_index = self.tab_widget.addTab(editor, Path(path_key).name)
        self.tab_widget.setTabToolTip(tab_index, path_key)
        self.editors[path_key] = editor

        print(f"[EditorTabManager] Created enhanced editor tab for: {path_key}")
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