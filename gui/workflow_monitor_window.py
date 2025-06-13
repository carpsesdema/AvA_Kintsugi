# kintsugi_ava/gui/workflow_monitor_window.py
# Placeholder for the visual AI workflow monitor.

from PySide6.QtWidgets import QMainWindow, QLabel
from PySide6.QtCore import Qt

from .components import Colors, Typography

class WorkflowMonitorWindow(QMainWindow):
    """
    A placeholder window that will eventually contain the visual graph
    of the AI agents and their status.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kintsugi AvA - Workflow Monitor")
        self.setGeometry(200, 200, 800, 600)
        self.setStyleSheet(f"background-color: {Colors.PRIMARY_BG.name()};")

        placeholder_label = QLabel("Workflow Monitor Placeholder")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setFont(Typography.get_font(24))
        placeholder_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")

        self.setCentralWidget(placeholder_label)