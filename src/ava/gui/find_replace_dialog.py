from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
                               QPushButton, QCheckBox, QLabel, QFrame)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor, QTextDocument

from .components import Colors, Typography, ModernButton


class FindReplaceDialog(QDialog):
    """
    A modern find and replace dialog for the code editor.
    """

    # Signals
    find_requested = Signal(str, bool, bool, bool)  # text, match_case, whole_word, regex
    replace_requested = Signal(str, str, bool, bool, bool)  # find_text, replace_text, match_case, whole_word, regex
    replace_all_requested = Signal(str, str, bool, bool, bool)  # find_text, replace_text, match_case, whole_word, regex

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find and Replace")
        self.setModal(False)
        self.setMinimumWidth(400)  # Give it a little more space

        # Store the editor reference
        self.current_editor = None

        self.setup_ui()
        self.setup_shortcuts()
        self.setup_connections()

    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.PRIMARY_BG.name()};
                color: {Colors.TEXT_PRIMARY.name()};
            }}
            QLineEdit {{
                background-color: {Colors.SECONDARY_BG.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                padding: 8px;
                border-radius: 4px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {Colors.ACCENT_BLUE.name()};
            }}
            QCheckBox {{
                color: {Colors.TEXT_PRIMARY.name()};
                spacing: 8px;
            }}
            QLabel {{
                color: {Colors.TEXT_PRIMARY.name()};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Find section
        find_layout = QHBoxLayout()
        find_label = QLabel("Find:")
        find_label.setMinimumWidth(50)
        find_layout.addWidget(find_label)
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Enter text to find...")
        find_layout.addWidget(self.find_edit)
        layout.addLayout(find_layout)

        # Replace section
        replace_layout = QHBoxLayout()
        replace_label = QLabel("Replace:")
        replace_label.setMinimumWidth(50)
        replace_layout.addWidget(replace_label)
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Enter replacement text...")
        replace_layout.addWidget(self.replace_edit)
        layout.addLayout(replace_layout)

        # Options section
        options_layout = QHBoxLayout()
        self.match_case_cb = QCheckBox("Match case")
        self.whole_word_cb = QCheckBox("Whole word")
        self.regex_cb = QCheckBox("Regex")
        self.regex_cb.setToolTip("Regular Expression search is not yet implemented.")
        self.regex_cb.setEnabled(False)  # Disable until implemented

        options_layout.addStretch()
        options_layout.addWidget(self.match_case_cb)
        options_layout.addWidget(self.whole_word_cb)
        options_layout.addWidget(self.regex_cb)
        layout.addLayout(options_layout)

        # Buttons section
        button_layout = QHBoxLayout()
        self.find_prev_btn = ModernButton("Find Prev")
        self.find_next_btn = ModernButton("Find Next")
        button_layout.addStretch()
        button_layout.addWidget(self.find_prev_btn)
        button_layout.addWidget(self.find_next_btn)

        self.replace_btn = ModernButton("Replace", "primary")
        self.replace_all_btn = ModernButton("Replace All", "primary")
        button_layout.addWidget(self.replace_btn)
        button_layout.addWidget(self.replace_all_btn)

        close_btn = ModernButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        find_next_shortcut = QShortcut(Qt.Key.Key_F3, self)
        find_next_shortcut.activated.connect(self._find_next)

        find_prev_shortcut = QShortcut(QKeySequence("Shift+F3"), self)
        find_prev_shortcut.activated.connect(self._find_previous)

        self.find_edit.returnPressed.connect(self._find_next)

        replace_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.replace_edit)
        replace_shortcut.activated.connect(self._replace)

    def setup_connections(self):
        """Connect button signals."""
        self.find_next_btn.clicked.connect(self._find_next)
        self.find_prev_btn.clicked.connect(self._find_previous)
        self.replace_btn.clicked.connect(self._replace)
        self.replace_all_btn.clicked.connect(self._replace_all)

    def set_editor(self, editor):
        """Set the current editor to search in."""
        self.current_editor = editor

    def set_find_text(self, text: str):
        """Set the find text and select it."""
        self.find_edit.setText(text)
        self.find_edit.selectAll()

    def show_and_focus(self):
        """Show the dialog and focus the find field."""
        self.show()
        self.raise_()
        self.activateWindow()
        self.find_edit.setFocus()

    def _get_search_options(self):
        """Get the current search options."""
        flags = QTextDocument.FindFlag(0)
        if self.match_case_cb.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if self.whole_word_cb.isChecked():
            flags |= QTextDocument.FindFlag.FindWholeWords
        return flags

    def _find_next(self):
        self._find_in_editor(forward=True)

    def _find_previous(self):
        self._find_in_editor(forward=False)

    def _replace(self):
        self._replace_in_editor(replace_all=False)

    def _replace_all(self):
        self._replace_in_editor(replace_all=True)

    def _find_in_editor(self, forward: bool):
        if not self.current_editor:
            return False

        text = self.find_edit.text()
        if not text:
            return False

        flags = self._get_search_options()
        if not forward:
            flags |= QTextDocument.FindFlag.FindBackward

        # Pass editor's cursor to find from current position
        found_cursor = self.current_editor.document().find(text, self.current_editor.textCursor(), flags)

        if not found_cursor.isNull():
            self.current_editor.setTextCursor(found_cursor)
            return True
        else:
            # Wrap around search
            cursor = self.current_editor.textCursor()
            if forward:
                cursor.movePosition(QTextCursor.MoveOperation.Start)
            else:
                cursor.movePosition(QTextCursor.MoveOperation.End)

            found_cursor = self.current_editor.document().find(text, cursor, flags)
            if not found_cursor.isNull():
                self.current_editor.setTextCursor(found_cursor)
                return True

        return False

    def _replace_in_editor(self, replace_all: bool):
        if not self.current_editor:
            return 0

        find_text = self.find_edit.text()
        replace_text = self.replace_edit.text()
        flags = self._get_search_options()
        replaced_count = 0

        # For 'replace all', start from the beginning
        if replace_all:
            cursor = self.current_editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.current_editor.setTextCursor(cursor)

        self.current_editor.document().undo()  # Group changes for undo

        while True:
            cursor = self.current_editor.document().find(find_text, self.current_editor.textCursor(), flags)
            if cursor.isNull():
                break  # No more occurrences

            cursor.insertText(replace_text)
            replaced_count += 1

            if not replace_all:
                break

        self.current_editor.document().endUndoBlock()
        return replaced_count