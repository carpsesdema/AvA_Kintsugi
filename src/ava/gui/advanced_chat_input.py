# src/ava/gui/advanced_chat_input.py
# NEW FILE: A feature-rich, multi-line chat input with image attachment capabilities.

import io
from typing import Optional

from PySide6.QtCore import Qt, Signal, QBuffer, QIODevice
from PySide6.QtGui import QImage, QKeySequence, QTextCursor, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton, QFrame

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
    message_sent = Signal(str, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._attached_image: Optional[QImage] = None
        self._attached_media_type: Optional[str] = None
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # --- Image Thumbnail Preview (hidden by default) ---
        self.thumbnail_preview = self._create_thumbnail_widget()
        main_layout.addWidget(self.thumbnail_preview)
        self.thumbnail_preview.hide()

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
        self.text_input.setFixedHeight(40) # Start with a reasonable height
        self.text_input.textChanged.connect(self._adjust_input_height)
        self.text_input.image_pasted.connect(self._on_image_pasted)
        self.text_input.send_message_requested.connect(self._on_send)

        # Bottom bar with send button
        bottom_bar_layout = QHBoxLayout()
        bottom_bar_layout.addStretch()
        send_button = ModernButton("Send", "primary")
        send_button.clicked.connect(self._on_send)
        bottom_bar_layout.addWidget(send_button)

        frame_layout.addWidget(self.text_input)
        frame_layout.addLayout(bottom_bar_layout)
        main_layout.addWidget(input_frame)

    def _create_thumbnail_widget(self) -> QWidget:
        widget = QFrame()
        widget.setObjectName("thumbnail_frame")
        widget.setFixedHeight(80)
        widget.setStyleSheet(f"""
            #thumbnail_frame {{
                background-color: {Colors.SECONDARY_BG.name()};
                border-radius: 8px;
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
            }}
        """)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        self.thumbnail_label = QLabel("Image Attached")
        self.thumbnail_label.setScaledContents(False)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.thumbnail_label)

        layout.addStretch()

        remove_button = QPushButton("×")
        remove_button.setFixedSize(24, 24)
        remove_button.setCursor(Qt.PointingHandCursor)
        remove_button.setStyleSheet(f"""
            QPushButton {{
                font-size: 20px;
                color: {Colors.TEXT_SECONDARY.name()};
                border: none;
                background-color: {Colors.ELEVATED_BG.name()};
                border-radius: 12px;
            }}
            QPushButton:hover {{
                background-color: {Colors.ACCENT_RED.name()};
                color: white;
            }}
        """)
        remove_button.clicked.connect(self._clear_attachment)
        layout.addWidget(remove_button, alignment=Qt.AlignmentFlag.AlignTop)
        return widget

    def _adjust_input_height(self):
        doc_height = self.text_input.document().size().height()
        # Clamp height between 40 and 150
        new_height = max(40, min(int(doc_height) + 10, 150))
        self.text_input.setFixedHeight(new_height)

    def _on_image_pasted(self, image: QImage):
        self._attached_image = image
        self._attached_media_type = "image/png" # Assume PNG for clipboard ops

        # --- THIS IS THE FIX ---
        # Convert the QImage to a QPixmap before setting it on the label.
        thumbnail_pixmap = QPixmap.fromImage(image.scaled(
            60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        ))
        self.thumbnail_label.setPixmap(thumbnail_pixmap)
        # --- END OF FIX ---

        self.thumbnail_preview.show()
        self.text_input.setFocus()

    def _clear_attachment(self):
        self._attached_image = None
        self._attached_media_type = None
        self.thumbnail_preview.hide()
        self.text_input.setFocus()

    def _on_send(self):
        text = self.text_input.toPlainText().strip()
        image_bytes = None

        if self._attached_image:
            # Convert QImage to bytes
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            self._attached_image.save(buffer, "PNG")
            image_bytes = buffer.data().data()

        if text or image_bytes:
            self.message_sent.emit(text, image_bytes, self._attached_media_type)
            self.text_input.clear()
            self._clear_attachment()
            self.text_input.setFixedHeight(40) # Reset height

    def setPlaceholderText(self, text: str):
        self.text_input.setPlaceholderText(text)