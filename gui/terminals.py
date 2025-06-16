# kintsugi_ava/gui/terminals.py
# V4: Added missing methods to support event coordinator wiring

from PySide6.QtWidgets import QMainWindow, QTextEdit
from PySide6.QtGui import QTextCursor
from datetime import datetime
import html

from .components import Colors, Typography


class TerminalsWindow(QMainWindow):
    """
    A window that acts as a dedicated Log Viewer, showing formatted,
    real-time log messages from the application's various services.
    It contains no interactive elements but supports terminal output events.
    """

    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        self.setWindowTitle("Kintsugi AvA - Log Viewer")
        self.setGeometry(250, 250, 900, 600)

        # The Log View is now the central widget. No tabs, no IntegratedTerminal.
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
        self.log_view.setHtml("<h3>Kintsugi AvA Log Viewer Initialized</h3>")

        self.setCentralWidget(self.log_view)

    def add_log_message(self, source: str, message_type: str, content: str):
        """A public slot that receives log data and displays it in the log viewer."""
        timestamp = datetime.now().strftime("%H:%M:%S")

        type_colors = {
            "info": "#58a6ff",
            "success": "#3fb950",
            "warning": "#d29922",
            "error": "#f85149",
            "ai_call": "#a5a6ff"
        }
        log_color = type_colors.get(message_type, Colors.TEXT_SECONDARY.name())

        # Escape content to prevent HTML injection issues from logs
        escaped_content = html.escape(content).replace('\n', '<br>')

        log_html = (
            f'<span style="color: #8b949e;">[{timestamp}]</span> '
            f'<span style="color: {log_color}; font-weight: bold;">[{source.upper()}]</span> '
            f'<span style="color: {Colors.TEXT_PRIMARY.name()};">{escaped_content}</span>'
        )

        self.log_view.append(log_html)
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def handle_output(self, text: str):
        """
        Handle terminal output events - converts to log format.
        This method is expected by the event coordinator.
        """
        # Convert terminal output to a log message
        self.add_log_message("Terminal", "info", text)

    def clear_terminal(self):
        """
        Clear the terminal/log view.
        This method is expected by the event coordinator.
        """
        self.log_view.clear()
        self.log_view.setHtml("<h3>Kintsugi AvA Log Viewer - Cleared</h3>")

    def show(self):
        """Overridden show method to ensure window comes to front."""
        super().show()
        self.activateWindow()
        self.raise_()