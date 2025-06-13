# kintsugi_ava/gui/chat_interface.py
# The main chat interface of our application.

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from .components import Colors # Import our new color palette

class ChatInterface(QWidget):
    """
    The chat view. For now, it's a simple placeholder widget.
    It will later hold the chat bubbles and the user input box.
    """
    def __init__(self):
        super().__init__()

        # Set the background color using our design system
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Colors.PRIMARY_BG)
        self.setPalette(palette)

        # --- Layout and Placeholder Content ---
        layout = QVBoxLayout(self)
        placeholder_label = QLabel("Chat Interface Placeholder")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()}; font-size: 24px;")
        layout.addWidget(placeholder_label)