# kintsugi_ava/gui/terminals.py
# A real, live-streaming log terminal.

from PySide6.QtWidgets import QMainWindow, QTextEdit
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QTextCursor, QColor
from datetime import datetime
import html

from .components import Colors, Typography


class TerminalsWindow(QMainWindow):
    """
    A window that displays formatted, real-time log messages from the application.
    It listens for events and formats them for clear, readable output.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kintsugi AvA - Log Terminal")
        self.setGeometry(250, 250, 900, 500)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(Typography.get_font(10, family="JetBrains Mono"))
        self.log_view.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.PRIMARY_BG.name()};
                color: {Colors.TEXT_SECONDARY.name()};
                border: none;
                padding: 10px;
            }}
        """)
        self.log_view.setPlainText("--- Kintsugi AvA Log Terminal Initialized ---")
        self.setCentralWidget(self.log_view)

    @Slot(str, str, str)
    def add_log_message(self, source: str, message_type: str, content: str):
        """A public slot that receives log data and displays it."""

        timestamp = datetime.now().strftime("%H:%M:%S")

        # Define colors for different message types
        type_colors = {
            "info": "#58a6ff",  # Blue
            "success": "#3fb950",  # Green
            "warning": "#d29922",  # Yellow/Orange
            "error": "#f85149",  # Red
            "ai_call": "#a5a6ff"  # Purple
        }
        log_color = type_colors.get(message_type, Colors.TEXT_SECONDARY.name())

        # Escape content to prevent it from being interpreted as HTML
        escaped_content = html.escape(content).replace('\n', '<br>')

        # Construct the log message using simple HTML for styling
        log_html = (
            f'<span style="color: #8b949e;">[{timestamp}]</span> '
            f'<span style="color: {log_color}; font-weight: bold;">[{source.upper()}]</span> '
            f'<span style="color: {Colors.TEXT_PRIMARY.name()};">{escaped_content}</span>'
        )

        self.log_view.append(log_html)

        # Auto-scroll to the bottom
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())