# kintsugi_ava/gui/components.py
# Our Design System. All reusable colors, fonts, and custom widgets live here.

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt

class Colors:
    """
    A modern, professional color palette inspired by tools like GitHub and VS Code.
    This creates a consistent look and feel across the entire application.
    """
    # Backgrounds
    PRIMARY_BG = QColor("#0d1117")      # Near-black, for main backgrounds
    SECONDARY_BG = QColor("#161b22")    # Dark grey, for sidebars and panels
    ELEVATED_BG = QColor("#21262d")     # Lighter grey, for elevated elements like buttons

    # Text
    TEXT_PRIMARY = QColor("#f0f6fc")     # Off-white, for primary text
    TEXT_SECONDARY = QColor("#8b949e")   # Grey, for secondary or muted text

    # Borders
    BORDER_DEFAULT = QColor("#30363d")   # Standard border color

    # Accents
    ACCENT_BLUE = QColor("#58a6ff")      # For primary actions and highlights
    ACCENT_GREEN = QColor("#3fb950")     # For success states
    ACCENT_RED = QColor("#f85149")       # <-- THE FIX: For error states

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
        self.setCursor(Qt.PointingHandCursor)

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