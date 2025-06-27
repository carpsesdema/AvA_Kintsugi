# src/ava/gui/aura_toggle.py
from PySide6.QtWidgets import QAbstractButton
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPointF, Property, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QPen

from .components import Colors, Typography
import qtawesome as qta


class AuraToggle(QAbstractButton):
    """
    A sleek, animated toggle switch for activating Aura, the creative assistant.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(140, 34)
        self.setCursor(Qt.PointingHandCursor)

        self._circle_position = 4.0
        self._bg_color = Colors.ELEVATED_BG
        self._circle_color = Colors.TEXT_SECONDARY
        self._text_color = Colors.TEXT_SECONDARY

        self.animation = QPropertyAnimation(self, b"circle_position")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

        self.toggled.connect(self._on_toggled)

    @Property(float)
    def circle_position(self):
        return self._circle_position

    @circle_position.setter
    def circle_position(self, pos):
        self._circle_position = pos
        self.update()

    def sizeHint(self) -> QSize:
        return self.size()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background
        bg_rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QPen(Colors.BORDER_DEFAULT, 1))
        painter.setBrush(self._bg_color)
        painter.drawRoundedRect(bg_rect, 16, 16)

        # Draw Text
        painter.setFont(Typography.get_font(10, QFont.Weight.Bold))
        painter.setPen(self._text_color)
        painter.drawText(bg_rect.adjusted(30, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, "Aura Mode")

        # Draw Circle with Icon
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._circle_color)
        painter.drawEllipse(QPointF(self._circle_position + 15, self.height() / 2), 11, 11)

        icon_color = self._bg_color
        icon = qta.icon("fa5s.lightbulb", color=icon_color)
        icon.paint(painter, self.rect().adjusted(int(self._circle_position), 0, 0, 0))

    def _on_toggled(self, checked):
        self.animation.setEndValue(108.0 if checked else 4.0)
        self.animation.start()

        self._bg_color = Colors.ACCENT_PURPLE if checked else Colors.ELEVATED_BG
        self._circle_color = Colors.TEXT_PRIMARY if checked else Colors.TEXT_SECONDARY
        self._text_color = Colors.TEXT_PRIMARY if checked else Colors.TEXT_SECONDARY

    def enterEvent(self, event):
        if not self.isChecked():
            self._bg_color = QColor("#30363d")
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        if not self.isChecked():
            self._bg_color = Colors.ELEVATED_BG
        super().leaveEvent(event)
        self.update()