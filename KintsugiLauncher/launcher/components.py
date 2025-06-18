# launcher/components.py

from PySide6.QtGui import QColor, QFont

class Colors:
    """A modern, professional color palette."""
    PRIMARY_BG = QColor("#0d1117")
    SECONDARY_BG = QColor("#161b22")
    ELEVATED_BG = QColor("#21262d")
    TEXT_PRIMARY = QColor("#f0f6fc")
    TEXT_SECONDARY = QColor("#8b949e")
    BORDER_DEFAULT = QColor("#30363d")
    ACCENT_BLUE = QColor("#58a6ff")
    ACCENT_GREEN = QColor("#3fb950")
    ACCENT_RED = QColor("#f85149")

class Typography:
    """A central place for defining font styles."""

    @staticmethod
    def get_font(size=12, weight=QFont.Weight.Normal, family="Segoe UI"):
        return QFont(family, size, weight)

    @staticmethod
    def heading(size: int):
        return Typography.get_font(size, QFont.Weight.Bold)

    @staticmethod
    def body(size: int):
        return Typography.get_font(size, QFont.Weight.Normal)