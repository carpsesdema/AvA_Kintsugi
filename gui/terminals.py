# kintsugi_ava/gui/terminals.py
# Placeholder for the streaming log terminal.

from PySide6.QtWidgets import QMainWindow, QTextEdit
from PySide6.QtCore import Qt

from .components import Colors, Typography

class TerminalsWindow(QMainWindow):
    """
    A placeholder window that will eventually contain a streaming log
    of the AI's thoughts and actions.
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
        self.log_view.setPlainText("--- Log Terminal Initialized ---")

        self.setCentralWidget(self.log_view)