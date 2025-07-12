# src/ava/gui/chat_interface.py
import json
import base64
import io
import re
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea, QHBoxLayout, QFileDialog, QMessageBox, \
    QMenu, QTextBrowser
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QPalette, QPixmap, QImage, QAction, QDragEnterEvent, QDropEvent, QTextOption, QResizeEvent

import qtawesome as qta

from src.ava.gui.components import Colors, Typography, ModernButton
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
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)

        if image:
            self.image_label = QLabel()
            pixmap = QPixmap.fromImage(image)
            if pixmap.width() > 400:
                pixmap = pixmap.scaledToWidth(400, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(pixmap)
            self.image_label.setStyleSheet("border-radius: 6px;")
            self.layout.addWidget(self.image_label)

        self.sender_label = QLabel(sender)
        self.sender_label.setFont(Typography.heading_small())
        self.sender_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")
        self.layout.addWidget(self.sender_label)

        self.content_widget = None
        self.set_text(text)

    def resizeEvent(self, event: QResizeEvent):
        """Handle resize events to reflow text and adjust height."""
        super().resizeEvent(event)
        self.update_browser_height()

    def is_markdown(self, text: str) -> bool:
        """A simple heuristic to detect if the text is likely markdown."""
        return any(marker in text for marker in ['\n##', '\n###', '\n*', '```'])

    def update_browser_height(self):
        """Adjusts the QTextBrowser's height to fit its content."""
        if not isinstance(self.content_widget, QTextBrowser):
            return
        # Add a small margin for better padding and to prevent minor scrollbar visibility
        height = self.content_widget.document().size().height() + 5
        self.content_widget.setMinimumHeight(int(height))

    def set_text(self, text: str, is_streaming: bool = False):
        use_browser = is_streaming or self.is_markdown(text)

        if (use_browser and not isinstance(self.content_widget, QTextBrowser)) or \
                (not use_browser and not isinstance(self.content_widget, QLabel)):
            if self.content_widget:
                self.content_widget.deleteLater()

            if use_browser:
                self.content_widget = QTextBrowser()
                self.content_widget.setReadOnly(True)
                self.content_widget.setOpenExternalLinks(True)
                self.content_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                self.content_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                self.content_widget.setStyleSheet(f"""
                    QTextBrowser {{
                        background-color: transparent;
                        border: none;
                        color: {Colors.TEXT_PRIMARY.name()};
                        font-family: "{Typography.body().family()}";
                        font-size: {Typography.body().pointSize()}pt;
                    }}
                """)
                self.content_widget.document().contentsChanged.connect(self.update_browser_height)
            else:
                self.content_widget = QLabel()
                self.content_widget.setWordWrap(True)
                self.content_widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                self.content_widget.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")

            self.content_widget.setFont(Typography.body())
            self.layout.addWidget(self.content_widget)

        if isinstance(self.content_widget, QTextBrowser):
            self.content_widget.setMarkdown(text)
        else:
            self.content_widget.setText(text)

    def append_text(self, chunk: str):
        if not isinstance(self.content_widget, QTextBrowser):
            current_text = self.content_widget.text() if self.content_widget else ""
            self.set_text(current_text + chunk, is_streaming=True)
        else:
            current_markdown = self.content_widget.toMarkdown()
            self.content_widget.setMarkdown(current_markdown + chunk)

    def get_full_text(self) -> str:
        if isinstance(self.content_widget, QTextBrowser):
            return self.content_widget.toMarkdown()
        elif isinstance(self.content_widget, QLabel):
            return self.content_widget.text()
        return ""


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
        if self.is_user:
            return

        menu = QMenu(self)
        use_as_prompt_action = QAction("🚀 Use as Build Prompt", self)
        use_as_prompt_action.triggered.connect(self._on_use_as_prompt)
        menu.addAction(use_as_prompt_action)
        menu.exec(self.mapToGlobal(pos))

    def _on_use_as_prompt(self):
        prompt_text = self.bubble.get_full_text()
        # Extract content from the first markdown block if it exists
        match = re.search(r'```markdown\n(.*)```', prompt_text, re.DOTALL)
        if match:
            prompt_text = match.group(1).strip()
        self.event_bus.emit("build_prompt_from_chat_requested", prompt_text)


class ChatInterface(QWidget):
    def __init__(self, event_bus: EventBus, project_root: Path):
        super().__init__()
        self.event_bus = event_bus
        self.project_manager = None
        self.project_root = project_root
        self.conversation_history = []
        self.streaming_message_widget = None
        self.streaming_sender = "Aura"

        self.setAcceptDrops(True)

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
        self._add_message({"role": "assistant", "sender": "Aura", "text": "Hello! Let's plan and build something amazing."},
                          is_feedback=True)
        # Set initial UI state to match the default mode (BUILD)
        self._on_interaction_mode_changed(InteractionMode.BUILD)

    def set_project_manager(self, pm):
        self.project_manager = pm

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
                if file_path.stat().st_size > 500 * 1024:
                    QMessageBox.warning(self, "File Too Large", "Cannot use files larger than 500 KB as context.")
                    return
                content = file_path.read_text(encoding='utf-8')
                self.input_widget.set_code_context(file_path.name, content)
                self.event_bus.emit("log_message_received", "ChatInterface", "info",
                                    f"Attached {file_path.name} as code context.")
            except Exception as e:
                QMessageBox.critical(self, "Error Reading File", f"Could not read file:\n{e}")
                self.event_bus.emit("log_message_received", "ChatInterface", "error",
                                    f"Failed to read dropped file {file_path.name}: {e}")

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
        controls_layout.setSpacing(10)

        self.mode_toggle = ModeToggle()
        self.mode_toggle.modeChanged.connect(self._on_mode_change_requested)
        self.mode_toggle.setMode(InteractionMode.BUILD, animate=False)
        controls_layout.addWidget(self.mode_toggle)

        # ProjectTypeSelector removed
        controls_layout.addStretch()
        layout.addLayout(controls_layout)

    def _setup_event_subscriptions(self):
        self.event_bus.subscribe("app_state_changed", self._on_app_state_changed)
        self.event_bus.subscribe("interaction_mode_changed", self._on_interaction_mode_changed)
        self.event_bus.subscribe("streaming_start", self.on_streaming_start)
        self.event_bus.subscribe("streaming_chunk", self.on_streaming_chunk)
        self.event_bus.subscribe("streaming_end", self.on_streaming_end)
        self.event_bus.subscribe("chat_cleared", self.clear_chat)
        self.scroll_area.verticalScrollBar().rangeChanged.connect(self._scroll_to_bottom)
        self.event_bus.subscribe("user_request_submitted", self.show_thinking_indicator)
        self.event_bus.subscribe("streaming_end", self.hide_thinking_indicator)
        self.event_bus.subscribe("ai_workflow_finished", self.hide_thinking_indicator)

    def show_thinking_indicator(self, *args):
        self.thinking_panel.show()

    def hide_thinking_indicator(self, *args):
        self.thinking_panel.hide()

    def _scroll_to_bottom(self, min_val, max_val):
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def _on_app_state_changed(self, new_state: AppState, project_name: str = None):
        if self.mode_toggle._current_mode == InteractionMode.BUILD:
            if new_state == AppState.BOOTSTRAP:
                self.input_widget.setPlaceholderText("Describe the new application you want to build...")
            elif new_state == AppState.MODIFY:
                self.input_widget.setPlaceholderText(
                    f"What changes for '{project_name}'? Paste an error or describe a new feature...")

    def _on_mode_change_requested(self, new_mode: InteractionMode):
        self.event_bus.emit("interaction_mode_change_requested", new_mode)

    def _on_interaction_mode_changed(self, new_mode: InteractionMode):
        """Handles the visual and placeholder changes when switching modes."""
        self.mode_toggle.setMode(new_mode)
        input_frame = self.input_widget.findChild(QFrame, "input_frame")

        if new_mode == InteractionMode.PLAN:
            self.input_widget.setPlaceholderText("Discuss your ideas with Aura...")
            self.input_widget.set_send_button_text("Ask Aura")
            if input_frame:
                input_frame.setStyleSheet(f"""
                    #input_frame {{
                        background-color: {Colors.SECONDARY_BG.name()};
                        border-radius: 8px;
                        border: 1px solid {Colors.ACCENT_PURPLE.name()};
                    }}
                """)
        elif new_mode == InteractionMode.BUILD:
            if self.project_manager and self.project_manager.active_project_name != "(none)":
                self.input_widget.setPlaceholderText(
                    f"What changes for '{self.project_manager.active_project_name}'? Paste an error or describe a new feature...")
            else:
                self.input_widget.setPlaceholderText("Describe the new application you want to build...")
            self.input_widget.set_send_button_text("Build")
            if input_frame:
                input_frame.setStyleSheet(f"""
                    #input_frame {{
                        background-color: {Colors.SECONDARY_BG.name()};
                        border-radius: 8px;
                        border: 1px solid {Colors.ACCENT_BLUE.name()};
                    }}
                """)

    def _create_input_widget(self) -> AdvancedChatInput:
        input_widget = AdvancedChatInput()
        input_widget.message_sent.connect(self._on_user_message_sent)
        return input_widget

    def _on_user_message_sent(self, text: str, image_bytes: Optional[bytes], image_media_type: Optional[str],
                              code_context: Optional[Dict[str, str]]):
        q_image = None
        if image_bytes:
            q_image = QImage()
            q_image.loadFromData(image_bytes)
        image_b64 = base64.b64encode(image_bytes).decode('utf-8') if image_bytes else None

        history_entry = {"role": "user", "text": text, "image_b64": image_b64, "media_type": image_media_type,
                         "code_context": code_context}
        self._add_message(history_entry, image_override=q_image)

        self.event_bus.emit("user_request_submitted", text, self.conversation_history, image_bytes,
                            image_media_type, code_context)
        self.auto_save_session()

    def _add_message(self, message_data: dict, is_feedback: bool = False, image_override: Optional[QImage] = None):
        role = message_data.get("role", "assistant")
        is_user = role == "user"
        text = message_data.get("text") or message_data.get("content", "")
        q_image = image_override
        if q_image is None:
            image_b64 = message_data.get("image_b64")
            if image_b64:
                q_image = QImage()
                q_image.loadFromData(base64.b64decode(image_b64))

        sender_name = "You" if is_user else message_data.get("sender", "Aura")
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
        self.streaming_message_widget.append_text(chunk)

    def on_streaming_end(self):
        if self.streaming_message_widget:
            full_text = self.streaming_message_widget.bubble.get_full_text()
            final_message_data = {"role": "assistant", "sender": self.streaming_sender, "text": full_text}
            self.conversation_history.append(final_message_data)
            self.streaming_message_widget = None
            self.auto_save_session()

    def clear_chat(self, initial_message: str = "New session started."):
        while self.bubble_layout.count() > 1:
            item = self.bubble_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self.conversation_history.clear()
        if initial_message:
            self._add_message({"role": "assistant", "sender": "Aura", "text": initial_message}, is_feedback=True)

    def get_session_filepath(self) -> Optional[Path]:
        if not self.project_manager or not self.project_manager.active_project_path:
            return None
        project_dir = self.project_manager.active_project_path
        sessions_dir = project_dir / ".ava_sessions"
        sessions_dir.mkdir(exist_ok=True)
        return sessions_dir / "project_chat.json"

    def auto_save_session(self):
        file_path = self.get_session_filepath()
        if not file_path:
            return
        session_data = {"schema_version": "1.2", "saved_at": datetime.now().isoformat(),
                        "conversation_history": self.conversation_history}
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
        except Exception as e:
            self.log("error", f"Auto-save session failed: {e}")

    def load_project_session(self):
        file_path = self.get_session_filepath()
        if not file_path or not file_path.exists():
            self.clear_chat("Aura is ready to plan! What's on your mind?")
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            self.clear_chat(None)
            self.conversation_history = session_data.get("conversation_history", [])
            for message_data in self.conversation_history:
                self._add_message(message_data, is_feedback=True)
            if not self.conversation_history:
                self.clear_chat("Aura is ready to plan! What's on your mind?")
        except Exception as e:
            self.log("error", f"Failed to auto-load session from {file_path}: {e}")
            self.clear_chat("Aura is ready to plan! What's on your mind?")

    def save_session(self):
        file_path_str, _ = QFileDialog.getSaveFileName(self, "Save Chat Session", "", "JSON Files (*.json)")
        if not file_path_str: return
        file_path = Path(file_path_str)
        session_data = {"schema_version": "1.2", "saved_at": datetime.now().isoformat(),
                        "conversation_history": self.conversation_history}
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
            QMessageBox.information(self, "Success", "Chat session saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save chat session: {e}")

    def load_session(self):
        file_path_str, _ = QFileDialog.getOpenFileName(self, "Load Chat Session", "", "JSON Files (*.json)")
        if not file_path_str: return
        file_path = Path(file_path_str)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            self.clear_chat(None)
            self.conversation_history = session_data.get("conversation_history", [])
            for message_data in self.conversation_history:
                self._add_message(message_data, is_feedback=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load chat session: {e}")

    def log(self, level, message):
        self.event_bus.emit("log_message_received", "ChatInterface", level, message)