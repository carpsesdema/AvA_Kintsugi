# src/ava/gui/loading_indicator.py
# FINAL VERSION: A beautiful, smooth, pulsing animation using QPropertyAnimation.

from pathlib import Path
import sys

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtWidgets import QWidget


class LoadingIndicator(QWidget):
    """
    Creates a smooth, pulsing animation by fading the opacity of a 'glow'
    image over a 'base' image. This is achieved using Qt's animation framework.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- Image Filenames (MUST be in src/ava/assets/) ---
        self.base_image_name = "loading_gear_base.png"
        self.glow_image_name = "loading_gear_glow.png"

        # --- Animation State ---
        self._glow_opacity = 0.0
        self.pixmap_base = None
        self.pixmap_glow = None
        self.animation = None

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

    def _setup_animation(self):
        """Sets up the infinitely looping fade-in and fade-out animation."""
        if not self.pixmap_base:
            return

        self.animation = QPropertyAnimation(self, b"glow_opacity")
        self.animation.setDuration(1800)
        self.animation.setStartValue(0.0)
        self.animation.setKeyValueAt(0.5, 1.0)
        self.animation.setEndValue(0.0)
        self.animation.setLoopCount(-1)
        self.animation.setEasingCurve(QEasingCurve.InOutSine)

    def paintEvent(self, event):
        """Draws the base and glow layers."""
        if not self.pixmap_base or not self.pixmap_glow:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Scale pixmaps to fit the widget's current size
        scaled_base = self.pixmap_base.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)
        scaled_glow = self.pixmap_glow.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)

        painter.drawPixmap(self.rect(), scaled_base)
        painter.setOpacity(self._glow_opacity)
        painter.drawPixmap(self.rect(), scaled_glow)

    def start(self):
        if self.animation and self.animation.state() != QPropertyAnimation.State.Running:
            self.animation.start()

    def stop(self):
        if self.animation:
            self.animation.stop()

    def hideEvent(self, event):
        self.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        self.start()
        super().showEvent(event)