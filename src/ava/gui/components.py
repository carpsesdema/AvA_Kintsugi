from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QPushButton, QSlider, QLabel, QHBoxLayout, QWidget
from PySide6.QtCore import Qt, Signal


class Colors:
    """
    A modern, professional color palette inspired by tools like GitHub and VS Code.
    This creates a consistent look and feel across the entire application.
    """
    # --- Professional Dev-Tool Palette ---
    PRIMARY_BG = QColor("#0d1117")  # Near-black, for main backgrounds
    SECONDARY_BG = QColor("#161b22")  # Dark grey, for sidebars and panels
    ELEVATED_BG = QColor("#21262d")  # Lighter grey, for elevated elements like buttons/inputs
    BORDER_DEFAULT = QColor("#30363d")  # Standard border color

    TEXT_PRIMARY = QColor("#f0f6fc")  # Brighter white for better contrast
    TEXT_SECONDARY = QColor("#8b949e")  # Grey, for secondary or muted text

    # --- Accent Colors ---
    ACCENT_BLUE = QColor("#ffa500")  # Swapped blue for a vibrant orange
    ACCENT_GREEN = QColor("#3fb950")  # For success states
    ACCENT_RED = QColor("#f85149")  # For error states
    ACCENT_PURPLE = QColor("#8957e5") # NEW: For Aura creative mode

    # Transparent background for highlighting lines in the editor
    DIFF_ADD_BG = QColor(46, 160, 67, 40)  # More subtle green highlight


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
        # Let's make the hover more subtle for the secondary button
        hover_color = Colors.ACCENT_BLUE.lighter(110) if button_type == "primary" else QColor("#30363d")

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
                border-color: {Colors.ACCENT_BLUE.name()};
            }}
            QPushButton:pressed {{
                background-color: {Colors.ACCENT_GREEN.darker(110).name()};
            }}
        """)


class TemperatureSlider(QWidget):
    """
    A reusable temperature slider widget for AI model configuration.
    Emits valueChanged signal when temperature is adjusted.
    """

    valueChanged = Signal(float)  # Emits the temperature value (0.0 - 2.0)

    def __init__(self, initial_value=0.7, min_temp=0.0, max_temp=2.0):
        super().__init__()
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.precision = 100  # Internal precision for slider (0-200 maps to 0.0-2.0)

        self._setup_ui()
        self.set_temperature(initial_value)

    def _setup_ui(self):
        """Set up the slider UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Temperature label
        self.temp_label = QLabel("Temperature:")
        self.temp_label.setFont(Typography.body())
        self.temp_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")

        # Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(int(self.min_temp * self.precision))
        self.slider.setMaximum(int(self.max_temp * self.precision))
        self.slider.setValue(int(0.7 * self.precision))  # Default to 0.7
        self.slider.setFixedWidth(120)

        # Style the slider
        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                height: 4px;
                background: {Colors.ELEVATED_BG.name()};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {Colors.ACCENT_BLUE.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {Colors.ACCENT_BLUE.lighter(120)};
            }}
            QSlider::sub-page:horizontal {{
                background: {Colors.ACCENT_BLUE.name()};
                border-radius: 2px;
            }}
        """)

        # Value display label
        self.value_label = QLabel("0.70")
        self.value_label.setFont(Typography.body())
        self.value_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()}; min-width: 30px;")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Connect slider to update methods
        self.slider.valueChanged.connect(self._on_slider_changed)

        # Add to layout
        layout.addWidget(self.temp_label)
        layout.addWidget(self.slider)
        layout.addWidget(self.value_label)

    def _on_slider_changed(self, value):
        """Handle slider value changes and emit the temperature value."""
        temperature = value / self.precision
        self.value_label.setText(f"{temperature:.2f}")
        self.valueChanged.emit(temperature)

    def set_temperature(self, temperature):
        """
        Set the temperature value programmatically.

        Args:
            temperature: Float value between min_temp and max_temp
        """
        # Clamp to valid range
        temperature = max(self.min_temp, min(self.max_temp, temperature))

        # Update slider (this will trigger _on_slider_changed)
        slider_value = int(temperature * self.precision)
        self.slider.setValue(slider_value)

    def get_temperature(self):
        """
        Get the current temperature value.

        Returns:
            Float temperature value
        """
        return self.slider.value() / self.precision


class StatusIndicatorDot(QWidget):
    """A simple colored dot to indicate status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self._color = Colors.TEXT_SECONDARY  # Default to grey
        self.setToolTip("Plugin status")

    def setStatus(self, status: str):
        """Sets the color of the dot based on the status string."""
        if status == 'ok':
            self._color = Colors.ACCENT_GREEN
            self.setToolTip("All enabled plugins are running.")
        elif status == 'error':
            self._color = Colors.ACCENT_RED
            self.setToolTip("One or more enabled plugins are not running or in an error state.")
        else:  # 'off' or any other state
            self._color = Colors.TEXT_SECONDARY
            self.setToolTip("No plugins are enabled.")
        self.update()  # Trigger a repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        painter.drawEllipse(0, 0, self.width(), self.height())