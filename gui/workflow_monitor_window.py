# kintsugi_ava/gui/workflow_monitor_window.py
# V2: Now with a real graphics scene to display the workflow.

from PySide6.QtWidgets import QMainWindow, QGraphicsView
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPainter

from .components import Colors
from .workflow_monitor_scene import WorkflowMonitorScene


class WorkflowMonitorWindow(QMainWindow):
    """
    A window that contains the visual graph of the AI agents and their status.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kintsugi AvA - Workflow Monitor")
        self.setGeometry(200, 200, 360, 500)
        self.setStyleSheet(f"background-color: {Colors.PRIMARY_BG.name()};")

        self.scene = WorkflowMonitorScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setCentralWidget(self.view)

    @Slot(str, str, str)
    def update_node_status(self, agent_id: str, status: str, status_text: str):
        """Public slot to update a node's visual status."""
        self.scene.update_node_status(agent_id, status, status_text)