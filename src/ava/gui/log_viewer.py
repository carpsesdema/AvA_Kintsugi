# src/ava/gui/log_viewer.py
import qasync
from PySide6.QtWidgets import QMainWindow, QTextEdit, QWidget, QVBoxLayout
from PySide6.QtGui import QColor, QTextCharFormat, QFont
from src.ava.core.event_bus import EventBus
from .components import Colors, Typography
from datetime import datetime

class LogViewerWindow(QMainWindow):
    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.event_bus = event_bus
        self.setWindowTitle("Kintsugi AvA - Log Viewer")
        self.setGeometry(200, 200, 900, 600)

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

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.log_view)
        self.setCentralWidget(central_widget)

        self.event_bus.subscribe("log_message_received", self.append_log)
        self.append_log("LogViewer", "info", "Log viewer initialized. Waiting for messages...")

    @qasync.Slot(str, str, str)
    def append_log(self, source: str, msg_type: str, content: str):
        # Color mapping
        color_map = {
            "info": Colors.TEXT_SECONDARY,
            "success": Colors.ACCENT_GREEN,
            "error": Colors.ACCENT_RED,
            "warning": QColor("#d29922"),  # Yellow
            "ai_call": Colors.ACCENT_BLUE,
        }
        color = color_map.get(msg_type.lower(), Colors.TEXT_PRIMARY)

        # Move cursor to end
        cursor = self.log_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        # Format timestamp
        time_format = QTextCharFormat()
        time_format.setForeground(Colors.TEXT_SECONDARY)
        time_format.setFont(Typography.get_font(9, family="JetBrains Mono"))
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        cursor.insertText(f"{timestamp} ", time_format)

        # Format source
        source_format = QTextCharFormat()
        source_format.setForeground(color)
        source_format.setFontWeight(QFont.Weight.Bold)
        cursor.insertText(f"[{source.upper()}] ", source_format)

        # Format content
        content_format = QTextCharFormat()
        content_format.setForeground(color)
        cursor.insertText(f"{content}\n", content_format)

        # Scroll to the bottom to make the latest log message visible
        self.log_view.ensureCursorVisible()

    def show(self):
        super().show()
        self.activateWindow()
        self.raise_()