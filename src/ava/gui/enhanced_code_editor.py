# src/ava/gui/enhanced_code_editor.py
from PySide6.QtWidgets import QWidget, QMessageBox, QPlainTextEdit, QTextEdit
from PySide6.QtCore import Qt, QRect, QSize, Signal
from PySide6.QtGui import QColor, QPainter, QTextFormat, QTextCursor, QFont, QKeySequence, QShortcut, QTextCharFormat
from typing import Dict, List, Any

from src.ava.gui.components import Colors, Typography


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
    content_changed = Signal()
    save_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(Typography.get_font(11, family="JetBrains Mono"))
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.line_number_area = LineNumberArea(self)
        self.current_line_color = QColor(Colors.ELEVATED_BG.name()).lighter(110)
        self.error_line_color = Colors.DIFF_ADD_BG
        self.diagnostic_underline_color = Colors.ACCENT_RED
        self.diagnostic_selections: List[QTextEdit.ExtraSelection] = []
        self.line_number_color = Colors.TEXT_SECONDARY
        self.line_number_bg_color = Colors.SECONDARY_BG
        self._is_dirty = False
        self._original_content = ""
        self.setup_styling()
        self.setup_shortcuts()
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.textChanged.connect(self._on_content_changed)
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

    def setup_shortcuts(self):
        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self.save_requested.emit)

    def set_content(self, content: str):
        self.setPlainText(content)
        self._original_content = content
        self._is_dirty = False

    def is_dirty(self) -> bool:
        return self._is_dirty

    def mark_clean(self):
        self._original_content = self.toPlainText()
        self._is_dirty = False
        self.content_changed.emit()

    def _on_content_changed(self):
        current_content = self.toPlainText()
        was_dirty = self._is_dirty
        self._is_dirty = current_content != self._original_content
        if was_dirty != self._is_dirty:
            self.content_changed.emit()

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
        height = self.fontMetrics().height()
        while block.isValid() and (top <= event.rect().bottom()):
            if block.isVisible() and (bottom >= event.rect().top()):
                number = str(block_number + 1)
                painter.setPen(self.line_number_color)
                painter.drawText(0, int(top), self.line_number_area.width() - 5, height,
                                 Qt.AlignmentFlag.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def highlight_current_line(self):
        extra_selections = []
        extra_selections.extend(self.diagnostic_selections)
        extra_selections.extend(
            [sel for sel in self.extraSelections() if sel.format.background() == self.error_line_color])

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

    def set_diagnostics(self, diagnostics: List[Dict[str, Any]]):
        """Applies squiggly underlines for LSP diagnostics."""
        self.diagnostic_selections.clear()
        for diag in diagnostics:
            start_line = diag['range']['start']['line']
            start_col = diag['range']['start']['character']
            end_line = diag['range']['end']['line']
            end_col = diag['range']['end']['character']

            severity = diag.get('severity', 1)
            color = Colors.ACCENT_RED if severity == 1 else Colors.ACCENT_BLUE.lighter(130)

            cursor = self.textCursor()
            block = self.document().findBlockByNumber(start_line)
            if not block.isValid(): continue

            cursor.setPosition(block.position() + start_col)
            end_block = self.document().findBlockByNumber(end_line) if end_line != start_line else block
            cursor.setPosition(end_block.position() + end_col, QTextCursor.MoveMode.KeepAnchor)

            selection = QTextEdit.ExtraSelection()
            selection.format.setUnderlineColor(color)
            selection.format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
            selection.format.setToolTip(diag.get('message', ''))
            selection.cursor = cursor
            self.diagnostic_selections.append(selection)

        self.highlight_current_line()

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
                else:
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