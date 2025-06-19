# src/ava/gui/loading_indicator.py
# FINAL VERSION: A beautiful, smooth, pulsing animation using QPropertyAnimation.

from pathlib import Path
import sys

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property, QParallelAnimationGroup
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtWidgets import QWidget


class LoadingIndicator(QWidget):
    """
    Creates a smooth, spinning and pulsing animation by rotating a 'base'
    image and fading the opacity of a 'glow' image over it. This is achieved
    using Qt's animation framework.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- Image Filenames (MUST be in src/ava/assets/) ---
        self.base_image_name = "loading_gear_base.png"
        self.glow_image_name = "loading_gear_glow.png"

        # --- Animation State ---
        self._glow_opacity = 0.0
        self._rotation_angle = 0.0
        self.pixmap_base = None
        self.pixmap_glow = None
        self.animation_group = None

        self._load_pixmaps()
        self._setup_animation()
        self.start()

    def _load_pixmaps(self):
        """Finds and loads the two gear images into QPixmap objects."""
        try:
            if getattr(sys, 'frozen', False):
                asset_dir = Path(sys._MEIPASS) / "ava" / "assets"
            else:
                asset_dir = Path(__file__).resolve().parent.parent / "assets"

            base_image_path = asset_dir / self.base_image_name
            glow_image_path = asset_dir / self.glow_image_name

            if not base_image_path.exists() or not glow_image_path.exists():
                print(f"ERROR: Loading indicator images not found in {asset_dir}")
                return

            self.pixmap_base = QPixmap(str(base_image_path))
            self.pixmap_glow = QPixmap(str(glow_image_path))

        except Exception as e:
            print(f"Failed to load loading indicator images: {e}")

    @Property(float)
    def glow_opacity(self):
        return self._glow_opacity

    @glow_opacity.setter
    def set_glow_opacity(self, value):
        self._glow_opacity = value
        self.update()

    @Property(float)
    def rotation_angle(self):
        return self._rotation_angle

    @rotation_angle.setter
    def set_rotation_angle(self, value):
        self._rotation_angle = value
        self.update()

    def _setup_animation(self):
        """Sets up the infinitely looping fade-in/out and rotation animations."""
        if not self.pixmap_base:
            return

        self.animation_group = QParallelAnimationGroup(self)

        # Pulse animation (fading the glow)
        pulse_animation = QPropertyAnimation(self, b"glow_opacity")
        pulse_animation.setDuration(1800)
        pulse_animation.setStartValue(0.0)
        pulse_animation.setKeyValueAt(0.5, 1.0)
        pulse_animation.setEndValue(0.0)
        pulse_animation.setLoopCount(-1)
        pulse_animation.setEasingCurve(QEasingCurve.InOutSine)

        # Rotation animation
        rotation_animation = QPropertyAnimation(self, b"rotation_angle")
        rotation_animation.setDuration(2500)
        rotation_animation.setStartValue(0)
        rotation_animation.setEndValue(360)
        rotation_animation.setLoopCount(-1)
        rotation_animation.setEasingCurve(QEasingCurve.Type.Linear)

        self.animation_group.addAnimation(pulse_animation)
        self.animation_group.addAnimation(rotation_animation)

    def paintEvent(self, event):
        """Draws the base and glow layers, applying rotation to the base."""
        if not self.pixmap_base or not self.pixmap_glow:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        scaled_base = self.pixmap_base.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)
        scaled_glow = self.pixmap_glow.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)

        # Apply rotation to the base gear
        center = self.rect().center()
        painter.save()
        painter.translate(center)
        painter.rotate(self._rotation_angle)
        painter.translate(-center)
        painter.drawPixmap(self.rect(), scaled_base)
        painter.restore()

        # Draw the glow layer on top, with opacity but no rotation
        painter.setOpacity(self._glow_opacity)
        painter.drawPixmap(self.rect(), scaled_glow)

    def start(self):
        if self.animation_group and self.animation_group.state() != QPropertyAnimation.State.Running:
            self.animation_group.start()

    def stop(self):
        if self.animation_group:
            self.animation_group.stop()

    def hideEvent(self, event):
        self.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        self.start()
        super().showEvent(event)