# src/ava/gui/chat_interface.py
import json
import base64
import io
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea, QHBoxLayout, QFileDialog, QMessageBox, QMenu
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QPalette, QPixmap, QImage, QAction, QDragEnterEvent, QDropEvent

import qtawesome as qta

from src.ava.gui.components import Colors, Typography
from src.ava.gui.mode_toggle import ModeToggle
from src.ava.gui.advanced_chat_input import AdvancedChatInput
from src.ava.gui.loading_indicator import LoadingIndicator
from src.ava.core.event_bus import EventBus
from src.ava.core.app_state import AppState
from src.ava.core.interaction_mode import InteractionMode
from typing import Optional, Dict


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
    def __init__(self, text: str, sender: str, is_user: bool, event_bus: EventBus, image: Optional[QImage] = None):
        super().__init__()
        self.event_bus = event_bus
        self.is_user = is_user
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
            layout.addWidget(self.bubble)
            layout.addStretch()

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def append_text(self, chunk: str):
        self.bubble.append_text(chunk)

    def _show_context_menu(self, pos: QPoint):
        # Only show context menu for non-user messages with text content
        if self.is_user or not self.bubble.message_label:
            return

        menu = QMenu(self)
        use_as_prompt_action = QAction("Use as Build Prompt", self)
        use_as_prompt_action.triggered.connect(self._on_use_as_prompt)
        menu.addAction(use_as_prompt_action)
        menu.exec(self.mapToGlobal(pos))

    def _on_use_as_prompt(self):
        if self.bubble.message_label:
            prompt_text = self.bubble.message_label.text()
            self.event_bus.emit("build_prompt_from_chat_requested", prompt_text)


class ChatInterface(QWidget):
    # MODIFIED: Added project_root to __init__
    def __init__(self, event_bus: EventBus, project_root: Path):
        super().__init__()
        self.event_bus = event_bus
        self.project_root = project_root # Store project_root
        self.conversation_history = []
        self.streaming_message_widget = None
        self.streaming_sender = "Kintsugi AvA"  # Default sender

        self.setAcceptDrops(True) # --- NEW: Enable drop events ---

        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, Colors.PRIMARY_BG)
        self.setPalette(palette)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        self.thinking_panel = self._create_thinking_panel()
        main_layout.addWidget(self.thinking_panel)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; }")
        self.bubble_container = QWidget()
        self.bubble_layout = QVBoxLayout(self.bubble_container)
        self.bubble_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.bubble_layout.addStretch()
        self.scroll_area.setWidget(self.bubble_container)
        main_layout.addWidget(self.scroll_area, 1)

        self._create_header_controls(main_layout)

        self.input_widget = self._create_input_widget()
        main_layout.addWidget(self.input_widget)

        self._setup_event_subscriptions()
        self._add_message({"role": "assistant", "text": "Hello! Let's build something amazing from scratch."},
                          is_feedback=True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if not urls:
            return

        file_path = Path(urls[0].toLocalFile())
        if file_path.is_file():
            try:
                # Limit file size to prevent loading huge files
                if file_path.stat().st_size > 500 * 1024: # 500 KB limit
                    QMessageBox.warning(self, "File Too Large", "Cannot use files larger than 500 KB as context.")
                    return

                content = file_path.read_text(encoding='utf-8')
                self.input_widget.set_code_context(file_path.name, content)
                self.event_bus.emit("log_message_received", "ChatInterface", "info", f"Attached {file_path.name} as code context.")
            except Exception as e:
                QMessageBox.critical(self, "Error Reading File", f"Could not read file:\n{e}")
                self.event_bus.emit("log_message_received", "ChatInterface", "error", f"Failed to read dropped file {file_path.name}: {e}")

    def _create_thinking_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("thinking_panel")
        panel.setFixedHeight(50)
        panel.setStyleSheet(f"""
            #thinking_panel {{
                background-color: {Colors.SECONDARY_BG.name()};
                border-radius: 8px;
                padding: 5px 15px;
            }}
        """)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        loading_indicator = LoadingIndicator(self.project_root)
        loading_indicator.setFixedSize(38, 38)
        layout.addWidget(loading_indicator)

        label = QLabel("AI is working on your request...")
        label.setFont(Typography.body())
        label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")
        layout.addWidget(label)
        layout.addStretch()

        panel.hide()
        return panel

    def _create_header_controls(self, layout: QVBoxLayout):
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        self.mode_toggle = ModeToggle()
        self.mode_toggle.modeChanged.connect(self._on_mode_change_requested)
        self.mode_toggle.setMode(InteractionMode.BUILD, animate=False)
        controls_layout.addWidget(self.mode_toggle)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)

    def _setup_event_subscriptions(self):
        self.event_bus.subscribe("app_state_changed", self._on_app_state_changed)
        self.event_bus.subscribe("interaction_mode_changed", self._on_interaction_mode_changed)
        self.event_bus.subscribe("load_chat_success", self._on_chat_loaded)
        self.event_bus.subscribe("streaming_start", self.on_streaming_start)
        self.event_bus.subscribe("streaming_chunk", self.on_streaming_chunk)
        self.event_bus.subscribe("streaming_end", self.on_streaming_end)
        self.event_bus.subscribe("chat_cleared", self.clear_chat)
        self.scroll_area.verticalScrollBar().rangeChanged.connect(self._scroll_to_bottom)
        self.event_bus.subscribe("user_request_submitted", self.show_thinking_indicator)
        self.event_bus.subscribe("streaming_end", self.hide_thinking_indicator)
        self.event_bus.subscribe("ai_fix_workflow_complete", self.hide_thinking_indicator)

    def show_thinking_indicator(self, *args):
        self.thinking_panel.show()

    def hide_thinking_indicator(self, *args):
        self.thinking_panel.hide()

    def _scroll_to_bottom(self, min_val, max_val):
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def _on_app_state_changed(self, new_state: AppState, project_name: str = None):
        if new_state == AppState.BOOTSTRAP:
            self.input_widget.setPlaceholderText("Describe the new application you want to build...")
        elif new_state == AppState.MODIFY:
            self.input_widget.setPlaceholderText(f"What changes for '{project_name}'? Paste an image of an error!")
        current_mode = self.mode_toggle._current_mode
        self._on_interaction_mode_changed(current_mode, is_state_change=True)

    def _on_chat_loaded(self, conversation_history: list):
        self.clear_chat(initial_message=None)
        self.conversation_history = conversation_history.copy()
        for message in conversation_history:
            self._add_message(message, is_feedback=True)

    def _on_mode_change_requested(self, new_mode: InteractionMode):
        self.event_bus.emit("interaction_mode_change_requested", new_mode)

    def _on_interaction_mode_changed(self, new_mode: InteractionMode, is_state_change: bool = False):
        self.mode_toggle.setMode(new_mode)
        if new_mode == InteractionMode.CHAT:
            self.input_widget.setPlaceholderText("Ask a question, brainstorm ideas, or paste an image...")
            if not is_state_change: self._add_message(
                message_data={"role": "assistant", "text": "Switched to Chat mode."}, is_feedback=True)
        elif new_mode == InteractionMode.BUILD:
            pass
            if not is_state_change: self._add_message(
                message_data={"role": "assistant", "text": "Switched to Build mode. Ready to code."}, is_feedback=True)

    def _create_input_widget(self) -> AdvancedChatInput:
        input_widget = AdvancedChatInput()
        input_widget.message_sent.connect(self._on_user_message_sent)
        return input_widget

    def _on_user_message_sent(self, text: str, image_bytes: Optional[bytes], image_media_type: Optional[str], code_context: Optional[Dict[str, str]]):
        image_b64 = base64.b64encode(image_bytes).decode('utf-8') if image_bytes else None
        history_entry = {"role": "user", "text": text, "image_b64": image_b64, "media_type": image_media_type, "code_context": code_context}
        self._add_message(history_entry)
        self.event_bus.emit("user_request_submitted", text, self.conversation_history, image_bytes, image_media_type, code_context)

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
        message_widget = ChatMessageWidget(text, sender_name, is_user, self.event_bus, image=q_image)
        self.bubble_layout.addWidget(message_widget)
        self.bubble_layout.addStretch()

        if not is_feedback: self.conversation_history.append(message_data)
        return message_widget

    def on_streaming_start(self, sender: str):
        self.streaming_message_widget = None
        self.streaming_sender = sender

    def on_streaming_chunk(self, chunk: str):
        if self.streaming_message_widget is None:
            self.streaming_message_widget = self._add_message(
                {"role": "assistant", "sender": self.streaming_sender, "text": ""},
                is_feedback=True
            )

        if self.streaming_message_widget:
            self.streaming_message_widget.append_text(chunk)

    def on_streaming_end(self):
        if self.streaming_message_widget:
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
            self.clear_chat(None)
            for message_data in session_data["conversation_history"]:
                self._add_message(message_data, is_feedback=True)
            QMessageBox.information(self, "Success", "Chat session loaded successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load chat session: {e}")