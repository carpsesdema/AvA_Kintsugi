# kintsugi_ava/gui/flow_animation_manager.py
# Manages file flow animations and movement between workflow nodes

import uuid
from typing import Dict, List, Tuple, Optional
from PySide6.QtCore import QObject, QTimer, QPointF, Signal, Qt
from PySide6.QtGui import QPainterPath, QTransform
from PySide6.QtWidgets import QGraphicsScene

from .file_flow_item import FileFlowItem


class FlowAnimationManager(QObject):
    """
    Manages the creation, movement, and lifecycle of file flow items
    in the workflow visualization. Handles path calculation and timing.
    """

    file_reached_node = Signal(str, str, str)  # file_id, node_id, operation

    def __init__(self, scene: QGraphicsScene):
        super().__init__()
        self.scene = scene
        self.active_files: Dict[str, FileFlowItem] = {}
        self.node_positions: Dict[str, QPointF] = {}
        self.animation_queue: List[Tuple] = []
        self.processing_queue = False

        # Timer for staggered animations
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self._process_animation_queue)
        self.queue_timer.setSingleShot(False)

    def set_node_positions(self, positions: Dict[str, QPointF]):
        """Updates the positions of workflow nodes for path calculation."""
        self.node_positions = positions

    def create_file_flow(self, filename: str, operation_type: str, start_node: str) -> str:
        """
        Creates a new file flow item and places it at the starting node.

        Returns:
            The unique file_id for tracking this file through the workflow.
        """
        file_id = str(uuid.uuid4())[:8]  # Short unique ID

        file_item = FileFlowItem(file_id, filename, operation_type)

        # Position at the starting node
        if start_node in self.node_positions:
            start_pos = self.node_positions[start_node]
            # Offset slightly to avoid overlap with node
            file_pos = QPointF(start_pos.x() + 180, start_pos.y() + 10)
            file_item.setPos(file_pos)

        # Connect animation completion signal
        file_item.animation_finished.connect(self._on_file_animation_finished)

        # Add to scene and tracking
        self.scene.addItem(file_item)
        self.active_files[file_id] = file_item

        # Animate fade in
        file_item.animate_fade_in()

        return file_id

    def move_file_to_node(self, file_id: str, target_node: str, delay_ms: int = 0):
        """
        Moves a file to the specified node with optional delay.
        Adds to animation queue to handle timing.
        """
        if file_id not in self.active_files:
            print(f"[FlowAnimationManager] Warning: File {file_id} not found for movement")
            return

        if target_node not in self.node_positions:
            print(f"[FlowAnimationManager] Warning: Target node {target_node} position not known")
            return

        # Add to animation queue
        self.animation_queue.append((file_id, target_node, delay_ms))

        # Start processing queue if not already running
        if not self.processing_queue:
            self._process_animation_queue()

    def update_file_status(self, file_id: str, status: str):
        """Updates the visual status of a file."""
        if file_id in self.active_files:
            self.active_files[file_id].update_status(status)

    def remove_file(self, file_id: str, fade_out: bool = True):
        """Removes a file from the visualization."""
        if file_id not in self.active_files:
            return

        file_item = self.active_files[file_id]

        if fade_out:
            file_item.animate_fade_out()
            # Remove after fade animation completes
            QTimer.singleShot(500, lambda: self._cleanup_file(file_id))
        else:
            self._cleanup_file(file_id)

    def create_batch_flow(self, filenames: List[str], operation_type: str, start_node: str) -> List[str]:
        """
        Creates multiple file flows with staggered timing for visual appeal.

        Returns:
            List of file_ids for the created files.
        """
        file_ids = []

        for i, filename in enumerate(filenames):
            file_id = self.create_file_flow(filename, operation_type, start_node)
            file_ids.append(file_id)

            # Stagger the creation slightly for visual effect
            if i > 0:
                QTimer.singleShot(i * 200, lambda fid=file_id: self._stagger_file_appearance(fid))

        return file_ids

    def move_batch_to_node(self, file_ids: List[str], target_node: str, stagger_delay: int = 300):
        """
        Moves multiple files to a node with staggered timing.
        """
        for i, file_id in enumerate(file_ids):
            delay = i * stagger_delay
            self.move_file_to_node(file_id, target_node, delay)

    def get_connection_path(self, from_node: str, to_node: str) -> QPainterPath:
        """
        Calculates a smooth bezier curve path between two nodes.
        Used for drawing connection lines and file movement paths.
        """
        if from_node not in self.node_positions or to_node not in self.node_positions:
            return QPainterPath()

        start_pos = self.node_positions[from_node]
        end_pos = self.node_positions[to_node]

        path = QPainterPath()
        path.moveTo(start_pos)

        # Calculate control points for smooth curve
        distance = abs(end_pos.x() - start_pos.x())
        control_offset = min(distance * 0.5, 100)

        if from_node == "executor" and to_node == "reviewer":
            # Special curved path for feedback loop
            control1 = QPointF(start_pos.x() + control_offset, start_pos.y() + 80)
            control2 = QPointF(end_pos.x() - control_offset, end_pos.y() + 80)
        else:
            # Standard horizontal flow
            control1 = QPointF(start_pos.x() + control_offset, start_pos.y())
            control2 = QPointF(end_pos.x() - control_offset, end_pos.y())

        path.cubicTo(control1, control2, end_pos)
        return path

    def _process_animation_queue(self):
        """Processes the animation queue with proper timing."""
        if not self.animation_queue:
            self.processing_queue = False
            self.queue_timer.stop()
            return

        self.processing_queue = True

        # Get next animation from queue
        file_id, target_node, delay_ms = self.animation_queue.pop(0)

        if file_id not in self.active_files:
            # Continue with next item
            QTimer.singleShot(100, self._process_animation_queue)
            return

        def execute_movement():
            if file_id in self.active_files:
                file_item = self.active_files[file_id]
                target_pos = self.node_positions[target_node]

                # Calculate offset position near the target node
                offset_pos = QPointF(target_pos.x() + 180, target_pos.y() + 10)

                # Update status to show movement
                file_item.update_status('processing')

                # Start the animation
                file_item.animate_to_position(offset_pos)

            # Continue processing queue
            QTimer.singleShot(100, self._process_animation_queue)

        # Execute after delay
        if delay_ms > 0:
            QTimer.singleShot(delay_ms, execute_movement)
        else:
            execute_movement()

    def _stagger_file_appearance(self, file_id: str):
        """Helper for staggered file appearance in batch operations."""
        if file_id in self.active_files:
            self.active_files[file_id].animate_fade_in()

    def _on_file_animation_finished(self, file_id: str):
        """Handles file animation completion."""
        if file_id in self.active_files:
            file_item = self.active_files[file_id]
            file_item.update_status('complete')

            # Emit signal for workflow coordination
            self.file_reached_node.emit(file_id, "target", file_item.operation_type)

    def _cleanup_file(self, file_id: str):
        """Removes file from scene and tracking."""
        if file_id in self.active_files:
            file_item = self.active_files[file_id]
            self.scene.removeItem(file_item)
            del self.active_files[file_id]

    def clear_all_files(self):
        """Removes all active file flows."""
        for file_id in list(self.active_files.keys()):
            self.remove_file(file_id, fade_out=False)

    def get_active_file_count(self) -> int:
        """Returns the number of active file flows."""
        return len(self.active_files)

    def get_files_at_node(self, node_id: str) -> List[str]:
        """Returns list of file_ids currently at the specified node."""
        files_at_node = []
        if node_id not in self.node_positions:
            return files_at_node

        node_pos = self.node_positions[node_id]

        for file_id, file_item in self.active_files.items():
            file_pos = file_item.pos()
            # Check if file is near the node (within reasonable distance)
            distance = ((file_pos.x() - node_pos.x()) ** 2 + (file_pos.y() - node_pos.y()) ** 2) ** 0.5
            if distance < 200:  # Adjust threshold as needed
                files_at_node.append(file_id)

        return files_at_node