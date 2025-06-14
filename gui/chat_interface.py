from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QFrame, QScrollArea, QHBoxLayout
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPalette
import qtawesome as qta

from .components import Colors, Typography, ModernButton
from core.event_bus import EventBus


class ChatBubble(QFrame):
    """A styled frame containing the sender's name and message."""

    def __init__(self, text: str, sender: str, is_user: bool):
        super().__init__()
        self.setObjectName("chat_bubble")

        bg_color = Colors.ACCENT_BLUE if is_user else Colors.ELEVATED_BG
        self.setStyleSheet(f"""
            #chat_bubble {{
                background-color: {bg_color.name()};
                border-radius: 12px;
                padding: 10px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        sender_label = QLabel(sender)
        sender_label.setFont(Typography.heading_small())
        sender_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")

        message_label = QLabel(text)
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        message_label.setFont(Typography.body())
        message_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")

        layout.addWidget(sender_label)
        layout.addWidget(message_label)


class ChatMessageWidget(QWidget):
    """A full chat message row, including avatar (for AI) and the chat bubble."""

    def __init__(self, text: str, sender: str, is_user: bool):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 5, 10, 5)

        bubble = ChatBubble(text, sender, is_user)
        # Constrain the bubble's width to be a max of ~70% of the container
        bubble.setMaximumWidth(self.parent().width() * 0.7 if self.parent() else 800)

        if is_user:
            layout.addStretch()
            layout.addWidget(bubble)
        else:  # AI message
            avatar = QLabel()
            avatar_icon = qta.icon("fa5s.atom", color=Colors.ACCENT_BLUE)
            avatar.setPixmap(avatar_icon.pixmap(28, 28))
            avatar.setFixedSize(30, 30)
            avatar.setAlignment(Qt.AlignmentFlag.AlignTop)

            layout.addWidget(avatar)
            layout.addWidget(bubble)
            layout.addStretch()


class ChatInterface(QWidget):
    """
    The main chat view. It assembles the scroll area, message bubbles,
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
        main_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; }")

        self.bubble_container = QWidget()
        self.bubble_layout = QVBoxLayout(self.bubble_container)
        self.bubble_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.bubble_layout.addStretch()

        self.scroll_area.setWidget(self.bubble_container)
        self.input_widget = self._create_input_widget()

        main_layout.addWidget(self.scroll_area, 1)
        main_layout.addWidget(self.input_widget)

        self._add_message("Hello! I'm Kintsugi AvA. Let's build something amazing.", is_user=False)
        self.event_bus.subscribe("new_session_requested", self.clear_chat)

    def _create_input_widget(self) -> QFrame:
        input_frame = QFrame()
        input_frame.setObjectName("input_frame")
        input_frame.setStyleSheet(f"""
            #input_frame {{ 
                background-color: {Colors.SECONDARY_BG.name()}; 
                border-radius: 8px; 
                border: 1px solid {Colors.BORDER_DEFAULT.name()}; 
            }}
        """)
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
        # Remove the stretch item before adding a new message
        stretch_item = self.bubble_layout.takeAt(self.bubble_layout.count() - 1)

        sender_name = "You" if is_user else "Kintsugi AvA"
        message_widget = ChatMessageWidget(text, sender_name, is_user)

        self.bubble_layout.addWidget(message_widget)
        # Add the stretch item back at the end
        self.bubble_layout.addStretch()

        # Use QTimer to ensure the scroll happens after the layout has been updated
        QTimer.singleShot(10, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()))

        role = "user" if is_user else "assistant"
        self.conversation_history.append({"role": role, "content": text})

    def _on_send_message(self):
        """Handles sending the user's message."""
        user_text = self.input_box.text().strip()
        if user_text:
            self.input_box.clear()
            self._add_message(user_text, is_user=True)
            self.event_bus.emit("user_request_submitted", user_text, self.conversation_history)

    def _add_ai_response(self, text: str):
        """A dedicated public slot to handle adding real AI responses."""
        self._add_message(text, is_user=False)

    def clear_chat(self):
        print("[ChatInterface] Heard 'new_session_requested' event, clearing chat.")
        while self.bubble_layout.count() > 1:
            item = self.bubble_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.conversation_history.clear()
        self._add_message("New session started. How can I help you build today?", is_user=False)