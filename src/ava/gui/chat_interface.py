# src/ava/gui/chat_interface.py
# UPDATED: Now uses AdvancedChatInput and displays images in bubbles.

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea, QHBoxLayout
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPalette, QPixmap, QImage
import qtawesome as qta

from .components import Colors, Typography, ModernButton
from .mode_toggle import ModeToggle
from .advanced_chat_input import AdvancedChatInput
from ava.core.event_bus import EventBus
from ava.core.app_state import AppState
from ava.core.interaction_mode import InteractionMode
from typing import Optional


class ChatBubble(QFrame):
    def __init__(self, text: str, sender: str, is_user: bool, image: Optional[QImage] = None):
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
        layout.setSpacing(8)

        # --- Image Display ---
        if image:
            self.image_label = QLabel()
            # --- THIS IS THE FIX ---
            # Explicitly convert QImage to QPixmap before scaling and setting.
            pixmap = QPixmap.fromImage(image)
            if pixmap.width() > 400:
                pixmap = pixmap.scaledToWidth(400, Qt.TransformationMode.SmoothTransformation)
            # --- END OF FIX ---
            self.image_label.setPixmap(pixmap)
            self.image_label.setStyleSheet("border-radius: 6px;")
            layout.addWidget(self.image_label)

        # --- Sender and Message Display ---
        self.sender_label = QLabel(sender)
        self.sender_label.setFont(Typography.heading_small())
        self.sender_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")
        layout.addWidget(self.sender_label)

        if text: # Only add message label if there is text
            self.message_label = QLabel(text)
            self.message_label.setWordWrap(True)
            self.message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.message_label.setFont(Typography.body())
            self.message_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")
            layout.addWidget(self.message_label)
        else:
            self.message_label = None # No text label to append to

    def append_text(self, chunk: str):
        """Appends a chunk of text to the message label for streaming."""
        if not self.message_label: # If no text was sent initially, create the label now
            # Find the layout to add the widget
            layout = self.layout()
            self.message_label = QLabel()
            self.message_label.setWordWrap(True)
            self.message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.message_label.setFont(Typography.body())
            self.message_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")
            layout.addWidget(self.message_label)

        self.message_label.setText(self.message_label.text() + chunk)


class ChatMessageWidget(QWidget):
    def __init__(self, text: str, sender: str, is_user: bool, image: Optional[QImage] = None):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 5, 10, 5)

        self.bubble = ChatBubble(text, sender, is_user, image)
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
        self.current_app_state = AppState.BOOTSTRAP
        self.current_project_name = None

        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, Colors.PRIMARY_BG)
        self.setPalette(palette)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # --- Chat History Area ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; }")
        self.bubble_container = QWidget()
        self.bubble_layout = QVBoxLayout(self.bubble_container)
        self.bubble_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.bubble_layout.addStretch()
        self.scroll_area.setWidget(self.bubble_container)

        # --- NEW Input Widget ---
        self.input_widget = self._create_input_widget()

        main_layout.addWidget(self.scroll_area, 1)
        main_layout.addWidget(self._create_top_input_bar()) # Mode toggle
        main_layout.addWidget(self.input_widget)

        # --- Connect Events ---
        self.event_bus.subscribe("app_state_changed", self.on_app_state_changed)
        self.event_bus.subscribe("chat_cleared", self.clear_chat)
        self.event_bus.subscribe("streaming_message_start", self.on_streaming_start)
        self.event_bus.subscribe("streaming_message_chunk", self.on_streaming_chunk)
        self.event_bus.subscribe("streaming_message_end", self.on_streaming_end)
        self.event_bus.subscribe("interaction_mode_changed", self.on_mode_changed)

        self.on_app_state_changed(AppState.BOOTSTRAP, None)

    def _create_top_input_bar(self) -> QWidget:
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0,0,0,0)
        self.mode_toggle = ModeToggle()
        self.mode_toggle.modeChanged.connect(
            lambda mode: self.event_bus.emit("interaction_mode_changed", mode)
        )
        container_layout.addStretch()
        container_layout.addWidget(self.mode_toggle)
        container_layout.addStretch()
        return container

    def on_app_state_changed(self, state: AppState, project_name: str | None):
        self.current_app_state = state
        self.current_project_name = project_name
        self.on_mode_changed(self.mode_toggle._current_mode, is_state_change=True)

        if state == AppState.BOOTSTRAP:
            self.clear_chat("Hello! Let's build something amazing from scratch.")
        else:
            self.clear_chat(f"Project '{project_name}' is loaded. I'm ready to make changes.")

    def on_mode_changed(self, new_mode: InteractionMode, is_state_change: bool = False):
        self.mode_toggle.setMode(new_mode)
        if new_mode == InteractionMode.CHAT:
            self.input_widget.setPlaceholderText("Ask a question, brainstorm ideas, or paste an image...")
            if not is_state_change: self._add_message("Switched to Chat mode.", is_user=False, is_feedback=True)
        elif new_mode == InteractionMode.BUILD:
            if self.current_app_state == AppState.BOOTSTRAP:
                self.input_widget.setPlaceholderText("Describe the new application you want to build...")
            else:
                self.input_widget.setPlaceholderText(f"What changes for '{self.current_project_name}'? Paste an image of an error!")
            if not is_state_change: self._add_message("Switched to Build mode. Ready to code.", is_user=False, is_feedback=True)

    def _create_input_widget(self) -> AdvancedChatInput:
        input_widget = AdvancedChatInput()
        input_widget.message_sent.connect(self._on_user_message_sent)
        return input_widget

    def _on_user_message_sent(self, text: str, image_bytes: Optional[bytes], image_media_type: Optional[str]):
        """Handles the send action from the new input widget."""
        q_image = None
        if image_bytes:
            q_image = QImage()
            q_image.loadFromData(image_bytes)

        self._add_message(text, is_user=True, image=q_image)
        # Emit with raw bytes, let the backend handle encoding
        self.event_bus.emit("user_request_submitted", text, self.conversation_history, image_bytes, image_media_type)

    def _add_message(self, text: str, is_user: bool, sender: str = None,
                     is_feedback: bool = False, image: Optional[QImage] = None) -> ChatMessageWidget:
        stretch_item = self.bubble_layout.takeAt(self.bubble_layout.count() - 1)
        sender_name = sender if sender else ("You" if is_user else "Kintsugi AvA")
        message_widget = ChatMessageWidget(text, sender_name, is_user, image=image)
        self.bubble_layout.addWidget(message_widget)
        self.bubble_layout.addStretch()

        QTimer.singleShot(10, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()))

        if not is_feedback:
            # TODO: Handle multimodal history correctly
            role = "user" if is_user else "assistant"
            self.conversation_history.append({"role": role, "content": text})

        return message_widget

    def on_streaming_start(self, sender: str):
        self.streaming_message_widget = self._add_message("", is_user=False, sender=sender, is_feedback=True)

    def on_streaming_chunk(self, chunk: str):
        if self.streaming_message_widget:
            self.streaming_message_widget.append_text(chunk)
            QTimer.singleShot(1, lambda: self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()))

    def on_streaming_end(self):
        if self.streaming_message_widget:
            full_text = ""
            if self.streaming_message_widget.bubble.message_label:
                full_text = self.streaming_message_widget.bubble.message_label.text()
            self.conversation_history.append({"role": "assistant", "content": full_text})
            self.streaming_message_widget = None

    def clear_chat(self, initial_message: str = "New session started."):
        while self.bubble_layout.count() > 1:
            item = self.bubble_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.conversation_history.clear()
        self.on_streaming_start("Kintsugi AvA")
        self.on_streaming_chunk(initial_message)
        self.on_streaming_end()