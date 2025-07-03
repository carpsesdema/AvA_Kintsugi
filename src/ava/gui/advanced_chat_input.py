import io
from typing import Optional, Dict

from PySide6.QtCore import Qt, Signal, QBuffer, QIODevice, QByteArray
from PySide6.QtGui import QImage, QKeySequence, QTextCursor, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton, QFrame
import qtawesome as qta

from .components import Colors, Typography, ModernButton


class _PasteableTextEdit(QTextEdit):
    """
    An internal QTextEdit that captures pasted images instead of inserting them.
    It also handles Enter/Shift+Enter for sending/newlines.
    """
    image_pasted = Signal(QImage)
    send_message_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def canInsertFromMimeData(self, source) -> bool:
        # We can handle image data from the clipboard
        return source.hasImage() or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasImage():
            image = QImage(source.imageData())
            self.image_pasted.emit(image)
            return  # Don't call the base class implementation
        super().insertFromMimeData(source)

    def keyPressEvent(self, event):
        # Send on Enter, new line on Shift+Enter
        if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.send_message_requested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class AdvancedChatInput(QWidget):
    """The main chat input widget, coordinating text, image attachments, and sending."""
    message_sent = Signal(str, object, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._attached_image: Optional[QImage] = None
        self._attached_media_type: Optional[str] = None
        self._code_context: Optional[Dict[str, str]] = None
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # --- Code Context Preview (hidden by default) ---
        self.code_context_preview = self._create_context_widget("code_context", "fa5s.file-code",
                                                                "Code Context Attached")
        main_layout.addWidget(self.code_context_preview)
        self.code_context_preview.hide()

        # --- Image Thumbnail Preview (hidden by default) ---
        self.image_preview = self._create_context_widget("image", "fa5s.image", "Image Attached")
        main_layout.addWidget(self.image_preview)
        self.image_preview.hide()

        # --- Input Frame ---
        input_frame = QFrame()
        input_frame.setObjectName("input_frame")
        input_frame.setStyleSheet(f"""
            #input_frame {{
                background-color: {Colors.SECONDARY_BG.name()};
                border-radius: 8px;
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
            }}
        """)
        frame_layout = QVBoxLayout(input_frame)
        frame_layout.setContentsMargins(10, 5, 5, 5)
        frame_layout.setSpacing(5)

        self.text_input = _PasteableTextEdit()
        self.text_input.setPlaceholderText("Describe the new application you want to build...")
        self.text_input.setFont(Typography.body())
        self.text_input.setStyleSheet("border: none; background-color: transparent;")
        self.text_input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_input.setFixedHeight(40)  # Start with a reasonable height
        self.text_input.textChanged.connect(self._adjust_input_height)
        self.text_input.image_pasted.connect(self._on_image_pasted)
        self.text_input.send_message_requested.connect(self._on_send)

        # Bottom bar with send button
        bottom_bar_layout = QHBoxLayout()
        bottom_bar_layout.addStretch()
        self.send_button = ModernButton("Send", "primary")
        self.send_button.clicked.connect(self._on_send)
        bottom_bar_layout.addWidget(self.send_button)

        frame_layout.addWidget(self.text_input)
        frame_layout.addLayout(bottom_bar_layout)
        main_layout.addWidget(input_frame)

    def _create_context_widget(self, widget_type: str, icon_name: str, default_text: str) -> QFrame:
        widget = QFrame()
        widget.setObjectName(f"{widget_type}_frame")
        widget.setFixedHeight(50)
        widget.setStyleSheet(f"""
            #""" + widget.objectName() + f""" {{
                background-color: {Colors.SECONDARY_BG.name()};
                border-radius: 8px;
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
            }}
        """)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 5, 10, 5)

        icon_label = QLabel()
        icon_label.setPixmap(qta.icon(icon_name, color=Colors.TEXT_SECONDARY).pixmap(24, 24))
        layout.addWidget(icon_label)

        text_label = QLabel(default_text)
        text_label.setFont(Typography.body())
        text_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")
        widget.setProperty("text_label", text_label)
        layout.addWidget(text_label)

        layout.addStretch()

        remove_button = QPushButton("×")
        remove_button.setFixedSize(24, 24)
        remove_button.setCursor(Qt.PointingHandCursor)
        remove_button.setStyleSheet(f"""
            QPushButton {{
                font-size: 20px; color: {Colors.TEXT_SECONDARY.name()}; border: none;
                background-color: {Colors.ELEVATED_BG.name()}; border-radius: 12px;
            }}
            QPushButton:hover {{ background-color: {Colors.ACCENT_RED.name()}; color: white; }}
        """)
        if widget_type == "image":
            remove_button.clicked.connect(self._clear_image_attachment)
        elif widget_type == "code_context":
            remove_button.clicked.connect(self._clear_code_context)
        layout.addWidget(remove_button, alignment=Qt.AlignmentFlag.AlignTop)
        return widget

    def _adjust_input_height(self):
        doc_height = self.text_input.document().size().height()
        new_height = max(40, min(int(doc_height) + 10, 150))
        self.text_input.setFixedHeight(new_height)

    def _on_image_pasted(self, image: QImage):
        self._attached_image = image
        self._attached_media_type = "image/png"  # Assume PNG for pasted images

        # Update the preview
        preview_label = self.image_preview.property("text_label")
        if preview_label:
            pixmap = QPixmap.fromImage(image)
            # Create a thumbnail for the text label
            thumbnail = pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
            preview_label.setPixmap(thumbnail)
            preview_label.setText("")  # Clear the "Image Attached" text

        self.image_preview.show()
        self.text_input.setFocus()

    def set_code_context(self, filename: str, content: str):
        self._code_context = {filename: content}
        text_label = self.code_context_preview.property("text_label")
        if text_label:
            text_label.setText(f"Context: {filename}")
        self.code_context_preview.show()
        self.text_input.setFocus()

    def _clear_image_attachment(self):
        self._attached_image = None
        self._attached_media_type = None

        # Reset the preview widget to its default state
        preview_label = self.image_preview.property("text_label")
        if preview_label:
            preview_label.setPixmap(QPixmap())  # Clear the image
            preview_label.setText("Image Attached")  # Restore the text

        self.image_preview.hide()
        self.text_input.setFocus()

    def _clear_code_context(self):
        self._code_context = None
        self.code_context_preview.hide()
        self.text_input.setFocus()

    def _on_send(self):
        text = self.text_input.toPlainText().strip()
        image_bytes = None

        if self._attached_image:
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            self._attached_image.save(buffer, "PNG")
            # QBuffer.data() returns a QByteArray, which can be directly
            # converted to bytes. This silences the type checker warning.
            image_data: QByteArray = buffer.data()
            image_bytes = bytes(image_data)

        if text or image_bytes or self._code_context:
            self.message_sent.emit(text, image_bytes, self._attached_media_type, self._code_context)
            self.text_input.clear()
            self._clear_image_attachment()
            self._clear_code_context()
            self.text_input.setFixedHeight(40)

    def setPlaceholderText(self, text: str):
        self.text_input.setPlaceholderText(text)

    def set_send_button_text(self, text: str):
        self.send_button.setText(text)

    def set_text_and_focus(self, text: str):
        self.text_input.setPlainText(text)
        self.text_input.setFocus()
        cursor = self.text_input.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.text_input.setTextCursor(cursor)