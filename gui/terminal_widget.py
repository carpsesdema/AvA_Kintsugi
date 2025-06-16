# kintsugi_ava/gui/terminal_widget.py
# Individual terminal widget with virtual environment awareness

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QLabel, QPushButton, QTabWidget, QFrame, QSplitter
)
from PySide6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor
from PySide6.QtCore import Signal, Qt, QTimer
import qtawesome as qta
from datetime import datetime
from pathlib import Path

from .components import Colors, Typography, ModernButton


class TerminalSession:
    """Represents a single terminal session with its own state."""

    def __init__(self, session_id: int, project_path: str = None):
        self.session_id = session_id
        self.project_path = project_path
        self.command_history = []
        self.history_index = -1
        self.is_busy = False
        self.last_command = ""


class TerminalWidget(QWidget):
    """
    Individual terminal widget with virtual environment awareness,
    command history, and proper shell-like interface.
    """
    command_entered = Signal(str, int)  # command, session_id
    new_terminal_requested = Signal()
    close_terminal_requested = Signal(int)  # session_id

    def __init__(self, event_bus, session_id: int = 0, project_manager=None):
        super().__init__()
        self.event_bus = event_bus
        self.session_id = session_id
        self.project_manager = project_manager
        self.session = TerminalSession(session_id)

        self.setObjectName(f"terminal_widget_{session_id}")
        self.setup_ui()
        self.update_venv_status()

        # Auto-refresh venv status periodically
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_venv_status)
        self.status_timer.start(5000)  # Update every 5 seconds

    def setup_ui(self):
        """Set up the terminal UI with all components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # 1. Header with status and controls
        self.setup_header(main_layout)

        # 2. Output display
        self.setup_output_display(main_layout)

        # 3. Command input
        self.setup_command_input(main_layout)

    def setup_header(self, main_layout):
        """Set up the terminal header with status indicators."""
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.ELEVATED_BG.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                border-radius: 6px;
                padding: 5px;
            }}
        """)

        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(8, 4, 8, 4)

        # Virtual environment status indicator
        self.venv_status_label = QLabel()
        self.venv_status_label.setFont(Typography.get_font(9, family="JetBrains Mono"))
        header_layout.addWidget(self.venv_status_label)

        # Project path display
        self.project_label = QLabel()
        self.project_label.setFont(Typography.get_font(9, family="JetBrains Mono"))
        self.project_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")
        header_layout.addWidget(self.project_label)

        header_layout.addStretch()

        # Terminal controls
        self.new_terminal_btn = QPushButton()
        self.new_terminal_btn.setIcon(qta.icon("fa5s.plus", color=Colors.TEXT_PRIMARY.name()))
        self.new_terminal_btn.setToolTip("New Terminal")
        self.new_terminal_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                padding: 4px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {Colors.SECONDARY_BG.name()};
            }}
        """)
        self.new_terminal_btn.clicked.connect(self.new_terminal_requested.emit)
        header_layout.addWidget(self.new_terminal_btn)

        if self.session_id > 0:  # Don't show close button for the first terminal
            self.close_terminal_btn = QPushButton()
            self.close_terminal_btn.setIcon(qta.icon("fa5s.times", color=Colors.TEXT_PRIMARY.name()))
            self.close_terminal_btn.setToolTip("Close Terminal")
            self.close_terminal_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    padding: 4px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: {Colors.ACCENT_RED.name()};
                }}
            """)
            self.close_terminal_btn.clicked.connect(lambda: self.close_terminal_requested.emit(self.session_id))
            header_layout.addWidget(self.close_terminal_btn)

        main_layout.addWidget(header_frame)

    def setup_output_display(self, main_layout):
        """Set up the terminal output display area."""
        self.output_view = QTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setFont(Typography.get_font(10, family="JetBrains Mono"))
        self.output_view.setStyleSheet(f"""
            QTextEdit {{
                color: {Colors.TEXT_SECONDARY.name()};
                background-color: {Colors.PRIMARY_BG.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                border-radius: 6px;
                padding: 8px;
            }}
        """)

        # Add welcome message
        welcome_msg = f"Terminal Session {self.session_id} - Ready\n"
        if self.project_manager and self.project_manager.active_project_path:
            welcome_msg += f"Project: {self.project_manager.active_project_name}\n"
        welcome_msg += "Type commands below. Python/pip commands will use the project's virtual environment.\n\n"

        self.output_view.setPlainText(welcome_msg)
        main_layout.addWidget(self.output_view, 1)

    def setup_command_input(self, main_layout):
        """Set up the command input area."""
        input_frame = QFrame()
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        # Prompt label
        self.prompt_label = QLabel()
        self.prompt_label.setFont(Typography.get_font(10, family="JetBrains Mono"))
        self.prompt_label.setStyleSheet(f"color: {Colors.ACCENT_BLUE.name()};")
        self.update_prompt()
        input_layout.addWidget(self.prompt_label)

        # Command input
        self.command_input = QLineEdit()
        self.command_input.setFont(Typography.get_font(10, family="JetBrains Mono"))
        self.command_input.setPlaceholderText("Enter command and press Enter")
        self.command_input.setStyleSheet(f"""
            QLineEdit {{
                color: {Colors.TEXT_PRIMARY.name()};
                background-color: {Colors.SECONDARY_BG.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                border-radius: 6px;
                padding: 8px;
            }}
            QLineEdit:focus {{
                border: 1px solid {Colors.ACCENT_BLUE.name()};
            }}
        """)
        self.command_input.returnPressed.connect(self._on_command_entered)
        self.command_input.keyPressEvent = self._handle_key_press
        input_layout.addWidget(self.command_input, 1)

        # Quick action buttons
        self.setup_quick_actions(input_layout)

        main_layout.addWidget(input_frame)

    def setup_quick_actions(self, input_layout):
        """Set up quick action buttons."""
        # Python button
        python_btn = QPushButton("python")
        python_btn.setFont(Typography.get_font(8, family="JetBrains Mono"))
        python_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT_GREEN.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background-color: #40a86a;
            }}
        """)
        python_btn.clicked.connect(lambda: self._insert_command("python "))
        input_layout.addWidget(python_btn)

        # Pip button
        pip_btn = QPushButton("pip")
        pip_btn.setFont(Typography.get_font(8, family="JetBrains Mono"))
        pip_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT_BLUE.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background-color: #4f8cc9;
            }}
        """)
        pip_btn.clicked.connect(lambda: self._insert_command("pip "))
        input_layout.addWidget(pip_btn)

    def update_venv_status(self):
        """Update the virtual environment status indicator."""
        if not self.project_manager:
            self.venv_status_label.setText("❌ No Project Manager")
            self.venv_status_label.setStyleSheet(f"color: {Colors.ACCENT_RED.name()};")
            return

        venv_info = self.project_manager.get_venv_info()

        if venv_info["active"]:
            self.venv_status_label.setText("🐍 venv active")
            self.venv_status_label.setStyleSheet(f"color: {Colors.ACCENT_GREEN.name()};")
        else:
            reason = venv_info.get("reason", "Unknown")
            self.venv_status_label.setText(f"❌ venv: {reason}")
            self.venv_status_label.setStyleSheet(f"color: {Colors.ACCENT_RED.name()};")

        # Update project path
        if self.project_manager.active_project_path:
            project_name = self.project_manager.active_project_name
            self.project_label.setText(f"📁 {project_name}")
            self.session.project_path = str(self.project_manager.active_project_path)
        else:
            self.project_label.setText("📁 No project")
            self.session.project_path = None

        self.update_prompt()

    def update_prompt(self):
        """Update the command prompt display."""
        if self.session.project_path:
            project_name = Path(self.session.project_path).name
            if self.project_manager and self.project_manager.is_venv_active:
                prompt = f"(venv) {project_name}>"
            else:
                prompt = f"{project_name}>"
        else:
            prompt = "terminal>"

        self.prompt_label.setText(prompt)

    def _insert_command(self, command):
        """Insert a command into the input field."""
        self.command_input.setText(command)
        self.command_input.setFocus()

    def _handle_key_press(self, event):
        """Handle key press events for command history navigation."""
        if event.key() == Qt.Key.Key_Up:
            self._navigate_history(-1)
        elif event.key() == Qt.Key.Key_Down:
            self._navigate_history(1)
        else:
            # Call the original keyPressEvent
            QLineEdit.keyPressEvent(self.command_input, event)

    def _navigate_history(self, direction):
        """Navigate through command history."""
        if not self.session.command_history:
            return

        self.session.history_index += direction

        if self.session.history_index < 0:
            self.session.history_index = 0
        elif self.session.history_index >= len(self.session.command_history):
            self.session.history_index = len(self.session.command_history) - 1

        if 0 <= self.session.history_index < len(self.session.command_history):
            command = self.session.command_history[self.session.history_index]
            self.command_input.setText(command)

    def _on_command_entered(self):
        """Handle command submission."""
        command_text = self.command_input.text().strip()
        if not command_text:
            return

        # Add to history
        if command_text not in self.session.command_history:
            self.session.command_history.append(command_text)
        self.session.history_index = len(self.session.command_history)

        # Display the command with prompt
        timestamp = datetime.now().strftime("%H:%M:%S")
        prompt = self.prompt_label.text()
        self.append_output(f"[{timestamp}] {prompt} {command_text}\n")

        # Emit the command
        self.command_entered.emit(command_text, self.session_id)
        self.command_input.clear()
        self.session.last_command = command_text
        self.session.is_busy = True

    def append_output(self, text: str):
        """Append text to the output view."""
        self.output_view.moveCursor(QTextCursor.MoveOperation.End)
        self.output_view.insertPlainText(text)
        self.output_view.ensureCursorVisible()

    def append_colored_output(self, text: str, color: QColor = None):
        """Append colored text to the output view."""
        cursor = self.output_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        if color:
            format = QTextCharFormat()
            format.setForeground(color)
            cursor.insertText(text, format)
        else:
            cursor.insertText(text)

        self.output_view.ensureCursorVisible()

    def append_error_output(self, text: str):
        """Append error text in red color."""
        self.append_colored_output(text, QColor(Colors.ACCENT_RED.name()))

    def append_success_output(self, text: str):
        """Append success text in green color."""
        self.append_colored_output(text, QColor(Colors.ACCENT_GREEN.name()))

    def clear_output(self):
        """Clear the output view."""
        self.output_view.clear()
        # Re-add welcome message
        welcome_msg = f"Terminal Session {self.session_id} - Cleared\n"
        if self.session.project_path:
            welcome_msg += f"Project: {Path(self.session.project_path).name}\n"
        welcome_msg += "\n"
        self.output_view.setPlainText(welcome_msg)

    def mark_command_finished(self):
        """Mark the current command as finished."""
        self.session.is_busy = False

    def get_session_info(self) -> dict:
        """Get information about this terminal session."""
        return {
            "session_id": self.session_id,
            "project_path": self.session.project_path,
            "is_busy": self.session.is_busy,
            "last_command": self.session.last_command,
            "command_count": len(self.session.command_history)
        }