# src/ava/gui/terminal_widget.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QLabel, QMenu
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QKeyEvent, QAction
from PySide6.QtCore import Signal, Qt

from src.ava.gui.components import Colors, Typography
from src.ava.core.project_manager import ProjectManager
from src.ava.core.event_bus import EventBus


class TerminalWidget(QWidget):
    """A widget for a single terminal session, designed to be used in a QTabWidget."""
    command_entered = Signal(str, int)  # command, session_id

    def __init__(self, session_id: int, project_manager: ProjectManager, event_bus: EventBus):
        super().__init__()
        self.session_id = session_id
        self.project_manager = project_manager
        self.event_bus = event_bus
        self.is_busy = False
        self.command_history = []
        self.history_index = -1

        self.setup_ui()
        self.update_prompt()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 10, 5, 5)
        layout.setSpacing(5)

        self.output_view = QTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setFont(Typography.get_font(10, family="JetBrains Mono"))
        self.output_view.setStyleSheet(f"background-color: transparent; border: none; padding: 5px;")
        welcome_msg = f"Terminal Session {self.session_id + 1} Ready.\n"
        if self.project_manager and self.project_manager.active_project_path:
            welcome_msg += f"Project: {self.project_manager.active_project_name}\n"
        self.output_view.setPlainText(welcome_msg)
        # Enable context menu
        self.output_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.output_view.customContextMenuRequested.connect(self.show_context_menu)


        input_layout = QHBoxLayout()
        self.prompt_label = QLabel(">")
        self.prompt_label.setFont(Typography.get_font(10, family="JetBrains Mono"))
        self.prompt_label.setStyleSheet(f"color: {Colors.ACCENT_GREEN.name()};")

        self.command_input = QLineEdit()
        self.command_input.setFont(Typography.get_font(10, family="JetBrains Mono"))
        self.command_input.setPlaceholderText("Enter command...")
        self.command_input.setStyleSheet("border: none; background-color: transparent;")
        self.command_input.returnPressed.connect(self._on_command_entered)
        self.command_input.keyPressEvent = self._handle_key_press

        input_layout.addWidget(self.prompt_label)
        input_layout.addWidget(self.command_input, 1)

        layout.addWidget(self.output_view, 1)
        layout.addLayout(input_layout)

    def show_context_menu(self, pos):
        """Shows a custom context menu."""
        menu = QMenu(self)

        # Action to fix selection, only shown if text is selected
        if self.output_view.textCursor().hasSelection():
            fix_action = QAction("Ask AI to Fix This Error", self)
            fix_action.triggered.connect(self._request_fix_for_highlighted_error)
            menu.addAction(fix_action)
            menu.addSeparator()

        # Standard actions
        copy_action = menu.addAction("Copy")
        copy_action.triggered.connect(self.output_view.copy)
        menu.addSeparator()
        clear_action = menu.addAction("Clear Terminal")
        clear_action.triggered.connect(self.clear_output)

        menu.exec(self.output_view.viewport().mapToGlobal(pos))

    def _request_fix_for_highlighted_error(self):
        """Emits an event with the selected text to be fixed by the WorkflowManager."""
        selected_text = self.output_view.textCursor().selectedText().strip()
        if selected_text:
            self.event_bus.emit("fix_highlighted_error_requested", selected_text)

    def _on_command_entered(self):
        if self.is_busy:
            self.append_error_output("Terminal is busy with another command.\n")
            return

        command_text = self.command_input.text().strip()
        if command_text:
            if command_text not in self.command_history:
                self.command_history.append(command_text)
            self.history_index = len(self.command_history)

            self.is_busy = True
            self.append_output(f"{self.prompt_label.text()} {command_text}\n")
            self.command_entered.emit(command_text, self.session_id)
            self.command_input.clear()

    def _handle_key_press(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Up:
            self._navigate_history(-1)
        elif event.key() == Qt.Key.Key_Down:
            self._navigate_history(1)
        else:
            QLineEdit.keyPressEvent(self.command_input, event)

    def _navigate_history(self, direction: int):
        if not self.command_history:
            return

        self.history_index += direction
        if self.history_index < 0:
            self.history_index = 0
        elif self.history_index >= len(self.command_history):
            self.history_index = len(self.command_history) - 1

        if self.command_history:
            self.command_input.setText(self.command_history[self.history_index])


    def append_output(self, text: str):
        self.output_view.moveCursor(QTextCursor.MoveOperation.End)
        self.output_view.insertPlainText(text)
        self.output_view.ensureCursorVisible()

    def append_error_output(self, text: str):
        self.append_colored_output(text, Colors.ACCENT_RED)

    def append_success_output(self, text: str):
        self.append_colored_output(text, Colors.ACCENT_GREEN)

    def append_colored_output(self, text: str, color: QColor):
        cursor = self.output_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        char_format = QTextCharFormat()
        char_format.setForeground(color)
        cursor.insertText(text, char_format)
        self.output_view.ensureCursorVisible()

    def mark_command_finished(self):
        self.is_busy = False

    def set_project_manager(self, project_manager: ProjectManager):
        self.project_manager = project_manager
        self.update_prompt()

    def update_prompt(self):
        if self.project_manager and self.project_manager.active_project_path:
            project_name = self.project_manager.active_project_name
            venv_active = self.project_manager.get_venv_info().get("active", False)
            prompt = f"({project_name}) >" if not venv_active else f"(venv) ({project_name}) >"
        else:
            prompt = "kintsugi-ava>"

        self.prompt_label.setText(prompt)

    def clear_output(self):
        self.output_view.clear()