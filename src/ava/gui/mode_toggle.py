# src/ava/gui/mode_toggle.py
# UPDATED: Polished the UI with better spacing and alignment.

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QFont, QPen

from .components import Colors, Typography
from src.ava.core.interaction_mode import InteractionMode


class ModeToggle(QWidget):
    """
    A sleek, animated toggle switch for changing between Plan and Build modes.
    """
    modeChanged = Signal(object)  # Emits the new InteractionMode enum

    def __init__(self, parent=None):
        super().__init__(parent)
        # Adjusted for shorter "Plan" / "Build" text
        self.setFixedSize(150, 34)
        self.setCursor(Qt.PointingHandCursor)

        self._current_mode = InteractionMode.BUILD
        # The x-position of the sliding highlight rectangle
        self._highlight_x = 77  # Start on the right for "Build"

        # Animation for the toggle
        self.animation = QPropertyAnimation(self, b"highlight_x")
        self.animation.setDuration(250)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    @Property(int)
    def highlight_x(self):
        return self._highlight_x

    @highlight_x.setter
    def highlight_x(self, pos):
        self._highlight_x = pos
        self.update()

    def setMode(self, mode, animate=True):
        """Programmatically set the mode."""
        if self._current_mode == mode:
            return

        self._current_mode = mode

        # Positions for the left edge of the highlight rectangle
        plan_pos = 2
        build_pos = self.width() - 71 - 2  # 150 - 71 - 2 = 77
        target_pos = build_pos if mode == InteractionMode.BUILD else plan_pos

        if animate:
            self.animation.stop()
            self.animation.setEndValue(target_pos)
            self.animation.start()
        else:
            self.highlight_x = target_pos

    def mousePressEvent(self, event):
        if self._current_mode == InteractionMode.BUILD:
            new_mode = InteractionMode.PLAN
        else:
            new_mode = InteractionMode.BUILD

        self.setMode(new_mode)
        self.modeChanged.emit(new_mode)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Draw background
        bg_rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QPen(Colors.BORDER_DEFAULT, 1))
        painter.setBrush(Colors.ELEVATED_BG)
        painter.drawRoundedRect(bg_rect, 16, 16)

        # 2. Draw the sliding highlight
        highlight_color = Colors.ACCENT_PURPLE if self._current_mode == InteractionMode.PLAN else Colors.ACCENT_BLUE
        painter.setBrush(highlight_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.highlight_x, 2, 71, 30, 14, 14)

        # 3. Draw text labels
        painter.setFont(Typography.get_font(10, QFont.Weight.Bold))

        plan_color = Colors.TEXT_PRIMARY if self._current_mode == InteractionMode.PLAN else Colors.TEXT_SECONDARY
        build_color = Colors.TEXT_PRIMARY if self._current_mode == InteractionMode.BUILD else Colors.TEXT_SECONDARY

        painter.setPen(plan_color)
        painter.drawText(0, 0, self.width() // 2, self.height(), Qt.AlignmentFlag.AlignCenter, "Plan")

        painter.setPen(build_color)
        painter.drawText(self.width() // 2, 0, self.width() // 2, self.height(), Qt.AlignmentFlag.AlignCenter, "Build")