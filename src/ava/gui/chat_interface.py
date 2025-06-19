# src/ava/gui/chat_interface.py
# UPDATED: Correctly uses the new GIF-based loading indicator.

import json
import base64
import io
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea, QHBoxLayout, QFileDialog, QMessageBox
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPalette, QPixmap, QImage, QMovie
import qtawesome as qta

from .components import Colors, Typography, ModernButton
from .mode_toggle import ModeToggle
from .advanced_chat_input import AdvancedChatInput
from .loading_indicator import LoadingIndicator
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
        if image:
            self.image_label = QLabel()
            pixmap = QPixmap.fromImage(image)
            if pixmap.width() > 400:
                pixmap = pixmap.scaledToWidth(400, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(pixmap)
            self.image_label.setStyleSheet("border-radius: 6px;")
            layout.addWidget(self.image_label)
        self.sender_label = QLabel(sender)
        self.sender_label.setFont(Typography.heading_small())
        self.sender_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")
        layout.addWidget(self.sender_label)
        if text:
            self.message_label = QLabel(text)
            self.message_label.setWordWrap(True)
            self.message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.message_label.setFont(Typography.body())
            self.message_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")
            layout.addWidget(self.message_label)
        else:
            self.message_label = None

    def append_text(self, chunk: str):
        if not self.message_label:
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
        main_layout.addWidget(self._create_top_input_bar())
        main_layout.addWidget(self.input_widget)

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
        container_layout.setContentsMargins(0, 0, 0, 0)
        self.mode_toggle = ModeToggle()
        self.mode_toggle.modeChanged.connect(lambda mode: self.event_bus.emit("interaction_mode_changed", mode))
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
            if not is_state_change: self._add_message(
                message_data={"role": "assistant", "text": "Switched to Chat mode."}, is_feedback=True)
        elif new_mode == InteractionMode.BUILD:
            if self.current_app_state == AppState.BOOTSTRAP:
                self.input_widget.setPlaceholderText("Describe the new application you want to build...")
            else:
                self.input_widget.setPlaceholderText(
                    f"What changes for '{self.current_project_name}'? Paste an image of an error!")
            if not is_state_change: self._add_message(
                message_data={"role": "assistant", "text": "Switched to Build mode. Ready to code."}, is_feedback=True)

    def _create_input_widget(self) -> AdvancedChatInput:
        input_widget = AdvancedChatInput()
        input_widget.message_sent.connect(self._on_user_message_sent)
        return input_widget

    def _on_user_message_sent(self, text: str, image_bytes: Optional[bytes], image_media_type: Optional[str]):
        image_b64 = base64.b64encode(image_bytes).decode('utf-8') if image_bytes else None
        history_entry = {"role": "user", "text": text, "image_b64": image_b64, "media_type": image_media_type}
        self._add_message(history_entry)
        self.event_bus.emit("user_request_submitted", text, self.conversation_history, image_bytes, image_media_type)

    def _add_message(self, message_data: dict, is_feedback: bool = False):
        role = message_data.get("role", "assistant")
        is_user = role == "user"
        text = message_data.get("text", "")
        image_b64 = message_data.get("image_b64")
        q_image = None
        if image_b64:
            q_image = QImage()
            q_image.loadFromData(base64.b64decode(image_b64))

        sender_name = "You" if is_user else message_data.get("sender", "Kintsugi AvA")

        stretch_item = self.bubble_layout.takeAt(self.bubble_layout.count() - 1)
        message_widget = ChatMessageWidget(text, sender_name, is_user, image=q_image)
        self.bubble_layout.addWidget(message_widget)
        self.bubble_layout.addStretch()

        QTimer.singleShot(10, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()))
        if not is_feedback: self.conversation_history.append(message_data)
        return message_widget

    def on_streaming_start(self, sender: str):
        # --- THIS IS THE ARCHITECTURALLY CORRECT FIX ---
        self._remove_loading_indicator()

        # 1. Create a ChatMessageWidget with NO text. This creates the correctly aligned avatar and bubble.
        self.streaming_message_widget = self._add_message(
            {"role": "assistant", "sender": sender, "text": None},
            is_feedback=True
        )

        # 2. Get the empty bubble from the widget.
        bubble = self.streaming_message_widget.bubble
        bubble.sender_label.hide()  # Hide the sender name temporarily

        # 3. Create the loading indicator and add it INSIDE the bubble's layout.
        indicator = LoadingIndicator()
        indicator.setFixedSize(32, 32)
        bubble.layout().addWidget(indicator, alignment=Qt.AlignCenter)
        bubble.setMinimumHeight(50)  # Give it some space
        # --- END OF FIX ---

    def on_streaming_chunk(self, chunk: str):
        if self.streaming_message_widget and self.streaming_message_widget.bubble.layout().count() > 1:
            # This means it's still a loading bubble. We need to convert it.
            bubble = self.streaming_message_widget.bubble

            # Remove the indicator widget
            indicator_item = bubble.layout().takeAt(1)
            if indicator_item and indicator_item.widget():
                indicator_item.widget().deleteLater()

            # Show the sender label again and set its text
            bubble.sender_label.show()

        if self.streaming_message_widget:
            self.streaming_message_widget.append_text(chunk)
            QTimer.singleShot(1, lambda: self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()))

    def _remove_loading_indicator(self):
        # This now just cleans up the whole widget if a new stream starts before the old one finishes.
        if self.streaming_message_widget:
            # Check if it's a loading widget (has more than just the sender label)
            if self.streaming_message_widget.bubble.layout().count() > 1:
                self.streaming_message_widget.deleteLater()
                self.streaming_message_widget = None

    def on_streaming_end(self):
        if self.streaming_message_widget:
            # If the widget still exists, it's a completed text stream.
            # We need to add its content to the history.
            if self.streaming_message_widget.bubble.message_label:
                full_text = self.streaming_message_widget.bubble.message_label.text()
                final_message_data = {"role": "assistant", "text": full_text, "image_b64": None, "media_type": None}
                self.conversation_history.append(final_message_data)

            self.streaming_message_widget = None

    def clear_chat(self, initial_message: str = "New session started."):
        self._remove_loading_indicator()
        while self.bubble_layout.count() > 1:
            item = self.bubble_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
        self.conversation_history.clear()
        self._add_message(message_data={"role": "assistant", "text": initial_message})

    def save_session(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Chat Session", "", "JSON Files (*.json)")
        if not file_path: return
        session_data = {"schema_version": "1.0", "saved_at": datetime.now().isoformat(),
                        "conversation_history": self.conversation_history}
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
            QMessageBox.information(self, "Success", "Chat session saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save chat session: {e}")

    def load_session(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Chat Session", "", "JSON Files (*.json)")
        if not file_path: return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            if "conversation_history" not in session_data: raise ValueError(
                "Invalid session file: 'conversation_history' key not found.")
            self.clear_chat("Session loaded.")
            self.conversation_history.pop()
            for message_data in session_data["conversation_history"]: self._add_message(message_data)
            QMessageBox.information(self, "Success", "Chat session loaded successfully.")
        except Exception as e:
            QMessageBox.information(self, "Error", f"Failed to load chat session: {e}")