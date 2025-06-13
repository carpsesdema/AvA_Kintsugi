# kintsugi_ava/gui/chat_interface.py
# The main chat interface, now with bubbles, scrolling, and input.

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QFrame, QScrollArea, QHBoxLayout
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette

from .components import Colors, Typography, ModernButton
from core.event_bus import EventBus


class ChatBubble(QFrame):
    """A custom widget to display a single chat message."""

    def __init__(self, text: str, is_user: bool):
        super().__init__()
        self.setObjectName("chat_bubble")

        # Bubble Style
        bg_color = Colors.ELEVATED_BG
        alignment = Qt.AlignmentFlag.AlignLeft
        if is_user:
            bg_color = Colors.ACCENT_BLUE
            alignment = Qt.AlignmentFlag.AlignRight

        self.setStyleSheet(f"""
            #chat_bubble {{
                background-color: {bg_color.name()};
                border-radius: 12px;
                padding: 10px;
            }}
        """)

        # Layout for the bubble
        bubble_layout = QVBoxLayout(self)

        message_label = QLabel(text)
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        message_label.setFont(Typography.body())
        message_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")

        bubble_layout.addWidget(message_label)

        # Main layout to handle alignment
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(10, 5, 10, 5)

        if is_user:
            main_layout.addStretch()  # Push bubble to the right
            main_layout.addWidget(self)
        else:
            main_layout.addWidget(self)
            main_layout.addStretch()  # Push bubble to the left

        self.setLayout(main_layout)


class ChatInterface(QWidget):
    """
    The main chat view. It now assembles the scroll area, message bubbles,
    and a dedicated input widget.
    """

    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.event_bus = event_bus
        self.conversation_history = []

        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, Colors.PRIMARY_BG)
        self.setPalette(palette)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # --- Scroll Area for Bubbles ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; }")

        self.bubble_container = QWidget()
        self.bubble_layout = QVBoxLayout(self.bubble_container)
        self.bubble_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.bubble_layout.addStretch()

        self.scroll_area.setWidget(self.bubble_container)

        # --- Input Widget ---
        self.input_widget = self._create_input_widget()

        main_layout.addWidget(self.scroll_area, 1)  # Give scroll area more space
        main_layout.addWidget(self.input_widget)

        self._add_message("Hello! I'm Kintsugi AvA. Let's build something solid.", is_user=False)
        self.event_bus.subscribe("new_session_requested", self.clear_chat)
        # We will create this new event soon
        self.event_bus.subscribe("ai_response_ready", self._add_ai_response)

    def _create_input_widget(self) -> QFrame:
        """Factory for the message input box and send button."""
        input_frame = QFrame()
        input_frame.setStyleSheet(f"""
            #input_frame {{
                background-color: {Colors.SECONDARY_BG.name()};
                border-radius: 8px;
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
            }}
        """)
        input_frame.setObjectName("input_frame")

        layout = QHBoxLayout(input_frame)
        layout.setContentsMargins(5, 5, 5, 5)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Type your request here...")
        self.input_box.setFont(Typography.body())
        self.input_box.setStyleSheet("border: none; background-color: transparent; padding: 5px;")
        self.input_box.returnPressed.connect(self._on_send_message)

        send_button = ModernButton("Send", "primary")
        send_button.clicked.connect(self._on_send_message)

        layout.addWidget(self.input_box)
        layout.addWidget(send_button)

        return input_frame

    def _add_message(self, text: str, is_user: bool):
        """Adds a new chat bubble to the scroll area."""
        # Remove the stretch before adding a new bubble
        stretch_item = self.bubble_layout.takeAt(self.bubble_layout.count() - 1)

        bubble = ChatBubble(text, is_user)
        self.bubble_layout.addWidget(bubble)

        # Add the stretch back at the end
        self.bubble_layout.addStretch()

        # Ensure the scroll area scrolls to the new message
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

        # Store message in history
        role = "user" if is_user else "assistant"
        self.conversation_history.append({"role": role, "content": text})

    def _on_send_message(self):
        """Handles the send button click or enter press."""
        user_text = self.input_box.text().strip()
        if user_text:
            self.input_box.clear()
            self._add_message(user_text, is_user=True)
            # This is where we will tell the Application to start the AI workflow
            self.event_bus.emit("user_request_submitted", user_text, self.conversation_history)

            # For now, let's just simulate an AI response for testing
            self.event_bus.emit("ai_response_ready", f"Placeholder AI response for: '{user_text}'")

    def _add_ai_response(self, text: str):
        """A dedicated slot to handle adding AI responses."""
        self._add_message(text, is_user=False)

    def clear_chat(self):
        """Clears all bubbles and resets the chat interface."""
        print("[ChatInterface] Heard 'new_session_requested' event, clearing chat.")
        # Clear the layout
        while self.bubble_layout.count() > 1:  # Keep the stretch
            item = self.bubble_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.conversation_history.clear()
        self._add_message("New session started. How can I help you build today?", is_user=False)