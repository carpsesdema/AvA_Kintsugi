# kintsugi_ava/gui/workflow_monitor_scene.py
# V2: Adds the Reviewer node to the scene layout.

from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtGui import QColor

from .agent_node import AgentNode
from .components import Colors


class WorkflowMonitorScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.setBackgroundBrush(QColor(Colors.PRIMARY_BG))
        self._nodes = {}
        self.setup_layout()

    def setup_layout(self):
        """Creates and positions the nodes for our self-correcting workflow."""
        self.clear()
        self._nodes.clear()

        # Define nodes and their positions
        node_definitions = {
            "architect": {"name": "Architect", "icon": "🏛️", "pos": (100, 50)},
            "coder": {"name": "Coder", "icon": "⚙️", "pos": (100, 150)},
            "executor": {"name": "Executor", "icon": "🚀", "pos": (100, 250)},
            "reviewer": {"name": "Reviewer", "icon": "🧐", "pos": (100, 350)},  # New node
        }

        for agent_id, details in node_definitions.items():
            node = AgentNode(agent_id, details["name"], details["icon"])
            node.setPos(*details["pos"])
            self.addItem(node)
            self._nodes[agent_id] = node

    def update_node_status(self, agent_id: str, status: str, status_text: str):
        if agent_id in self._nodes:
            self._nodes[agent_id].set_status(status, status_text)