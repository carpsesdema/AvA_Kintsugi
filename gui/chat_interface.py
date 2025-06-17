# kintsugi_ava/gui/chat_interface.py
# UPDATED: Added a ModeToggle and logic for handling streaming chat responses.

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QFrame, QScrollArea, QHBoxLayout
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPalette
import qtawesome as qta

from .components import Colors, Typography, ModernButton
from .mode_toggle import ModeToggle
from core.event_bus import EventBus
from core.app_state import AppState
from core.interaction_mode import InteractionMode


class ChatBubble(QFrame):
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

        self.sender_label = QLabel(sender)
        self.sender_label.setFont(Typography.heading_small())
        self.sender_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")

        self.message_label = QLabel(text)
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.message_label.setFont(Typography.body())
        self.message_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")

        layout.addWidget(self.sender_label)
        layout.addWidget(self.message_label)

    def append_text(self, chunk: str):
        """Appends a chunk of text to the message label for streaming."""
        self.message_label.setText(self.message_label.text() + chunk)


class ChatMessageWidget(QWidget):
    def __init__(self, text: str, sender: str, is_user: bool):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 5, 10, 5)

        self.bubble = ChatBubble(text, sender, is_user)
        bubble_width = self.parent().width() * 0.75 if self.parent() else 800
        self.bubble.setMaximumWidth(int(bubble_width))

        if is_user:
            layout.addStretch()
            layout.addWidget(self.bubble)
        else:
            avatar = QLabel()
            avatar_icon = qta.icon("fa5s.atom", color=Colors.ACCENT_BLUE)
            avatar.setPixmap(avatar_icon.pixmap(28, 28))
            avatar.setFixedSize(30, 30)
            avatar.setAlignment(Qt.AlignmentFlag.AlignTop)

            layout.addWidget(avatar)
            layout.addWidget(self.bubble)
            layout.addStretch()

    def append_text(self, chunk: str):
        self.bubble.append_text(chunk)


class ChatInterface(QWidget):
    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.event_bus = event_bus
        self.conversation_history = []
        self.streaming_message_widget = None

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

        self.event_bus.subscribe("app_state_changed", self.on_app_state_changed)
        self.event_bus.subscribe("chat_cleared", self.clear_chat)
        self.event_bus.subscribe("streaming_message_start", self.on_streaming_start)
        self.event_bus.subscribe("streaming_message_chunk", self.on_streaming_chunk)
        self.event_bus.subscribe("streaming_message_end", self.on_streaming_end)

        self.on_app_state_changed(AppState.BOOTSTRAP, None)

    def on_app_state_changed(self, state: AppState, project_name: str | None):
        if state == AppState.BOOTSTRAP:
            self.input_box.setPlaceholderText("Describe the new application you want to build...")
            self.clear_chat("Hello! Let's build something amazing from scratch.")
        elif state == AppState.MODIFY:
            self.input_box.setPlaceholderText(f"What changes should we make to '{project_name}'?")
            self.clear_chat(f"Project '{project_name}' is loaded. I'm ready to make changes.")

    def _create_input_widget(self) -> QWidget:
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(10)

        # Mode Toggle Switch
        self.mode_toggle = ModeToggle()
        self.mode_toggle.modeChanged.connect(
            lambda mode: self.event_bus.emit("interaction_mode_changed", mode)
        )
        toggle_layout = QHBoxLayout()
        toggle_layout.addStretch()
        toggle_layout.addWidget(self.mode_toggle)
        toggle_layout.addStretch()
        container_layout.addLayout(toggle_layout)

        # Input Box Frame
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
        self.input_box.setFont(Typography.body())
        self.input_box.setStyleSheet("border: none; background-color: transparent; padding: 5px;")
        self.input_box.returnPressed.connect(self._on_send_message)
        send_button = ModernButton("Send", "primary")
        send_button.clicked.connect(self._on_send_message)
        layout.addWidget(self.input_box)
        layout.addWidget(send_button)

        container_layout.addWidget(input_frame)
        return container

    def _add_message(self, text: str, is_user: bool, sender: str = None) -> ChatMessageWidget:
        stretch_item = self.bubble_layout.takeAt(self.bubble_layout.count() - 1)
        sender_name = sender if sender else ("You" if is_user else "Kintsugi AvA")
        message_widget = ChatMessageWidget(text, sender_name, is_user)
        self.bubble_layout.addWidget(message_widget)
        self.bubble_layout.addStretch()

        QTimer.singleShot(10, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()))

        if not is_user:
            role = "assistant"
            self.conversation_history.append({"role": role, "content": text})
        return message_widget

    def on_streaming_start(self, sender: str):
        self.streaming_message_widget = self._add_message("", is_user=False, sender=sender)

    def on_streaming_chunk(self, chunk: str):
        if self.streaming_message_widget:
            self.streaming_message_widget.append_text(chunk)
            QTimer.singleShot(1, lambda: self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()))

    def on_streaming_end(self):
        if self.streaming_message_widget:
            full_text = self.streaming_message_widget.bubble.message_label.text()
            self.conversation_history.append({"role": "assistant", "content": full_text})
            self.streaming_message_widget = None

    def _on_send_message(self):
        user_text = self.input_box.text().strip()
        if user_text:
            self.input_box.clear()
            self._add_message(user_text, is_user=True)
            self.conversation_history.append({"role": "user", "content": user_text})
            self.event_bus.emit("user_request_submitted", user_text, self.conversation_history)

    def clear_chat(self, initial_message: str = "New session started."):
        print("[ChatInterface] Clearing chat history.")
        while self.bubble_layout.count() > 1:
            item = self.bubble_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.conversation_history.clear()
        self.on_streaming_start("Kintsugi AvA")
        self.on_streaming_chunk(initial_message)
        self.on_streaming_end()