# src/ava/gui/chat_interface.py
# FINAL FIX: Replaced QTimer-based scrolling with a robust rangeChanged signal.

import json
import base64
import io
import sys
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
    def __init__(self, text: str, sender: str, is_user: bool, image: Optional[QImage] = None, is_loading: bool = False):
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
            if is_loading:
                # For loading state, use the LoadingIndicator widget
                self.avatar_widget = LoadingIndicator()
                self.avatar_widget.setFixedSize(48, 48)
            else:
                # For normal state, use the gear base image
                self.avatar_widget = QLabel()

                # Find the gear base image
                if getattr(sys, 'frozen', False):
                    asset_dir = Path(sys._MEIPASS) / "ava" / "assets"
                else:
                    asset_dir = Path(__file__).resolve().parent.parent / "assets"

                gear_base_path = asset_dir / "loading_gear_base.png"
                if gear_base_path.exists():
                    pixmap = QPixmap(str(gear_base_path))
                    scaled_pixmap = pixmap.scaled(46, 46, Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation)
                    self.avatar_widget.setPixmap(scaled_pixmap)
                else:
                    # Fallback to icon if image not found
                    avatar_icon = qta.icon("fa5s.cog", color=Colors.ACCENT_BLUE)
                    self.avatar_widget.setPixmap(avatar_icon.pixmap(46, 46))

                self.avatar_widget.setFixedSize(48, 48)
                self.avatar_widget.setAlignment(Qt.AlignmentFlag.AlignTop)

            layout.addWidget(self.avatar_widget)
            layout.addWidget(self.bubble)
            layout.addStretch()

    def append_text(self, chunk: str):
        self.bubble.append_text(chunk)

    def switch_to_normal_avatar(self):
        """Switch from loading indicator to normal gear avatar"""
        if hasattr(self, 'avatar_widget') and isinstance(self.avatar_widget, LoadingIndicator):
            # Remove the loading indicator
            self.layout().removeWidget(self.avatar_widget)
            self.avatar_widget.deleteLater()

            # Create normal gear avatar
            self.avatar_widget = QLabel()

            if getattr(sys, 'frozen', False):
                asset_dir = Path(sys._MEIPASS) / "ava" / "assets"
            else:
                asset_dir = Path(__file__).resolve().parent.parent / "assets"

            gear_base_path = asset_dir / "loading_gear_base.png"
            if gear_base_path.exists():
                pixmap = QPixmap(str(gear_base_path))
                scaled_pixmap = pixmap.scaled(46, 46, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)
                self.avatar_widget.setPixmap(scaled_pixmap)
            else:
                avatar_icon = qta.icon("fa5s.cog", color=Colors.ACCENT_BLUE)
                self.avatar_widget.setPixmap(avatar_icon.pixmap(46, 46))

            self.avatar_widget.setFixedSize(48, 48)
            self.avatar_widget.setAlignment(Qt.AlignmentFlag.AlignTop)

            # Insert it back at position 0 (before the bubble)
            self.layout().insertWidget(0, self.avatar_widget)


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
        main_layout.addWidget(self.scroll_area, 1)  # Give scroll area the stretch

        self._create_header_controls(main_layout)

        self.input_widget = self._create_input_widget()
        main_layout.addWidget(self.input_widget)  # No stretch for input

        self._setup_event_subscriptions()
        self._add_message({"role": "assistant", "text": "Hello! Let's build something amazing from scratch."},
                          is_feedback=True)

    def _create_header_controls(self, layout: QVBoxLayout):
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        self.mode_toggle = ModeToggle()
        self.mode_toggle.modeChanged.connect(self._on_mode_changed)
        self.mode_toggle.setMode(InteractionMode.BUILD, animate=False)
        controls_layout.addWidget(self.mode_toggle)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)

    def _setup_event_subscriptions(self):
        self.event_bus.subscribe("app_state_changed", self._on_app_state_changed)
        self.event_bus.subscribe("load_chat_success", self._on_chat_loaded)
        self.event_bus.subscribe("streaming_start", self.on_streaming_start)
        self.event_bus.subscribe("streaming_chunk", self.on_streaming_chunk)
        self.event_bus.subscribe("streaming_end", self.on_streaming_end)

        # --- THIS IS THE FIX ---
        # Connect the scroll bar's rangeChanged signal to a handler that
        # will always scroll to the bottom. This is more reliable than a timer.
        self.scroll_area.verticalScrollBar().rangeChanged.connect(self._scroll_to_bottom)
        # --- END OF FIX ---

    def _scroll_to_bottom(self):
        """A robust slot to scroll to the bottom of the chat."""
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def _on_app_state_changed(self, new_state: AppState, project_name: str = None):
        self.current_app_state = new_state
        self.current_project_name = project_name
        if new_state == AppState.BOOTSTRAP:
            self.input_widget.setPlaceholderText("Describe the new application you want to build...")
        elif new_state == AppState.MODIFY:
            self.input_widget.setPlaceholderText(f"What changes for '{project_name}'? Paste an image of an error!")
        current_mode = self.mode_toggle._current_mode
        self._on_mode_changed(current_mode, is_state_change=True)

    def _on_chat_loaded(self, conversation_history: list):
        self.clear_chat(initial_message=None)
        self.conversation_history = conversation_history.copy()
        for message in conversation_history:
            self._add_message(message, is_feedback=True)

    def _on_mode_changed(self, new_mode: InteractionMode, is_state_change: bool = False):
        self.event_bus.emit("interaction_mode_changed", new_mode)
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

    def _add_message(self, message_data: dict, is_feedback: bool = False, is_loading: bool = False):
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
        message_widget = ChatMessageWidget(text, sender_name, is_user, image=q_image, is_loading=is_loading)
        self.bubble_layout.addWidget(message_widget)
        self.bubble_layout.addStretch()

        if not is_feedback: self.conversation_history.append(message_data)
        return message_widget

    def on_streaming_start(self, sender: str):
        self._remove_loading_indicator()

        # Create a message widget with loading indicator as avatar
        self.streaming_message_widget = self._add_message(
            {"role": "assistant", "sender": sender, "text": None},
            is_feedback=True,
            is_loading=True  # This flag makes it use LoadingIndicator as avatar
        )

    def on_streaming_chunk(self, chunk: str):
        if self.streaming_message_widget:
            # When first text arrives, switch from loading indicator to normal gear avatar
            if not self.streaming_message_widget.bubble.message_label:
                self.streaming_message_widget.switch_to_normal_avatar()

            self.streaming_message_widget.append_text(chunk)

    def _remove_loading_indicator(self):
        if self.streaming_message_widget:
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
        for i in reversed(range(self.bubble_layout.count())):
            widget = self.bubble_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        self.bubble_layout.addStretch()
        self.conversation_history.clear()
        if initial_message:
            self._add_message({"role": "assistant", "text": initial_message}, is_feedback=True)

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
            if "conversation_history" not in session_data:
                raise ValueError("Invalid session file: 'conversation_history' key not found.")
            self.clear_chat(None)  # Don't show initial message
            for message_data in session_data["conversation_history"]:
                self._add_message(message_data, is_feedback=True)
            QMessageBox.information(self, "Success", "Chat session loaded successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load chat session: {e}")