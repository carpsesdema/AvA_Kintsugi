# src/ava/gui/loading_indicator.py
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtWidgets import QWidget

class LoadingIndicator(QWidget):
    """
    Creates a smooth, spinning and pulsing animation using a QTimer for manual
    updates. This approach is highly robust and avoids potential framework
    issues with QPropertyAnimation, ensuring it works for launch.
    """

    def __init__(self, project_root: Path, parent=None):
        super().__init__(parent)
        self.project_root = project_root # Store project_root

        # --- Image Filenames ---
        self.base_image_name = "loading_gear_base.png"
        self.glow_image_name = "loading_gear_glow.png"

        # --- Animation State ---
        self._rotation_angle = 0.0
        self._glow_opacity = 0.0
        self._pulse_direction = 1  # 1 for increasing, -1 for decreasing

        self.pixmap_base = None
        self.pixmap_glow = None

        self._load_pixmaps()

        # --- Animation Timer ---
        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(16)  # ~60 FPS
        self.animation_timer.timeout.connect(self._update_animation_frame)

        self.start()

    def _load_pixmaps(self):
        """Finds and loads the two gear images into QPixmap objects."""
        try:
            # --- THIS IS THE FIX ---
            # Use the passed 'project_root' to determine the asset directory.
            # This 'project_root' is intelligently set by main.py.
            asset_dir = self.project_root / "ava" / "assets"
            # --- END OF FIX ---

            base_image_path = asset_dir / self.base_image_name
            glow_image_path = asset_dir / self.glow_image_name

            if not base_image_path.exists() or not glow_image_path.exists():
                print(f"ERROR: Loading indicator images not found in {asset_dir}")
                return

            self.pixmap_base = QPixmap(str(base_image_path))
            self.pixmap_glow = QPixmap(str(glow_image_path))

        except Exception as e:
            print(f"Failed to load loading indicator images: {e}")

    def _update_animation_frame(self):
        """Calculates the state of the animation for the current frame."""
        # --- Rotation ---
        # Rotate by a small amount each frame. The modulo keeps it from growing infinitely.
        self._rotation_angle = (self._rotation_angle + 1.5) % 360

        # --- Pulsing Glow ---
        # The step determines how fast the pulse is.
        pulse_step = 0.015
        if self._pulse_direction == 1:
            self._glow_opacity += pulse_step
            if self._glow_opacity >= 1.0:
                self._glow_opacity = 1.0
                self._pulse_direction = -1  # Reverse direction
        else:
            self._glow_opacity -= pulse_step
            if self._glow_opacity <= 0.0:
                self._glow_opacity = 0.0
                self._pulse_direction = 1  # Reverse direction

        # Trigger a repaint of the widget
        self.update()

    def paintEvent(self, event):
        """Draws the base and glow layers, applying rotation and opacity."""
        if not self.pixmap_base or not self.pixmap_glow:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Scale pixmaps to fit the widget's current size while keeping aspect ratio
        scaled_base = self.pixmap_base.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)
        scaled_glow = self.pixmap_glow.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)

        # --- Draw the spinning base gear ---
        painter.save()
        center = self.rect().center()
        painter.translate(center)
        painter.rotate(self._rotation_angle)
        painter.translate(-center)
        # Center the pixmap within the widget rect before drawing
        base_rect = scaled_base.rect()
        base_rect.moveCenter(self.rect().center())
        painter.drawPixmap(base_rect.topLeft(), scaled_base)
        painter.restore()

        # --- Draw the pulsing glow layer on top ---
        painter.setOpacity(self._glow_opacity)
        glow_rect = scaled_glow.rect()
        glow_rect.moveCenter(self.rect().center())
        painter.drawPixmap(glow_rect.topLeft(), scaled_glow)

    def start(self):
        if not self.animation_timer.isActive():
            self.animation_timer.start()

    def stop(self):
        self.animation_timer.stop()

    def hideEvent(self, event):
        self.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        self.start()
        super().showEvent(event)