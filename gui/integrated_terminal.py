# kintsugi_ava/gui/integrated_terminal.py
# V3: Added dynamic "Review & Fix" button for the co-pilot workflow.

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QFrame
)
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtCore import Signal, Qt
import qtawesome as qta

from .components import Colors, Typography, ModernButton


class IntegratedTerminal(QWidget):
    """
    An integrated terminal that now includes a dynamic button to trigger
    the AI review and fix process.
    """
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
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 1. Action Buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)

        run_main_btn = ModernButton("Run main.py", "primary")
        run_main_btn.clicked.connect(lambda: self.command_entered.emit("run_main"))

        install_reqs_btn = ModernButton("Install Requirements", "secondary")
        install_reqs_btn.clicked.connect(lambda: self.command_entered.emit("install_reqs"))

        # --- New "Review & Fix" Button ---
        self.fix_button = ModernButton("Review & Fix", "primary")
        self.fix_button.setIcon(qta.icon("fa5s.magic", color=Colors.TEXT_PRIMARY.name()))
        self.fix_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT_RED.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: 1px solid #ff7b72;
                border-radius: 6px;
                padding: 5px 15px;
            }}
            QPushButton:hover {{
                background-color: #ff4747;
            }}
        """)
        self.fix_button.clicked.connect(lambda: self.command_entered.emit("review_and_fix"))
        self.fix_button.hide()  # Hidden by default

        button_layout.addWidget(run_main_btn)
        button_layout.addWidget(install_reqs_btn)
        button_layout.addWidget(self.fix_button)
        button_layout.addStretch()

        main_layout.addLayout(button_layout)

        # 2. Output Display
        self.output_view = QTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setFont(Typography.get_font(10, family="JetBrains Mono"))
        self.output_view.setStyleSheet(f"""
            QTextEdit {{
                color: {Colors.TEXT_SECONDARY.name()};
                background-color: transparent;
                border: none;
                padding: 5px;
            }}
        """)
        self.output_view.setPlaceholderText("Command output will appear here...")
        main_layout.addWidget(self.output_view, 1)

        # 3. Command Input
        self.command_input = QLineEdit()
        self.command_input.setFont(Typography.get_font(10, family="JetBrains Mono"))
        self.command_input.setPlaceholderText("Enter command (e.g., 'pip list') and press Enter")
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
        main_layout.addWidget(self.command_input)

        # Connect the command signal to the event bus
        self.command_entered.connect(
            lambda cmd: self.event_bus.emit("terminal_command_entered", cmd)
        )

    def _on_command_entered(self):
        """Handle the returnPressed signal from the command input."""
        command_text = self.command_input.text().strip()
        if command_text:
            self.append_output(f"> {command_text}\n")
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

    def show_fix_button(self):
        """Makes the 'Review & Fix' button visible."""
        self.fix_button.show()

    def hide_fix_button(self):
        """Hides the 'Review & Fix' button."""
        self.fix_button.hide()