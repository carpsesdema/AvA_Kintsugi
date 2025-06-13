# kintsugi_ava/gui/integrated_terminal.py
# The command center widget for the Code Viewer.

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QFrame
)
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtCore import Signal, Qt

from .components import Colors, Typography, ModernButton


class IntegratedTerminal(QWidget):
    """
    A widget that provides an integrated terminal experience, including
    an output view, command input, and action buttons.
    """
    # Signal emitted when a user enters a command
    command_entered = Signal(str)

    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        self.setObjectName("integrated_terminal")
        self.setStyleSheet(f"""
            #integrated_terminal {{
                background-color: {Colors.PRIMARY_BG.name()};
                border-top: 1px solid {Colors.BORDER_DEFAULT.name()};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 1. Action Buttons
        button_layout = QHBoxLayout()
        run_main_btn = ModernButton("Run main.py", "primary")
        run_main_btn.clicked.connect(lambda: self.command_entered.emit("run_main"))

        install_reqs_btn = ModernButton("Install Requirements", "secondary")
        install_reqs_btn.clicked.connect(lambda: self.command_entered.emit("install_reqs"))

        button_layout.addWidget(run_main_btn)
        button_layout.addWidget(install_reqs_btn)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        # 2. Output Display
        self.output_view = QTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setFont(Typography.get_font(10, family="JetBrains Mono"))
        self.output_view.setStyleSheet(f"""
            QTextEdit {{
                color: {Colors.TEXT_SECONDARY.name()};
                background-color: {Colors.SECONDARY_BG.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                border-radius: 4px;
                padding: 5px;
            }}
        """)
        self.output_view.setPlaceholderText("Command output will appear here...")
        main_layout.addWidget(self.output_view, 1)  # Make it stretch

        # 3. Command Input
        self.command_input = QLineEdit()
        self.command_input.setFont(Typography.get_font(10, family="JetBrains Mono"))
        self.command_input.setPlaceholderText("Enter command (e.g., 'pip list') and press Enter")
        self.command_input.setStyleSheet(f"""
            QLineEdit {{
                color: {Colors.TEXT_PRIMARY.name()};
                background-color: {Colors.SECONDARY_BG.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                border-radius: 4px;
                padding: 8px;
            }}
            QLineEdit:focus {{
                border: 1px solid {Colors.ACCENT_BLUE.name()};
            }}
        """)
        self.command_input.returnPressed.connect(self._on_command_entered)
        main_layout.addWidget(self.command_input)

    def _on_command_entered(self):
        """Handle the returnPressed signal from the command input."""
        command_text = self.command_input.text().strip()
        if command_text:
            self.append_output(f"$ {command_text}\n")
            self.command_entered.emit(command_text)
            self.command_input.clear()

    def append_output(self, text: str):
        """Appends text to the output view and ensures it scrolls to the bottom."""
        self.output_view.moveCursor(QTextCursor.MoveOperation.End)
        self.output_view.insertPlainText(text)
        self.output_view.ensureCursorVisible()

    def clear_output(self):
        """Clears the output view."""
        self.output_view.clear()