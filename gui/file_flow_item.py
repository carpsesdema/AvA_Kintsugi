# kintsugi_ava/gui/file_flow_item.py
# Animated file objects that move through the workflow visualization

from PySide6.QtWidgets import QGraphicsObject, QGraphicsDropShadowEffect
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QPainterPath
from PySide6.QtCore import QRectF, Qt, QPropertyAnimation, QEasingCurve, Property, Signal, QPointF
import qtawesome as qta

from .components import Colors, Typography


class FileFlowItem(QGraphicsObject):
    """
    A visual representation of a file moving through the AI workflow.
    Shows filename, operation type, and current status with smooth animations.
    """

    # Signals
    animation_finished = Signal(str)  # Emits file_id when animation completes

    # Constants
    WIDTH = 120
    HEIGHT = 32
    BORDER_RADIUS = 16

    def __init__(self, file_id: str, filename: str, operation_type: str):
        super().__init__()
        self.file_id = file_id
        self.filename = filename
        self.operation_type = operation_type  # 'create', 'modify', 'fix'
        self.status = 'pending'  # 'pending', 'processing', 'complete', 'error'

        # Animation properties
        self._position = QPointF(0, 0)
        self._opacity = 1.0
        self._scale = 1.0

        # Animation objects
        self.move_animation = QPropertyAnimation(self, b"position")
        self.move_animation.setDuration(2000)
        self.move_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.move_animation.finished.connect(lambda: self.animation_finished.emit(self.file_id))

        self.fade_animation = QPropertyAnimation(self, b"opacity")
        self.fade_animation.setDuration(500)

        self.scale_animation = QPropertyAnimation(self, b"scale")
        self.scale_animation.setDuration(300)
        self.scale_animation.setEasingCurve(QEasingCurve.Type.OutBack)

        # Visual effects
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, True)

    def boundingRect(self):
        margin = 5
        return QRectF(-margin, -margin, self.WIDTH + 2 * margin, self.HEIGHT + 2 * margin)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Apply scale transform
        painter.scale(self._scale, self._scale)

        # Background color based on operation type and status
        bg_color = self._get_background_color()

        # Draw main rectangle
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(self._get_border_color(), 2))

        rect = QRectF(0, 0, self.WIDTH, self.HEIGHT)
        painter.drawRoundedRect(rect, self.BORDER_RADIUS, self.BORDER_RADIUS)

        # Draw operation icon
        icon_rect = QRectF(8, 6, 20, 20)
        painter.setPen(QPen(Colors.TEXT_PRIMARY, 1))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, self._get_operation_icon())

        # Draw filename (truncated if necessary)
        text_rect = QRectF(32, 6, self.WIDTH - 40, 20)
        painter.setPen(QPen(Colors.TEXT_PRIMARY, 1))
        painter.setFont(Typography.get_font(9))

        # Truncate filename if too long
        display_name = self.filename
        if len(display_name) > 12:
            display_name = display_name[:9] + "..."

        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, display_name)

        # Draw status indicator
        if self.status == 'processing':
            self._draw_processing_indicator(painter)

    def _get_background_color(self):
        """Returns background color based on operation type and status."""
        base_colors = {
            'create': QColor("#1f2c21"),  # Dark green
            'modify': QColor("#1f262c"),  # Dark blue
            'fix': QColor("#2c2a1f"),  # Dark yellow
            'test': QColor("#2c1f1f")  # Dark red
        }

        if self.status == 'error':
            return QColor("#2e1a1a")  # Error red
        elif self.status == 'complete':
            return base_colors.get(self.operation_type, Colors.ELEVATED_BG)
        else:
            return Colors.ELEVATED_BG

    def _get_border_color(self):
        """Returns border color based on operation type."""
        colors = {
            'create': Colors.ACCENT_GREEN,
            'modify': Colors.ACCENT_BLUE,
            'fix': QColor("#d29922"),  # Yellow
            'test': QColor("#a5a6ff")  # Purple
        }

        if self.status == 'error':
            return Colors.ACCENT_RED

        return colors.get(self.operation_type, Colors.BORDER_DEFAULT)

    def _get_operation_icon(self):
        """Returns icon character for operation type."""
        icons = {
            'create': '+',
            'modify': '~',
            'fix': '🔧',
            'test': '▶'
        }
        return icons.get(self.operation_type, '?')

    def _draw_processing_indicator(self, painter):
        """Draws an animated processing indicator."""
        # Simple pulsing dot for now - could be enhanced with rotating spinner
        center = QPointF(self.WIDTH - 15, self.HEIGHT / 2)
        painter.setBrush(QBrush(Colors.ACCENT_BLUE))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, 3, 3)

    def animate_to_position(self, target_pos: QPointF, duration: int = 2000):
        """Animates the file to a target position."""
        self.move_animation.setDuration(duration)
        self.move_animation.setStartValue(self.position)
        self.move_animation.setEndValue(target_pos)
        self.move_animation.start()

    def animate_fade_in(self):
        """Fades the item in with a scale effect."""
        self.setOpacity(0)
        self.setScale(0.5)

        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()

        self.scale_animation.setStartValue(0.5)
        self.scale_animation.setEndValue(1.0)
        self.scale_animation.start()

    def animate_fade_out(self):
        """Fades the item out."""
        self.fade_animation.setStartValue(self.opacity)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.start()

    def update_status(self, new_status: str):
        """Updates the file status and refreshes display."""
        self.status = new_status
        self.update()

    def set_filename(self, new_filename: str):
        """Updates the filename and refreshes display."""
        self.filename = new_filename
        self.update()

    # Property implementations for animations
    def get_position(self):
        return self._position

    def set_position(self, pos):
        self._position = pos
        self.setPos(pos)

    position = Property(QPointF, get_position, set_position)

    def get_opacity(self):
        return self._opacity

    def set_opacity(self, opacity):
        self._opacity = opacity
        super().setOpacity(opacity)

    opacity = Property(float, get_opacity, set_opacity)

    def get_scale(self):
        return self._scale

    def set_scale(self, scale):
        self._scale = scale
        self.update()

    scale = Property(float, get_scale, set_scale)