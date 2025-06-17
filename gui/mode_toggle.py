# kintsugi_ava/gui/mode_toggle.py
# UPDATED: Polished the UI with better spacing and alignment.

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
        self.setFixedSize(150, 34)  # Increased size for better spacing
        self.setCursor(Qt.PointingHandCursor)

        self._current_mode = InteractionMode.BUILD
        self._circle_position = 112  # Adjusted start on "Build" side

        # Animation for the toggle
        self.animation = QPropertyAnimation(self, b"circle_position")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    @Property(int)
    def circle_position(self):
        return self._circle_position

    @circle_position.setter
    def circle_position(self, pos):
        self._circle_position = pos
        self.update()

    def setMode(self, mode, animate=True):
        """Programmatically set the mode."""
        from core.interaction_mode import InteractionMode
        self._current_mode = mode

        target_pos = 112 if mode == InteractionMode.BUILD else 4

        if animate:
            self.animation.stop()
            self.animation.setEndValue(target_pos)
            self.animation.start()
        else:
            self.circle_position = target_pos

    def mousePressEvent(self, event):
        from core.interaction_mode import InteractionMode
        if self._current_mode == InteractionMode.BUILD:
            self.setMode(InteractionMode.CHAT)
        else:
            self.setMode(InteractionMode.BUILD)

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
        painter.drawRoundedRect(bg_rect, 16, 16)

        # Draw the sliding circle background (the highlight)
        highlight_color = Colors.ACCENT_BLUE.lighter(110)
        highlight_color.setAlpha(150)
        painter.setBrush(highlight_color)
        painter.setPen(Qt.PenStyle.NoPen)

        if self._current_mode == InteractionMode.CHAT:
            painter.drawRoundedRect(2, 2, 72, 30, 14, 14)
        else:
            painter.drawRoundedRect(76, 2, 72, 30, 14, 14)

        # Draw text labels
        painter.setFont(Typography.get_font(10, QFont.Weight.Bold))

        # Chat Label
        chat_color = Colors.TEXT_PRIMARY if self._current_mode == InteractionMode.CHAT else Colors.TEXT_SECONDARY
        painter.setPen(chat_color)
        painter.drawText(10, 0, 60, self.height(), Qt.AlignmentFlag.AlignCenter, "Chat")

        # Build Label
        build_color = Colors.TEXT_PRIMARY if self._current_mode == InteractionMode.BUILD else Colors.TEXT_SECONDARY
        painter.setPen(build_color)
        painter.drawText(80, 0, 60, self.height(), Qt.AlignmentFlag.AlignCenter, "Build")