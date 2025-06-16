# kintsugi_ava/gui/integrated_terminal.py
# V4: Upgraded to be a fully functional, venv-aware terminal widget.

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QFrame, QLabel
from PySide6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor
from PySide6.QtCore import Signal, Qt, QTimer
import qtawesome as qta
from pathlib import Path

from .components import Colors, Typography, ModernButton
from core.project_manager import ProjectManager


class IntegratedTerminal(QWidget):
    """
    An integrated, venv-aware terminal inside the Code Viewer.
    """
    # The session_id will always be 0 for this integrated terminal
    command_entered = Signal(str, int)

    def __init__(self, event_bus, project_manager: ProjectManager):
        super().__init__()
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.session_id = 0  # Fixed session ID for the integrated terminal
        self.is_busy = False

        self.setObjectName("integrated_terminal")
        self.setup_ui()
        self._connect_events()
        self.update_project_display()

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_project_display)
        self.status_timer.start(5000)  # Refresh every 5 seconds

    def setup_ui(self):
        self.setStyleSheet(f"""
            #integrated_terminal {{
                background-color: {Colors.PRIMARY_BG.name()};
                border-top: 1px solid {Colors.BORDER_DEFAULT.name()};
            }}
        """)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 10)
        main_layout.setSpacing(5)

        # Header
        header_layout = self._create_header()
        main_layout.addLayout(header_layout)

        # Output Display
        self.output_view = QTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setFont(Typography.get_font(10, family="JetBrains Mono"))
        self.output_view.setStyleSheet(f"background-color: transparent; border: none; padding: 5px;")
        self.output_view.setPlaceholderText("Command output will appear here...")
        main_layout.addWidget(self.output_view, 1)

        # Command Input
        input_layout = self._create_input_area()
        main_layout.addLayout(input_layout)

    def _create_header(self) -> QHBoxLayout:
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 5)
        self.project_status_label = QLabel("No project active")
        self.project_status_label.setFont(Typography.body())
        self.project_status_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")

        self.fix_button = ModernButton("Review & Fix", "primary")
        self.fix_button.setIcon(qta.icon("fa5s.magic", color=Colors.TEXT_PRIMARY.name()))
        self.fix_button.clicked.connect(lambda: self.event_bus.emit("review_and_fix_requested"))
        self.fix_button.hide()

        header_layout.addWidget(self.project_status_label)
        header_layout.addStretch()
        header_layout.addWidget(self.fix_button)
        return header_layout

    def _create_input_area(self) -> QHBoxLayout:
        input_layout = QHBoxLayout()
        self.prompt_label = QLabel(">")
        self.prompt_label.setFont(Typography.get_font(10, family="JetBrains Mono"))
        self.prompt_label.setStyleSheet(f"color: {Colors.ACCENT_GREEN.name()};")

        self.command_input = QLineEdit()
        self.command_input.setFont(Typography.get_font(10, family="JetBrains Mono"))
        self.command_input.setPlaceholderText("Enter command...")
        self.command_input.setStyleSheet(f"border: none; background-color: transparent; padding: 5px;")
        self.command_input.returnPressed.connect(self._on_command_entered)

        run_main_btn = ModernButton("Run main.py", "primary")
        run_main_btn.clicked.connect(lambda: self.command_entered.emit("run_main", self.session_id))

        input_layout.addWidget(self.prompt_label)
        input_layout.addWidget(self.command_input, 1)
        input_layout.addWidget(run_main_btn)
        return input_layout

    def _connect_events(self):
        # Listen for output destined for this terminal
        self.event_bus.subscribe("terminal_output_received", self.handle_terminal_output)
        self.event_bus.subscribe("terminal_error_received", self.handle_terminal_error)
        self.event_bus.subscribe("terminal_success_received", self.handle_terminal_success)
        self.event_bus.subscribe("terminal_command_finished", self.handle_command_finished)

    def set_project_manager(self, project_manager: ProjectManager):
        self.project_manager = project_manager
        self.update_project_display()

    def update_project_display(self):
        if not self.project_manager or not self.project_manager.active_project_path:
            self.project_status_label.setText("No project loaded")
            self.prompt_label.setText(">")
            return

        project_name = self.project_manager.active_project_name
        venv_info = self.project_manager.get_venv_info()

        if venv_info["active"]:
            self.project_status_label.setText(f"Project: {project_name} (venv active)")
            self.project_status_label.setStyleSheet(f"color: {Colors.ACCENT_GREEN.name()};")
            self.prompt_label.setText(f"({project_name}) >")
        else:
            reason = venv_info.get("reason", "inactive")
            self.project_status_label.setText(f"Project: {project_name} (venv: {reason})")
            self.project_status_label.setStyleSheet(f"color: {Colors.ACCENT_RED.name()};")
            self.prompt_label.setText(f"({project_name}) >")

    def _on_command_entered(self):
        if self.is_busy:
            self.append_error_output("Terminal is busy with another command.\n")
            return
        command_text = self.command_input.text().strip()
        if command_text:
            self.is_busy = True
            self.append_output(f"{self.prompt_label.text()} {command_text}\n")
            self.command_entered.emit(command_text, self.session_id)
            self.command_input.clear()

    def handle_terminal_output(self, text: str, session_id: int):
        if session_id == self.session_id:
            self.append_output(text)

    def handle_terminal_error(self, text: str, session_id: int):
        if session_id == self.session_id:
            self.append_error_output(text)

    def handle_terminal_success(self, text: str, session_id: int):
        if session_id == self.session_id:
            self.append_success_output(text)

    def handle_command_finished(self, session_id: int):
        if session_id == self.session_id:
            self.is_busy = False

    def append_output(self, text: str):
        self.output_view.moveCursor(QTextCursor.MoveOperation.End)
        self.output_view.insertPlainText(text)
        self.output_view.ensureCursorVisible()

    def append_colored_output(self, text: str, color: QColor):
        cursor = self.output_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        char_format = QTextCharFormat()
        char_format.setForeground(color)
        cursor.insertText(text, char_format)
        cursor.insertText("\n")
        self.output_view.ensureCursorVisible()

    def append_error_output(self, text: str):
        self.append_colored_output(text, Colors.ACCENT_RED)

    def append_success_output(self, text: str):
        self.append_colored_output(text, Colors.ACCENT_GREEN)

    def clear_output(self):
        self.output_view.clear()

    def show_fix_button(self):
        self.fix_button.setText("Review & Fix")
        self.fix_button.setEnabled(True)
        self.fix_button.show()

    def hide_fix_button(self):
        self.fix_button.hide()

    def show_fixing_in_progress(self):
        self.fix_button.setText("AI is Reviewing...")
        self.fix_button.setEnabled(False)