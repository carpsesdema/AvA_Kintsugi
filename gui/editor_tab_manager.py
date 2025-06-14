# kintsugi_ava/gui/editor_tab_manager.py
# V4: Final polish. Error highlighting now automatically opens the file if it's not already in a tab.

from pathlib import Path
from typing import Dict, Optional
from PySide6.QtWidgets import QTabWidget, QTextEdit, QLabel, QPlainTextEdit, QWidget
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QColor, QPainter, QTextFormat, QTextCursor, QFont

from .components import Colors, Typography
from .code_viewer_helpers import PythonHighlighter


class LineNumberArea(QWidget):
    """Widget for showing line numbers next to the code editor."""

    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)


class EnhancedCodeEditor(QPlainTextEdit):
    """
    A professional code editor with line numbers, current line highlighting,
    error highlighting, and enhanced editing keyboard shortcuts.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Use a proper programming font
        self.setFont(Typography.get_font(11, family="JetBrains Mono"))
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.line_number_area = LineNumberArea(self)

        # Colors
        self.current_line_color = QColor(Colors.ELEVATED_BG.name()).lighter(110)
        self.error_line_color = Colors.DIFF_ADD_BG
        self.line_number_color = Colors.TEXT_SECONDARY
        self.line_number_bg_color = Colors.SECONDARY_BG

        self.setup_styling()

        # Connect signals for line numbers and highlighting
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)
        self.highlight_current_line()

    def setup_styling(self):
        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {Colors.PRIMARY_BG.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: none;
                padding-left: 5px;
                selection-background-color: {Colors.ACCENT_BLUE.name()};
            }}
        """)

    def line_number_area_width(self):
        digits = 1
        count = max(1, self.blockCount())
        while count >= 10:
            count //= 10
            digits += 1
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), self.line_number_bg_color)
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(self.line_number_color)
                painter.drawText(0, int(top), self.line_number_area.width() - 5, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def highlight_current_line(self):
        extra_selections = self.extraSelections()
        extra_selections = [sel for sel in extra_selections if sel.format.background() != self.current_line_color]

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(self.current_line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

    def highlight_error_line(self, line_number: int):
        extra_selections = self.extraSelections()
        extra_selections = [sel for sel in extra_selections if sel.format.background() != self.error_line_color]

        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(self.error_line_color)
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)

        block = self.document().findBlockByNumber(line_number - 1)
        cursor = QTextCursor(block)
        selection.cursor = cursor
        extra_selections.append(selection)

        self.setExtraSelections(extra_selections)
        self.setTextCursor(cursor)

    def clear_error_highlight(self):
        extra_selections = self.extraSelections()
        extra_selections = [sel for sel in extra_selections if sel.format.background() != self.error_line_color]
        self.setExtraSelections(extra_selections)

    def keyPressEvent(self, event):
        cursor = self.textCursor()

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            current_block = cursor.block()
            current_text = current_block.text()
            indent_level = len(current_text) - len(current_text.lstrip(' '))

            super().keyPressEvent(event)

            new_indent = ' ' * indent_level
            if current_text.strip().endswith(':'):
                new_indent += ' ' * 4

            self.insertPlainText(new_indent)

        elif event.key() == Qt.Key.Key_Tab:
            self.handle_indent(cursor, "indent")
        elif event.key() == Qt.Key.Key_Backtab:
            self.handle_indent(cursor, "unindent")

        elif event.key() == Qt.Key.Key_D and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.duplicate_line(cursor)

        elif event.key() == Qt.Key.Key_Slash and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.toggle_comment(cursor)

        else:
            super().keyPressEvent(event)

    def handle_indent(self, cursor, direction="indent"):
        if cursor.hasSelection():
            start, end = cursor.selectionStart(), cursor.selectionEnd()
            cursor.setPosition(start, QTextCursor.MoveMode.MoveAnchor)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.MoveAnchor)

            cursor.beginEditBlock()
            while True:
                if direction == "indent":
                    cursor.insertText(' ' * 4)
                else:  # unindent
                    if cursor.block().text().startswith(' ' * 4):
                        for _ in range(4): cursor.deleteChar()
                    elif cursor.block().text().startswith('\t'):
                        cursor.deleteChar()
                if cursor.block().position() >= end or not cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                    break
            cursor.endEditBlock()
        else:
            if direction == "indent":
                cursor.insertText(' ' * 4)

    def duplicate_line(self, cursor):
        cursor.beginEditBlock()
        start_pos = cursor.position()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        line_text = cursor.selectedText()
        cursor.clearSelection()
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        cursor.insertText('\n' + line_text)
        cursor.setPosition(start_pos + len(line_text) + 1)
        cursor.endEditBlock()

    def toggle_comment(self, cursor):
        cursor.beginEditBlock()
        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()

        cursor.setPosition(start_pos, QTextCursor.MoveMode.MoveAnchor)
        start_block = cursor.blockNumber()
        cursor.setPosition(end_pos, QTextCursor.MoveMode.MoveAnchor)
        end_block = cursor.blockNumber()

        for block_num in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(block_num)
            cursor.setPosition(block.position(), QTextCursor.MoveMode.MoveAnchor)
            line_text = block.text()
            stripped_text = line_text.lstrip()

            if stripped_text.startswith('# '):
                cursor.movePosition(QTextCursor.MoveMode.Right, count=line_text.find('# '))
                cursor.deleteChar()
                cursor.deleteChar()
            elif stripped_text.startswith('#'):
                cursor.movePosition(QTextCursor.MoveMode.Right, count=line_text.find('#'))
                cursor.deleteChar()
            else:
                cursor.insertText('# ')
        cursor.endEditBlock()


class EditorTabManager:
    """Manages editor tabs with enhanced code editors."""

    def __init__(self, tab_widget: QTabWidget):
        self.tab_widget = tab_widget
        self.editors: Dict[str, EnhancedCodeEditor] = {}
        self._setup_initial_state()

    def _setup_initial_state(self):
        self.clear_all_tabs()
        self._add_welcome_tab("Code will appear here when generated.")

    def _add_welcome_tab(self, message: str):
        welcome_label = QLabel(message)
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setFont(Typography.get_font(18))
        welcome_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")
        self.tab_widget.addTab(welcome_label, "Welcome")

    def prepare_for_new_project(self):
        self.clear_all_tabs()
        self._add_welcome_tab("Ready for new project generation...")
        print("[EditorTabManager] State reset for new project session.")

    def clear_all_tabs(self):
        while self.tab_widget.count() > 0:
            self.tab_widget.removeTab(0)
        self.editors.clear()

    def get_active_file_path(self) -> Optional[str]:
        current_index = self.tab_widget.currentIndex()
        if current_index == -1: return None
        return self.tab_widget.tabToolTip(current_index)

    def create_or_update_tab(self, path_key: str, content: str):
        """Creates a tab if it doesn't exist, or updates it if it does."""
        if path_key not in self.editors:
            self.create_editor_tab(path_key)
        self.set_editor_content(path_key, content)
        self.focus_tab(path_key)

    def create_editor_tab(self, path_key: str) -> bool:
        if path_key in self.editors:
            return False

        if self.tab_widget.count() == 1 and isinstance(self.tab_widget.widget(0), QLabel):
            self.tab_widget.removeTab(0)

        editor = EnhancedCodeEditor()
        if path_key.endswith('.py'):
            PythonHighlighter(editor.document())

        tab_index = self.tab_widget.addTab(editor, Path(path_key).name)
        self.tab_widget.setTabToolTip(tab_index, path_key)
        self.editors[path_key] = editor
        print(f"[EditorTabManager] Created enhanced editor tab for: {path_key}")
        return True

    def set_editor_content(self, path_key: str, content: str):
        if path_key in self.editors:
            self.editors[path_key].setPlainText(content)

    def stream_content_to_editor(self, path_key: str, chunk: str):
        if path_key not in self.editors:
            self.create_editor_tab(path_key)
            self.focus_tab(path_key)

        editor = self.editors[path_key]
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        editor.ensureCursorVisible()

    def focus_tab(self, path_key: str):
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabToolTip(i) == path_key:
                self.tab_widget.setCurrentIndex(i)
                return True
        return False

    def open_file_in_tab(self, file_path: Path):
        if not file_path.is_file(): return
        path_key = str(file_path.resolve())
        if path_key in self.editors:
            self.focus_tab(path_key)
            return

        try:
            content = file_path.read_text(encoding='utf-8')
            self.create_or_update_tab(path_key, content)
        except Exception as e:
            print(f"[EditorTabManager] Error opening file {file_path}: {e}")

    def close_tab(self, index: int):
        tooltip = self.tab_widget.tabToolTip(index)
        if tooltip in self.editors:
            del self.editors[tooltip]
        self.tab_widget.removeTab(index)
        if self.tab_widget.count() == 0:
            self._add_welcome_tab("All tabs closed. Open a file or generate code.")

    def highlight_error(self, file_path_str: str, line_number: int):
        """
        Highlights an error in the specified file, opening it if necessary.
        """
        try:
            file_to_highlight = Path(file_path_str).resolve()
            if not file_to_highlight.is_file():
                print(f"[EditorTabManager] Error: Cannot highlight non-existent file: {file_to_highlight}")
                return

            path_key = str(file_to_highlight)

            # If the tab isn't open, open it now.
            if path_key not in self.editors:
                print(f"[EditorTabManager] File '{file_to_highlight.name}' not open. Opening for error highlighting.")
                self.open_file_in_tab(file_to_highlight)

            # Now that the tab is guaranteed to be open, apply the highlight.
            if path_key in self.editors:
                self.editors[path_key].highlight_error_line(line_number)
                self.focus_tab(path_key)
                print(f"[EditorTabManager] Highlighted error on line {line_number} in {path_key}")
            else:
                print(f"[EditorTabManager] Failed to open or find editor for highlighting: {path_key}")

        except Exception as e:
            print(f"[EditorTabManager] Unexpected error during error highlighting: {e}")

    def clear_all_error_highlights(self):
        """Clears error highlights from all open editor tabs."""
        for editor in self.editors.values():
            editor.clear_error_highlight()