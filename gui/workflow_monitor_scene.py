# kintsugi_ava/gui/workflow_monitor_scene.py
# V3: Enhanced workflow scene with file flow visualization and modern layout

from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtGui import QColor, QPen, QPainter
from PySide6.QtCore import QPointF, Slot, QTimer, Qt

from .agent_node import AgentNode
from .components import Colors

# Import the flow animation manager - will be created as new file
try:
    from .flow_animation_manager import FlowAnimationManager

    ENHANCED_FEATURES_AVAILABLE = True
except ImportError:
    ENHANCED_FEATURES_AVAILABLE = False
    print("[WorkflowMonitorScene] Enhanced features not available - flow animation manager not found")


class WorkflowMonitorScene(QGraphicsScene):
    """
    Enhanced workflow visualization scene that shows AI agents and file flows.
    Features a modern horizontal pipeline layout with feedback loops.
    Maintains backward compatibility with existing functionality.
    """

    def __init__(self):
        super().__init__()
        self.setBackgroundBrush(QColor(Colors.PRIMARY_BG))

        # Node tracking
        self._nodes = {}
        self._node_positions = {}

        # Enhanced features (if available)
        if ENHANCED_FEATURES_AVAILABLE:
            # File flow management
            self.flow_manager = FlowAnimationManager(self)
            self.flow_manager.file_reached_node.connect(self._on_file_reached_node)

            # Current workflow state
            self.current_files = []
            self.active_workflow = None
        else:
            self.flow_manager = None
            self.current_files = []

        self.setup_enhanced_layout()

    def setup_enhanced_layout(self):
        """Creates the enhanced pipeline layout with file flow support."""
        self.clear()
        self._nodes.clear()
        self._node_positions.clear()

        # Enhanced node definitions with better positioning
        node_definitions = {
            "architect": {
                "name": "Architect",
                "icon": "🏛️",
                "pos": (50, 100),
                "description": "Plans & Designs"
            },
            "coder": {
                "name": "Coder",
                "icon": "⚙️",
                "pos": (250, 100),
                "description": "Generates Code"
            },
            "executor": {
                "name": "Executor",
                "icon": "🚀",
                "pos": (450, 100),
                "description": "Tests & Validates"
            },
            "reviewer": {
                "name": "Reviewer",
                "icon": "🧐",
                "pos": (350, 250),
                "description": "Fixes & Refines"
            }
        }

        # Create and position nodes
        for agent_id, details in node_definitions.items():
            node = AgentNode(agent_id, details["name"], details["icon"])
            pos = QPointF(*details["pos"])
            node.setPos(pos)

            self.addItem(node)
            self._nodes[agent_id] = node
            self._node_positions[agent_id] = pos

        # Update flow manager with node positions (if available)
        if self.flow_manager:
            self.flow_manager.set_node_positions(self._node_positions)

        # Draw connection paths
        self._draw_workflow_connections()

        # Set scene rectangle to encompass all elements
        self.setSceneRect(-20, -20, 600, 350)

    def _draw_workflow_connections(self):
        """Draws the connecting lines between workflow nodes."""
        connections = [
            ("architect", "coder"),
            ("coder", "executor"),
            ("executor", "reviewer"),  # Feedback loop
            ("reviewer", "executor")  # Return path
        ]

        for from_node, to_node in connections:
            self._draw_connection_line(from_node, to_node)

    def _draw_connection_line(self, from_node: str, to_node: str):
        """Draws a connection line between two nodes."""
        if from_node not in self._node_positions or to_node not in self._node_positions:
            return

        from_pos = self._node_positions[from_node]
        to_pos = self._node_positions[to_node]

        # Calculate connection points (edge of nodes, not center)
        if from_node == "executor" and to_node == "reviewer":
            # Feedback loop - curved line going down
            start_point = QPointF(from_pos.x() + 80, from_pos.y() + 60)
            end_point = QPointF(to_pos.x() + 80, to_pos.y())

            # Create curved path for feedback
            if self.flow_manager:
                path = self.flow_manager.get_connection_path(from_node, to_node)
                pen = QPen(Colors.BORDER_DEFAULT, 2)
                pen.setStyle(Qt.PenStyle.DashLine)  # Fixed: Use Qt.PenStyle enum
                self.addPath(path, pen)
            else:
                # Fallback simple line
                pen = QPen(Colors.BORDER_DEFAULT, 2)
                pen.setStyle(Qt.PenStyle.DashLine)  # Fixed: Use Qt.PenStyle enum
                self.addLine(start_point.x(), start_point.y(), end_point.x(), end_point.y(), pen)

        elif from_node == "reviewer" and to_node == "executor":
            # Return path - lighter dashed line
            pen = QPen(QColor(Colors.BORDER_DEFAULT.red(), Colors.BORDER_DEFAULT.green(),
                              Colors.BORDER_DEFAULT.blue(), 100), 1)
            pen.setStyle(Qt.PenStyle.DashLine)  # Fixed: Use Qt.PenStyle enum

            start_point = QPointF(to_pos.x() + 80, to_pos.y() + 40)
            end_point = QPointF(from_pos.x() + 80, from_pos.y() + 20)
            self.addLine(start_point.x(), start_point.y(), end_point.x(), end_point.y(), pen)

        else:
            # Standard horizontal connections
            start_point = QPointF(from_pos.x() + 160, from_pos.y() + 40)
            end_point = QPointF(to_pos.x(), to_pos.y() + 40)

            pen = QPen(Colors.BORDER_DEFAULT, 2)
            self.addLine(start_point.x(), start_point.y(), end_point.x(), end_point.y(), pen)

            # Add arrow head
            self._draw_arrow_head(end_point, 0)  # 0 degrees for horizontal

    def _draw_arrow_head(self, pos: QPointF, angle: float):
        """Draws a small arrow head at the specified position."""
        # Simple triangle arrow head
        arrow_size = 8
        pen = QPen(Colors.BORDER_DEFAULT, 2)

        # Calculate arrow points (simplified for horizontal arrows)
        p1 = QPointF(pos.x() - arrow_size, pos.y() - arrow_size / 2)
        p2 = QPointF(pos.x() - arrow_size, pos.y() + arrow_size / 2)

        self.addLine(pos.x(), pos.y(), p1.x(), p1.y(), pen)
        self.addLine(pos.x(), pos.y(), p2.x(), p2.y(), pen)

    @Slot(str, str, str)
    def update_node_status(self, agent_id: str, status: str, status_text: str):
        """Updates a node's visual status (existing functionality)."""
        if agent_id in self._nodes:
            self._nodes[agent_id].set_status(status, status_text)

    # === ENHANCED FILE FLOW EVENT HANDLERS ===

    def start_new_project_flow(self, filenames: list):
        """Initiates file flow visualization for new project generation."""
        if not self.flow_manager:
            print("[WorkflowMonitorScene] Enhanced features not available - using basic visualization")
            return

        self.flow_manager.clear_all_files()

        # Create files at architect
        file_ids = self.flow_manager.create_batch_flow(filenames, 'create', 'architect')
        self.current_files = file_ids

        # Move to coder after brief delay
        self.flow_manager.move_batch_to_node(file_ids, 'coder', stagger_delay=400)

    def start_modification_flow(self, filenames: list):
        """Initiates file flow visualization for project modifications."""
        if not self.flow_manager:
            print("[WorkflowMonitorScene] Enhanced features not available - using basic visualization")
            return

        self.flow_manager.clear_all_files()

        # Create files at architect
        file_ids = self.flow_manager.create_batch_flow(filenames, 'modify', 'architect')
        self.current_files = file_ids

        # Move to coder
        self.flow_manager.move_batch_to_node(file_ids, 'coder', stagger_delay=300)

    def move_files_to_executor(self):
        """Moves current files from coder to executor for testing."""
        if not self.flow_manager or not self.current_files:
            return

        self.flow_manager.move_batch_to_node(self.current_files, 'executor', stagger_delay=200)

    def move_files_to_reviewer(self, failed_files: list = None):
        """Moves failed files to reviewer for fixing."""
        if not self.flow_manager:
            return

        files_to_move = failed_files if failed_files else self.current_files
        if files_to_move:
            # Update files to show they need fixing
            for file_id in files_to_move:
                self.flow_manager.update_file_status(file_id, 'error')

            # Move to reviewer
            self.flow_manager.move_batch_to_node(files_to_move, 'reviewer', stagger_delay=100)

    def return_files_from_reviewer(self, fixed_files: list = None):
        """Returns fixed files from reviewer back to executor."""
        if not self.flow_manager:
            return

        files_to_move = fixed_files if fixed_files else self.current_files
        if files_to_move:
            # Update operation type to show they're fixes
            for file_id in files_to_move:
                if file_id in self.flow_manager.active_files:
                    self.flow_manager.active_files[file_id].operation_type = 'fix'
                    self.flow_manager.update_file_status(file_id, 'processing')

            # Move back to executor
            self.flow_manager.move_batch_to_node(files_to_move, 'executor', stagger_delay=150)

    def complete_workflow(self):
        """Marks the workflow as complete and cleans up files."""
        if not self.flow_manager or not self.current_files:
            return

        for file_id in self.current_files:
            self.flow_manager.update_file_status(file_id, 'complete')

        # Remove files after a delay to show completion
        for i, file_id in enumerate(self.current_files):
            delay = (i + 1) * 500 + 2000  # Staggered removal after 2 seconds
            QTimer.singleShot(delay, lambda fid=file_id: self.flow_manager.remove_file(fid))

        self.current_files = []

    def handle_file_streaming(self, filename: str):
        """Shows real-time file generation with streaming effect."""
        if not self.flow_manager:
            return

        # Find the file being streamed and update its status
        for file_id, file_item in self.flow_manager.active_files.items():
            if file_item.filename == filename:
                file_item.update_status('processing')
                break

    @Slot(str, str, str)
    def _on_file_reached_node(self, file_id: str, node_id: str, operation: str):
        """Handles file reaching a workflow node."""
        # This can be used for additional logic when files reach specific nodes
        print(f"[WorkflowScene] File {file_id} reached {node_id} for {operation}")

    def get_workflow_statistics(self) -> dict:
        """Returns current workflow statistics for debugging/monitoring."""
        if not self.flow_manager:
            return {
                'active_files': 0,
                'files_at_architect': 0,
                'files_at_coder': 0,
                'files_at_executor': 0,
                'files_at_reviewer': 0,
            }

        return {
            'active_files': self.flow_manager.get_active_file_count(),
            'files_at_architect': len(self.flow_manager.get_files_at_node('architect')),
            'files_at_coder': len(self.flow_manager.get_files_at_node('coder')),
            'files_at_executor': len(self.flow_manager.get_files_at_node('executor')),
            'files_at_reviewer': len(self.flow_manager.get_files_at_node('reviewer')),
        }