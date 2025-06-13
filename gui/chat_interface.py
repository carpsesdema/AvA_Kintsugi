# kintsugi_ava/gui/chat_interface.py
# The main chat interface of our application.

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

from .components import Colors # Import our color palette
from core.event_bus import EventBus # Import EventBus

class ChatInterface(QWidget):
    """
    The chat view. For now, it's a simple placeholder widget.
    It will later hold the chat bubbles and the user input box.
    """
    def __init__(self, event_bus: EventBus):
        """
        The __init__ method accepts the event_bus and subscribes its
        methods to events it cares about.
        """
        super().__init__()
        self.event_bus = event_bus # Store the event bus for later use

        # Set the background color using our design system
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Colors.PRIMARY_BG)
        self.setPalette(palette)

        # --- Layout and Placeholder Content ---
        layout = QVBoxLayout(self)
        self.placeholder_label = QLabel("Chat Interface Placeholder")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()}; font-size: 24px;")
        layout.addWidget(self.placeholder_label)

        # --- Subscribe to Events ---
        # This is the "listening" part of our decoupled system.
        # When the sidebar emits "new_session_requested", the event bus will
        # call our self.clear_chat method.
        self.event_bus.subscribe("new_session_requested", self.clear_chat)

    def clear_chat(self):
        """
        A placeholder method that responds to the 'new_session_requested' event.
        """
        print("[ChatInterface] Heard 'new_session_requested' event, clearing chat.")
        self.placeholder_label.setText("Chat Cleared! New Session Started.")