# kintsugi_ava/gui/workflow_monitor_scene.py
# V4: Simplified animations to support the co-pilot workflow.

from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtGui import QColor, QPen, QPainter
from PySide6.QtCore import QPointF, Slot, QTimer, Qt

from .agent_node import AgentNode
from .components import Colors

try:
    from .flow_animation_manager import FlowAnimationManager

    ENHANCED_FEATURES_AVAILABLE = True
except ImportError:
    ENHANCED_FEATURES_AVAILABLE = False
    print("[WorkflowMonitorScene] Enhanced features not available - flow animation manager not found")


class WorkflowMonitorScene(QGraphicsScene):
    """
    Enhanced workflow visualization scene that shows AI agents and file flows,
    now simplified to reflect the user-driven co-pilot workflow.
    """

    def __init__(self):
        super().__init__()
        self.setBackgroundBrush(QColor(Colors.PRIMARY_BG))

        self._nodes = {}
        self._node_positions = {}

        if ENHANCED_FEATURES_AVAILABLE:
            self.flow_manager = FlowAnimationManager(self)
        else:
            self.flow_manager = None

        self.current_files = []
        self.setup_enhanced_layout()

    def setup_enhanced_layout(self):
        """Creates the enhanced pipeline layout."""
        self.clear()
        self._nodes.clear()
        self._node_positions.clear()

        node_definitions = {
            "architect": {"name": "Architect", "icon": "🏛️", "pos": (50, 100)},
            "coder": {"name": "Coder", "icon": "⚙️", "pos": (250, 100)},
            "executor": {"name": "Executor", "icon": "🚀", "pos": (450, 100)},
            "reviewer": {"name": "Reviewer", "icon": "🧐", "pos": (350, 250)}
        }

        for agent_id, details in node_definitions.items():
            node = AgentNode(agent_id, details["name"], details["icon"])
            pos = QPointF(*details["pos"])
            node.setPos(pos)
            self.addItem(node)
            self._nodes[agent_id] = node
            self._node_positions[agent_id] = pos

        if self.flow_manager:
            self.flow_manager.set_node_positions(self._node_positions)

        self._draw_workflow_connections()
        self.setSceneRect(-20, -20, 600, 350)

    def _draw_workflow_connections(self):
        """Draws the connecting lines between workflow nodes."""
        connections = [
            ("architect", "coder"),
            ("coder", "executor"),
            ("executor", "reviewer"),
            ("reviewer", "executor")
        ]
        pen = QPen(Colors.BORDER_DEFAULT, 2)
        pen.setStyle(Qt.PenStyle.DashLine)

        for from_node, to_node in connections:
            if from_node in self._node_positions and to_node in self._node_positions:
                start_point = self._node_positions[from_node] + QPointF(160, 40)
                end_point = self._node_positions[to_node] + QPointF(0, 40)
                if from_node == "executor":  # Special case for feedback loop
                    start_point = self._node_positions[from_node] + QPointF(80, 80)
                    end_point = self._node_positions[to_node] + QPointF(80, 0)
                elif from_node == "reviewer":  # Return path
                    start_point = self._node_positions[from_node] + QPointF(80, 0)
                    end_point = self._node_positions[to_node] + QPointF(80, 80)

                self.addLine(start_point.x(), start_point.y(), end_point.x(), end_point.y(), pen)

    @Slot(str, str, str)
    def update_node_status(self, agent_id: str, status: str, status_text: str):
        """Updates a node's visual status."""
        if agent_id in self._nodes:
            self._nodes[agent_id].set_status(status, status_text)

    # === New Co-pilot Workflow Methods ===

    def start_new_project_flow(self, filenames: list):
        """Initiates file flow visualization for new project generation."""
        if not self.flow_manager:
            return

        self.flow_manager.clear_all_files()
        file_ids = self.flow_manager.create_batch_flow(filenames, 'create', 'architect')
        self.current_files = file_ids

        # In the new model, files "rest" at the architect/coder stage until the user acts.
        # We no longer automatically move them.
        # self.flow_manager.move_batch_to_node(file_ids, 'coder', stagger_delay=400)

    def start_modification_flow(self, filenames: list):
        """Initiates file flow visualization for project modifications."""
        if not self.flow_manager:
            return

        self.flow_manager.clear_all_files()
        file_ids = self.flow_manager.create_batch_flow(filenames, 'modify', 'architect')
        self.current_files = file_ids

    def handle_file_streaming(self, filename: str):
        """Shows real-time file generation with streaming effect."""
        if not self.flow_manager:
            return

        # Activate the coder node when streaming starts
        self.update_node_status("coder", "working", "Generating code...")

        for file_id, file_item in self.flow_manager.active_files.items():
            if file_item.filename == filename:
                file_item.update_status('processing')
                break