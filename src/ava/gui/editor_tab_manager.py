# src/ava/gui/editor_tab_manager.py
from pathlib import Path
from typing import Dict, Optional, List
from PySide6.QtWidgets import QTabWidget, QTextEdit, QLabel, QPlainTextEdit, QWidget, QMessageBox
from PySide6.QtCore import Qt, QRect, QSize, Signal
from PySide6.QtGui import QColor, QPainter, QTextFormat, QTextCursor, QFont, QKeySequence, QShortcut

from src.ava.gui.components import Colors, Typography
from src.ava.gui.code_viewer_helpers import PythonHighlighter, GenericHighlighter
from src.ava.core.event_bus import EventBus
from src.ava.core.project_manager import ProjectManager


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
        extra_selections = [sel for sel in self.extraSelections() if sel.format.background() != self.current_line_color]
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


class EditorTabManager:
    """Manages editor tabs with enhanced code editors and file saving."""

    def __init__(self, tab_widget: QTabWidget, event_bus: EventBus, project_manager: ProjectManager):
        self.tab_widget = tab_widget
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.editors: Dict[str, EnhancedCodeEditor] = {}
        self._setup_initial_state()
        self._connect_events()

    def _connect_events(self):
        self.event_bus.subscribe("file_renamed", self._handle_file_renamed)
        self.event_bus.subscribe("items_deleted", self._handle_items_deleted)
        self.event_bus.subscribe("items_moved", self._handle_items_moved)  # New
        self.event_bus.subscribe("items_added", self._handle_items_added)  # New

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
        if self.has_unsaved_changes():
            reply = QMessageBox.question(self.tab_widget, "Unsaved Changes",
                                         "You have unsaved changes. Save them before creating a new project?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                self.save_all_files()
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        self.clear_all_tabs()
        self._add_welcome_tab("Ready for new project generation...")
        print("[EditorTabManager] State reset for new project session.")

    def clear_all_tabs(self):
        while self.tab_widget.count() > 0:
            widget_to_remove = self.tab_widget.widget(0)
            self.tab_widget.removeTab(0)
            if widget_to_remove in self.editors.values():
                path_key_to_remove = None
                for key, editor_instance in self.editors.items():
                    if editor_instance == widget_to_remove:
                        path_key_to_remove = key
                        break
                if path_key_to_remove:
                    del self.editors[path_key_to_remove]
            if widget_to_remove:  # Ensure widget exists before calling deleteLater
                widget_to_remove.deleteLater()
        self.editors.clear()

    def get_active_file_path(self) -> Optional[str]:
        current_index = self.tab_widget.currentIndex()
        if current_index == -1: return None
        return self.tab_widget.tabToolTip(current_index)

    def create_or_update_tab(self, abs_path_str: str, content: str):
        if abs_path_str not in self.editors:
            self.create_editor_tab(abs_path_str)
        self.set_editor_content(abs_path_str, content)
        self.focus_tab(abs_path_str)

    def create_editor_tab(self, abs_path_str: str) -> bool:
        if abs_path_str in self.editors:
            return False

        if self.tab_widget.count() == 1 and isinstance(self.tab_widget.widget(0), QLabel):
            self.tab_widget.removeTab(0)

        editor = EnhancedCodeEditor()
        if abs_path_str.endswith('.py'):
            PythonHighlighter(editor.document())
        elif abs_path_str.endswith('.gd'):
            GenericHighlighter(editor.document(), 'gdscript')

        editor.save_requested.connect(lambda: self.save_file(abs_path_str))
        editor.content_changed.connect(lambda: self._update_tab_title(abs_path_str))

        tab_index = self.tab_widget.addTab(editor, Path(abs_path_str).name)
        self.tab_widget.setTabToolTip(tab_index, abs_path_str)
        self.editors[abs_path_str] = editor
        print(f"[EditorTabManager] Created enhanced editor tab for: {abs_path_str}")
        return True

    def set_editor_content(self, abs_path_str: str, content: str):
        if abs_path_str in self.editors:
            self.editors[abs_path_str].set_content(content)
            self._update_tab_title(abs_path_str)

    def stream_content_to_editor(self, abs_path_str: str, chunk: str):
        if abs_path_str not in self.editors:
            self.create_editor_tab(abs_path_str)
            self.focus_tab(abs_path_str)

        editor = self.editors[abs_path_str]
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        editor.ensureCursorVisible()

    def focus_tab(self, abs_path_str: str):
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabToolTip(i) == abs_path_str:
                self.tab_widget.setCurrentIndex(i)
                return True
        return False

    def open_file_in_tab(self, file_path: Path):
        if not file_path.is_file(): return
        abs_path_str = str(file_path.resolve())
        if abs_path_str in self.editors:
            self.focus_tab(abs_path_str)
            return

        try:
            content = file_path.read_text(encoding='utf-8')
            self.create_or_update_tab(abs_path_str, content)
        except Exception as e:
            print(f"[EditorTabManager] Error opening file {file_path}: {e}")
            QMessageBox.warning(self.tab_widget, "Open File Error", f"Could not open file:\n{file_path.name}\n\n{e}")

    def close_tab(self, index: int, force_close: bool = False):
        abs_path_str = self.tab_widget.tabToolTip(index)
        widget_to_remove = self.tab_widget.widget(index)  # Get widget before removing tab

        if abs_path_str in self.editors:
            editor = self.editors[abs_path_str]
            if not force_close and editor.is_dirty():
                reply = QMessageBox.question(self.tab_widget, "Unsaved Changes",
                                             f"File '{Path(abs_path_str).name}' has unsaved changes. Save before closing?",
                                             QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
                if reply == QMessageBox.StandardButton.Save:
                    if not self.save_file(abs_path_str):
                        return
                elif reply == QMessageBox.StandardButton.Cancel:
                    return
            del self.editors[abs_path_str]

        self.tab_widget.removeTab(index)
        if widget_to_remove:  # Ensure widget exists before calling deleteLater
            widget_to_remove.deleteLater()

        if self.tab_widget.count() == 0:
            self._add_welcome_tab("All tabs closed. Open a file or generate code.")

    def save_file(self, abs_path_str: str) -> bool:
        if abs_path_str not in self.editors:
            print(f"[EditorTabManager] Cannot save: No editor for {abs_path_str}")
            return False
        editor = self.editors[abs_path_str]
        try:
            file_path = Path(abs_path_str)
            content = editor.toPlainText()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding='utf-8')
            editor.mark_clean()
            self._update_tab_title(abs_path_str)
            print(f"[EditorTabManager] Saved file: {file_path.name}")
            if self.project_manager and self.project_manager.active_project_path and self.project_manager.repo:
                if file_path.is_relative_to(self.project_manager.active_project_path):
                    rel_path = file_path.relative_to(self.project_manager.active_project_path).as_posix()
                    self.project_manager.stage_file(rel_path)
            return True
        except Exception as e:
            print(f"[EditorTabManager] Error saving file {abs_path_str}: {e}")
            self._show_save_error(Path(abs_path_str).name, str(e))
            return False

    def save_current_file(self) -> bool:
        current_path = self.get_active_file_path()
        if current_path:
            return self.save_file(current_path)
        return False

    def save_all_files(self) -> bool:
        all_saved = True
        # Iterate over a copy of keys if modifying the dictionary (not here, but good practice)
        for abs_path_str in list(self.editors.keys()):
            editor = self.editors.get(abs_path_str)  # Use .get for safety
            if editor and editor.is_dirty():
                if not self.save_file(abs_path_str):
                    all_saved = False
        return all_saved

    def has_unsaved_changes(self) -> bool:
        return any(editor.is_dirty() for editor in self.editors.values())

    def get_unsaved_files(self) -> list[str]:
        return [abs_path_str for abs_path_str, editor in self.editors.items() if editor.is_dirty()]

    def _update_tab_title(self, abs_path_str: str):
        if abs_path_str not in self.editors: return
        editor = self.editors[abs_path_str]
        base_name = Path(abs_path_str).name
        title = f"{'*' if editor.is_dirty() else ''}{base_name}"
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabToolTip(i) == abs_path_str:
                self.tab_widget.setTabText(i, title)
                break

    def _show_save_error(self, filename: str, error: str):
        QMessageBox.critical(self.tab_widget, "Save Error", f"Could not save '{filename}'\nError: {error}")

    def highlight_error(self, file_path_str: str, line_number: int):
        try:
            file_to_highlight = Path(file_path_str).resolve()
            if not file_to_highlight.is_file():
                print(f"[EditorTabManager] Error: Cannot highlight non-existent file: {file_to_highlight}")
                return
            abs_path_str = str(file_to_highlight)
            if abs_path_str not in self.editors:
                self.open_file_in_tab(file_to_highlight)
            if abs_path_str in self.editors:
                self.editors[abs_path_str].highlight_error_line(line_number)
                self.focus_tab(abs_path_str)
                print(f"[EditorTabManager] Highlighted error on line {line_number} in {abs_path_str}")
            else:
                print(f"[EditorTabManager] Failed to open or find editor for highlighting: {abs_path_str}")
        except Exception as e:
            print(f"[EditorTabManager] Unexpected error during error highlighting: {e}")

    def clear_all_error_highlights(self):
        for editor in self.editors.values():
            editor.clear_error_highlight()

    # --- Event Handlers for File System Changes ---
    def _handle_file_renamed(self, old_rel_path_str: str, new_rel_path_str: str):
        if not self.project_manager or not self.project_manager.active_project_path:
            return

        old_abs_path_str = str((self.project_manager.active_project_path / old_rel_path_str).resolve())
        new_abs_path_str = str((self.project_manager.active_project_path / new_rel_path_str).resolve())

        if old_abs_path_str in self.editors:
            editor = self.editors.pop(old_abs_path_str)
            self.editors[new_abs_path_str] = editor

            for i in range(self.tab_widget.count()):
                if self.tab_widget.tabToolTip(i) == old_abs_path_str:
                    new_tab_name = Path(new_abs_path_str).name
                    self.tab_widget.setTabText(i, new_tab_name + ("*" if editor.is_dirty() else ""))
                    self.tab_widget.setTabToolTip(i, new_abs_path_str)
                    print(f"[EditorTabManager] Updated tab for renamed file: {old_rel_path_str} -> {new_rel_path_str}")
                    break

    def _handle_items_deleted(self, deleted_rel_paths: List[str]):
        if not self.project_manager or not self.project_manager.active_project_path:
            return

        abs_paths_to_check_for_closing = set()
        for rel_path_str in deleted_rel_paths:
            abs_path = (self.project_manager.active_project_path / rel_path_str).resolve()
            abs_paths_to_check_for_closing.add(str(abs_path))
            # If it's a directory, we need to check all files within it that might be open
            if abs_path.is_dir():  # This check might be tricky if dir is already deleted, rely on path structure
                for open_abs_path_str in list(self.editors.keys()):  # Iterate on copy
                    if Path(open_abs_path_str).is_relative_to(abs_path):
                        abs_paths_to_check_for_closing.add(open_abs_path_str)

        tabs_to_close_indices = []
        for i in range(self.tab_widget.count()):
            tab_tooltip_path = self.tab_widget.tabToolTip(i)
            if tab_tooltip_path in abs_paths_to_check_for_closing:
                tabs_to_close_indices.append(i)

        # Close tabs in reverse order to avoid index shifting issues
        for i in sorted(tabs_to_close_indices, reverse=True):
            rel_path_of_closed_tab = Path(self.tab_widget.tabToolTip(i)).relative_to(
                self.project_manager.active_project_path).as_posix()
            self.close_tab(i, force_close=True)
            print(f"[EditorTabManager] Closed tab for deleted item: {rel_path_of_closed_tab}")

    def _handle_items_moved(self, moved_item_infos: List[Dict[str, str]]):
        """Handles items moved within the project tree."""
        if not self.project_manager or not self.project_manager.active_project_path:
            return

        for move_info in moved_item_infos:
            old_rel_path = move_info.get("old")
            new_rel_path = move_info.get("new")
            if not old_rel_path or not new_rel_path:
                continue

            old_abs_path_str = str((self.project_manager.active_project_path / old_rel_path).resolve())
            new_abs_path_str = str((self.project_manager.active_project_path / new_rel_path).resolve())

            # If the moved item itself was an open tab
            if old_abs_path_str in self.editors:
                editor = self.editors.pop(old_abs_path_str)
                self.editors[new_abs_path_str] = editor
                for i in range(self.tab_widget.count()):
                    if self.tab_widget.tabToolTip(i) == old_abs_path_str:
                        new_tab_name = Path(new_abs_path_str).name
                        self.tab_widget.setTabText(i, new_tab_name + ("*" if editor.is_dirty() else ""))
                        self.tab_widget.setTabToolTip(i, new_abs_path_str)
                        print(f"[EditorTabManager] Updated tab for moved file: {old_rel_path} -> {new_rel_path}")
                        break
            else:
                # Check if any open files were *inside* a moved directory
                # This requires iterating through open tabs and checking if their old path
                # was relative to the old_abs_path_str (if it was a directory).
                # Then, construct their new absolute path based on new_abs_path_str.
                for open_abs_path_str in list(self.editors.keys()):  # Iterate on copy
                    open_path_obj = Path(open_abs_path_str)
                    old_dir_abs_path_obj = Path(old_abs_path_str)

                    if old_dir_abs_path_obj.is_dir() and open_path_obj.is_relative_to(old_dir_abs_path_obj):
                        # This open file was inside the moved directory
                        relative_to_moved_dir = open_path_obj.relative_to(old_dir_abs_path_obj)
                        new_file_abs_path_str = str((Path(new_abs_path_str) / relative_to_moved_dir).resolve())

                        editor = self.editors.pop(open_abs_path_str)
                        self.editors[new_file_abs_path_str] = editor
                        for i in range(self.tab_widget.count()):
                            if self.tab_widget.tabToolTip(i) == open_abs_path_str:
                                new_tab_name = Path(new_file_abs_path_str).name
                                self.tab_widget.setTabText(i, new_tab_name + ("*" if editor.is_dirty() else ""))
                                self.tab_widget.setTabToolTip(i, new_file_abs_path_str)
                                print(
                                    f"[EditorTabManager] Updated tab for file within moved directory: {open_abs_path_str} -> {new_file_abs_path_str}")
                                break

    def _handle_items_added(self, added_item_infos: List[Dict[str, str]]):
        """Handles items added to the project (e.g., by external drop)."""
        if not self.project_manager or not self.project_manager.active_project_path:
            return

        for add_info in added_item_infos:
            new_rel_path = add_info.get("new_project_rel_path")
            if new_rel_path:
                new_abs_path = (self.project_manager.active_project_path / new_rel_path).resolve()
                print(f"[EditorTabManager] File added to project: {new_rel_path}. Absolute: {new_abs_path}")
                # Optionally, automatically open newly added files:
                # if new_abs_path.is_file():
                #    self.open_file_in_tab(new_abs_path)