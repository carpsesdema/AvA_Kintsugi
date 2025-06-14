# kintsugi_ava/gui/terminals.py
# V2: Plumbing update to pass EventBus down to the IntegratedTerminal.

from PySide6.QtWidgets import QMainWindow, QTextEdit, QTabWidget, QVBoxLayout, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor, QColor
from datetime import datetime
import html

from .components import Colors, Typography
from .integrated_terminal import IntegratedTerminal


class TerminalsWindow(QMainWindow):
    """
    A window that holds multiple terminal-like views.
    - The Log View shows formatted, real-time log messages from the application.
    - The Integrated Terminal provides an interactive command line.
    """

    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        self.setWindowTitle("Kintsugi AvA - Terminals")
        self.setGeometry(250, 250, 900, 600)

        # Main Tab Widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border-top: 1px solid {Colors.BORDER_DEFAULT.name()};
            }}
            QTabBar::tab {{
                background: {Colors.SECONDARY_BG.name()};
                color: {Colors.TEXT_SECONDARY.name()};
                padding: 8px 15px;
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                border-bottom: none;
            }}
            QTabBar::tab:selected, QTabBar::tab:hover {{
                background: {Colors.PRIMARY_BG.name()};
                color: {Colors.TEXT_PRIMARY.name()};
            }}
        """)

        # --- Log Viewer Tab ---
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

        # --- Integrated Terminal Tab ---
        self.integrated_terminal = IntegratedTerminal(self.event_bus)
        self.event_bus.subscribe("terminal_output_received", self.integrated_terminal.append_output)

        # Add tabs
        self.tab_widget.addTab(self.integrated_terminal, "Interactive Terminal")
        self.tab_widget.addTab(self.log_view, "Log Viewer")

        self.setCentralWidget(self.tab_widget)

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

        escaped_content = html.escape(content).replace('\n', '<br>')

        log_html = (
            f'<span style="color: #8b949e;">[{timestamp}]</span> '
            f'<span style="color: {log_color}; font-weight: bold;">[{source.upper()}]</span> '
            f'<span style="color: {Colors.TEXT_PRIMARY.name()};">{escaped_content}</span>'
        )

        self.log_view.append(log_html)
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def show_fix_button(self):
        """Shows the fix button on the interactive terminal."""
        self.integrated_terminal.show_fix_button()
        self.tab_widget.setCurrentWidget(self.integrated_terminal)  # Switch to terminal tab

    def hide_fix_button(self):
        """Hides the fix button on the interactive terminal."""
        self.integrated_terminal.hide_fix_button()