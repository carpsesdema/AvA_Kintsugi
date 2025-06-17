# kintsugi_ava/gui/mode_toggle.py
# NEW FILE: A sleek, animated toggle switch for changing interaction modes.

from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import Qt, Signal, QPoint, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QColor, QFont, QPen

from .components import Colors, Typography


class ModeToggle(QWidget):
    """
    A sleek, animated toggle switch for changing between Chat and Build modes.
    """
    modeChanged = Signal(object)  # Emits the new InteractionMode enum

    def __init__(self, parent=None):
        super().__init__(parent)
        from core.interaction_mode import InteractionMode  # Local import
        self.setFixedSize(140, 32)
        self.setCursor(Qt.PointingHandCursor)

        self._current_mode = InteractionMode.BUILD
        self._circle_position = 106  # Start on the "Build" side

        # Animation for the toggle
        self.animation = QPropertyAnimation(self, b"circle_position")
        self.animation.setDuration(200)  # in milliseconds
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    @Property(int)
    def circle_position(self):
        return self._circle_position

    @circle_position.setter
    def circle_position(self, pos):
        self._circle_position = pos
        self.update()

    def setMode(self, mode):
        """Programmatically set the mode without emitting a signal."""
        from core.interaction_mode import InteractionMode
        self._current_mode = mode
        self.animation.stop()
        self.animation.setEndValue(106 if mode == InteractionMode.BUILD else 4)
        self.animation.start()

    def mousePressEvent(self, event):
        from core.interaction_mode import InteractionMode
        if self._current_mode == InteractionMode.BUILD:
            self._current_mode = InteractionMode.CHAT
            self.animation.setEndValue(4)
        else:
            self._current_mode = InteractionMode.BUILD
            self.animation.setEndValue(106)

        self.animation.start()
        self.modeChanged.emit(self._current_mode)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        from core.interaction_mode import InteractionMode
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background
        bg_rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QPen(Colors.BORDER_DEFAULT, 1))
        painter.setBrush(Colors.ELEVATED_BG)
        painter.drawRoundedRect(bg_rect, 15, 15)

        # Draw text labels
        painter.setFont(Typography.get_font(10, QFont.Weight.Bold))

        # Chat Label
        chat_color = Colors.TEXT_PRIMARY if self._current_mode == InteractionMode.CHAT else Colors.TEXT_SECONDARY
        painter.setPen(chat_color)
        painter.drawText(10, 0, 50, self.height(), Qt.AlignmentFlag.AlignCenter, "Chat")

        # Build Label
        build_color = Colors.TEXT_PRIMARY if self._current_mode == InteractionMode.BUILD else Colors.TEXT_SECONDARY
        painter.setPen(build_color)
        painter.drawText(80, 0, 50, self.height(), Qt.AlignmentFlag.AlignCenter, "Build")

        # Draw the sliding circle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Colors.ACCENT_BLUE)
        painter.drawEllipse(QPoint(self._circle_position + 14, self.height() // 2), 12, 12)