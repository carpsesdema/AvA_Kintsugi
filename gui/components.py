# kintsugi_ava/gui/components.py
# Our Design System. All reusable colors, fonts, and custom widgets live here.

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt # <--- FIX #1: Import Qt

class Colors:
    """
    A modern, professional color palette inspired by tools like GitHub and VS Code.
    This creates a consistent look and feel across the entire application.
    """
    PRIMARY_BG = QColor("#0d1117")
    SECONDARY_BG = QColor("#161b22")
    ELEVATED_BG = QColor("#21262d")
    TEXT_PRIMARY = QColor("#f0f6fc")
    TEXT_SECONDARY = QColor("#8b949e")
    BORDER_DEFAULT = QColor("#30363d")
    ACCENT_BLUE = QColor("#58a6ff")
    ACCENT_GREEN = QColor("#3fb950")

class Typography:
    """A central place for defining font styles."""
    @staticmethod
    def get_font(size=12, weight=QFont.Weight.Normal, family="Segoe UI"):
        return QFont(family, size, weight)

    @staticmethod
    def heading_small():
        return Typography.get_font(12, QFont.Weight.Bold)

    @staticmethod
    def body():
        return Typography.get_font(11, QFont.Weight.Normal)

class ModernButton(QPushButton):
    """A custom-styled button that fits our application's theme."""
    def __init__(self, text="", button_type="primary"):
        super().__init__(text)
        self.setMinimumHeight(32)
        self.setFont(Typography.body())
        self.setCursor(Qt.PointingHandCursor) # <--- FIX #2: Use the correct cursor shape

        bg_color = Colors.ACCENT_BLUE if button_type == "primary" else Colors.ELEVATED_BG
        hover_color = Colors.ACCENT_GREEN if button_type == "primary" else QColor("#30363d")

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                border-radius: 6px;
                padding: 5px 15px;
            }}
            QPushButton:hover {{
                background-color: {hover_color.name()};
                border: 1px solid {Colors.ACCENT_BLUE.name()};
            }}
            QPushButton:pressed {{
                background-color: {Colors.ACCENT_GREEN.name()};
            }}
        """)