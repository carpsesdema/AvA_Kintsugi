# kintsugi_ava/gui/chat_interface.py
# V3: Removes direct subscription to AI events. Now a pure "View" component.

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QFrame, QScrollArea, QHBoxLayout
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPalette

from .components import Colors, Typography, ModernButton
from core.event_bus import EventBus

class ChatBubble(QFrame):
    """A custom widget to display a single chat message."""
    def __init__(self, text: str, is_user: bool):
        super().__init__()
        self.setObjectName("chat_bubble")
        bg_color = Colors.ACCENT_BLUE if is_user else Colors.ELEVATED_BG
        alignment = Qt.AlignmentFlag.AlignRight if is_user else Qt.AlignmentFlag.AlignLeft
        self.setStyleSheet(f"""
            #chat_bubble {{ background-color: {bg_color.name()}; border-radius: 12px; padding: 10px; }}
        """)
        bubble_layout = QVBoxLayout(self)
        message_label = QLabel(text)
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        message_label.setFont(Typography.body())
        message_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")
        bubble_layout.addWidget(message_label)
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(10, 5, 10, 5)
        if is_user: main_layout.addStretch()
        main_layout.addWidget(self)
        if not is_user: main_layout.addStretch()
        self.setLayout(main_layout)

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
        main_layout.setSpacing(10)
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
        self._add_message("Hello! I'm Kintsugi AvA. Let's build something solid.", is_user=False)
        self.event_bus.subscribe("new_session_requested", self.clear_chat)
        # --- THE FIX ---
        # We remove this line. The Application class is now responsible
        # for telling the chat interface when to add an AI response.
        # self.event_bus.subscribe("ai_response_ready", self._add_ai_response)
        # --- END OF FIX ---

    def _create_input_widget(self) -> QFrame:
        input_frame = QFrame()
        input_frame.setObjectName("input_frame")
        input_frame.setStyleSheet(f"""
            #input_frame {{ background-color: {Colors.SECONDARY_BG.name()}; border-radius: 8px; border: 1px solid {Colors.BORDER_DEFAULT.name()}; }}
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
        stretch_item = self.bubble_layout.takeAt(self.bubble_layout.count() - 1)
        bubble = ChatBubble(text, is_user)
        self.bubble_layout.addWidget(bubble)
        self.bubble_layout.addStretch()
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())
        role = "user" if is_user else "assistant"
        self.conversation_history.append({"role": role, "content": text})

    def _on_send_message(self):
        """Handles sending the user's message."""
        user_text = self.input_box.text().strip()
        if user_text:
            self.input_box.clear()
            self._add_message(user_text, is_user=True)
            self.event_bus.emit("user_request_submitted", user_text, self.conversation_history)

    @Slot(str)
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