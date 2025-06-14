# kintsugi_ava/gui/agent_node.py

from PySide6.QtWidgets import QGraphicsObject, QGraphicsDropShadowEffect
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QFont
from PySide6.QtCore import QRectF, Qt, QPropertyAnimation, QEasingCurve, Property

from .components import Colors, Typography


class AgentNode(QGraphicsObject):
    """A stylish, animated node representing an AI agent in the graph."""

    WIDTH = 160
    HEIGHT = 80
    BORDER_RADIUS = 10

    def __init__(self, agent_id: str, name: str, icon: str):
        super().__init__()
        self.agent_id = agent_id
        self.name = name
        self.icon = icon
        self._status = "idle"  # idle, working, success, error
        self._status_text = "Ready"

        # Animation properties
        self._border_opacity = 0.0
        self.border_animation = QPropertyAnimation(self, b"borderOpacity")
        self.border_animation.setDuration(300)
        self.border_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

    def boundingRect(self):
        return QRectF(-5, -5, self.WIDTH + 10, self.HEIGHT + 10)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        bg_color = {
            "idle": Colors.ELEVATED_BG, "working": Colors.ELEVATED_BG,
            "success": QColor("#1f2c21"), "error": QColor("#2e1a1a")
        }.get(self._status, Colors.ELEVATED_BG)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.WIDTH, self.HEIGHT, self.BORDER_RADIUS, self.BORDER_RADIUS)

        # Status Border
        border_color = {
            "working": Colors.ACCENT_BLUE, "success": Colors.ACCENT_GREEN, "error": Colors.ACCENT_RED
        }.get(self._status)

        if border_color:
            pen = QPen(border_color, 2)
            pen_color = pen.color()
            pen_color.setAlphaF(self._border_opacity)
            pen.setColor(pen_color)
            painter.setPen(pen)
            painter.drawRoundedRect(0, 0, self.WIDTH, self.HEIGHT, self.BORDER_RADIUS, self.BORDER_RADIUS)

        # Content
        painter.setPen(Colors.TEXT_PRIMARY)
        painter.setFont(Typography.get_font(24))
        painter.drawText(QRectF(10, 10, 40, 40), Qt.AlignmentFlag.AlignCenter, self.icon)

        painter.setFont(Typography.heading_small())
        painter.drawText(QRectF(50, 15, 100, 20), self.name)

        painter.setPen(Colors.TEXT_SECONDARY)
        painter.setFont(Typography.body())

        # --- THE FIX IS HERE ---
        # The correct enum is Qt.AlignmentFlag, not Qt.TextFlag
        alignment_flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        painter.drawText(QRectF(50, 40, 100, 30), alignment_flags, self._status_text)
        # --- END OF FIX ---

    def set_status(self, status: str, status_text: str):
        self._status = status
        self._status_text = status_text
        target_opacity = 1.0 if status != "idle" else 0.0
        self.border_animation.setEndValue(target_opacity)
        self.border_animation.start()
        self.update()

    def get_border_opacity(self):
        return self._border_opacity

    def set_border_opacity(self, opacity):
        self._border_opacity = opacity
        self.update()

    borderOpacity = Property(float, get_border_opacity, set_border_opacity)