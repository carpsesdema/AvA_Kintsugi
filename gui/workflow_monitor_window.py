# kintsugi_ava/gui/workflow_monitor_window.py
# V3: Enhanced workflow monitor with file flow visualization and event integration

from PySide6.QtWidgets import QMainWindow, QGraphicsView, QVBoxLayout, QWidget, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QFont

from .components import Colors, Typography
from .workflow_monitor_scene import WorkflowMonitorScene


class WorkflowMonitorWindow(QMainWindow):
    """
    Enhanced workflow monitor window that displays AI agent status and file flows.
    Features real-time visualization of the code generation pipeline.
    """

    def __init__(self, event_bus=None):
        super().__init__()
        self.event_bus = event_bus
        self.setWindowTitle("Kintsugi AvA - Enhanced Workflow Monitor")
        self.setGeometry(200, 200, 700, 450)
        self.setStyleSheet(f"background-color: {Colors.PRIMARY_BG.name()};")

        # Create the enhanced scene
        self.scene = WorkflowMonitorScene()

        # Create view with optimized settings
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        # Create main widget with status bar
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Add the view
        main_layout.addWidget(self.view, 1)

        # Add status bar at bottom
        self.status_widget = self._create_status_widget()
        main_layout.addWidget(self.status_widget)

        self.setCentralWidget(main_widget)

        # Track current workflow state for intelligent updates
        self.current_workflow_type = None
        self.current_files = []
        self.workflow_phase = "idle"  # idle, planning, generating, testing, reviewing

        # Statistics update timer
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_statistics)
        self.stats_timer.start(1000)  # Update every second

        # Connect to event bus if provided
        if self.event_bus:
            self._connect_events()

    def _create_status_widget(self) -> QWidget:
        """Creates the status bar widget showing workflow statistics."""
        status_widget = QWidget()
        status_widget.setFixedHeight(40)
        status_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.SECONDARY_BG.name()};
                border-top: 1px solid {Colors.BORDER_DEFAULT.name()};
            }}
        """)

        layout = QHBoxLayout(status_widget)
        layout.setContentsMargins(15, 5, 15, 5)

        # Workflow phase indicator
        self.phase_label = QLabel("Phase: Idle")
        self.phase_label.setFont(Typography.body())
        self.phase_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")

        # File count indicator
        self.file_count_label = QLabel("Files: 0")
        self.file_count_label.setFont(Typography.body())
        self.file_count_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")

        # Workflow type indicator
        self.workflow_type_label = QLabel("Ready")
        self.workflow_type_label.setFont(Typography.body())
        self.workflow_type_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")

        layout.addWidget(self.phase_label)
        layout.addWidget(QLabel("|"))
        layout.addWidget(self.file_count_label)
        layout.addWidget(QLabel("|"))
        layout.addWidget(self.workflow_type_label)
        layout.addStretch()

        return status_widget

    def _connect_events(self):
        """Connects to event bus for real-time workflow updates."""
        # Core workflow events
        self.event_bus.subscribe("prepare_for_generation", self._on_prepare_for_generation)
        self.event_bus.subscribe("stream_code_chunk", self._on_stream_code_chunk)
        self.event_bus.subscribe("code_generation_complete", self._on_code_generation_complete)
        self.event_bus.subscribe("node_status_changed", self._on_node_status_changed)

        # Validation and review events
        self.event_bus.subscribe("validation_started", self._on_validation_started)
        self.event_bus.subscribe("validation_failed", self._on_validation_failed)
        self.event_bus.subscribe("review_started", self._on_review_started)
        self.event_bus.subscribe("workflow_completed", self._on_workflow_completed)

        # Session management
        self.event_bus.subscribe("new_session_requested", self._on_new_session)

    # === EVENT HANDLERS ===

    def _on_prepare_for_generation(self, filenames: list, project_path: str = None):
        """Handles preparation for code generation."""
        self.current_files = [f for f in filenames if not f.endswith('.txt')]  # Filter out requirements.txt

        if project_path:
            # New project workflow
            self.current_workflow_type = "New Project"
            self.workflow_phase = "planning"
            self.scene.start_new_project_flow(self.current_files)
        else:
            # Modification workflow
            self.current_workflow_type = "Modification"
            self.workflow_phase = "planning"
            self.scene.start_modification_flow(self.current_files)

        self._update_status_display()

    def _on_stream_code_chunk(self, filename: str, chunk: str):
        """Handles real-time code streaming."""
        self.workflow_phase = "generating"
        self.scene.handle_file_streaming(filename)
        self._update_status_display()

    def _on_code_generation_complete(self, files: dict):
        """Handles completion of code generation."""
        self.workflow_phase = "testing"
        self.scene.move_files_to_executor()
        self._update_status_display()

    def _on_node_status_changed(self, agent_id: str, status: str, status_text: str):
        """Updates node status in the visualization."""
        self.scene.update_node_status(agent_id, status, status_text)

        # Update workflow phase based on agent activity
        if agent_id == "executor" and status == "working":
            self.workflow_phase = "testing"
        elif agent_id == "reviewer" and status == "working":
            self.workflow_phase = "reviewing"
        elif status == "success" and agent_id == "executor":
            self.workflow_phase = "complete"

        self._update_status_display()

    def _on_validation_started(self):
        """Handles start of validation phase."""
        self.workflow_phase = "testing"
        self._update_status_display()

    def _on_validation_failed(self, failed_files: list = None):
        """Handles validation failure - moves files to reviewer."""
        self.workflow_phase = "reviewing"
        self.scene.move_files_to_reviewer(failed_files)
        self._update_status_display()

    def _on_review_started(self):
        """Handles start of review phase."""
        self.workflow_phase = "reviewing"
        self._update_status_display()

    def _on_workflow_completed(self):
        """Handles workflow completion."""
        self.workflow_phase = "complete"
        self.scene.complete_workflow()
        self._update_status_display()

        # Reset to idle after a delay
        QTimer.singleShot(3000, self._reset_to_idle)

    def _on_new_session(self):
        """Handles new session start - resets visualization."""
        self._reset_to_idle()

    # === STATUS AND DISPLAY MANAGEMENT ===

    def _update_status_display(self):
        """Updates the status bar with current workflow information."""
        self.phase_label.setText(f"Phase: {self.workflow_phase.title()}")
        self.file_count_label.setText(f"Files: {len(self.current_files)}")
        self.workflow_type_label.setText(self.current_workflow_type or "Ready")

    def _update_statistics(self):
        """Updates statistics display periodically."""
        try:
            stats = self.scene.get_workflow_statistics()
            active_count = stats['active_files']

            if active_count > 0:
                self.file_count_label.setText(f"Active Files: {active_count}")
        except Exception as e:
            # Graceful handling if scene doesn't have enhanced methods yet
            print(f"[WorkflowMonitor] Statistics update error: {e}")

    def _reset_to_idle(self):
        """Resets the workflow monitor to idle state."""
        self.workflow_phase = "idle"
        self.current_workflow_type = None
        self.current_files = []
        try:
            self.scene.flow_manager.clear_all_files()
        except AttributeError:
            # Graceful handling if enhanced scene not available yet
            pass
        self._update_status_display()

    # === PUBLIC INTERFACE ===

    def update_node_status(self, agent_id: str, status: str, status_text: str):
        """Public slot for updating node status (maintains compatibility)."""
        self._on_node_status_changed(agent_id, status, status_text)

    def show_window(self):
        """Shows the workflow monitor window."""
        if not self.isVisible():
            self.show()
        else:
            self.activateWindow()
            self.raise_()

    def zoom_to_fit(self):
        """Zooms the view to show the entire workflow."""
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def reset_view(self):
        """Resets the view to default zoom and position."""
        self.view.resetTransform()
        self.zoom_to_fit()

    def get_current_stats(self) -> dict:
        """Returns current workflow statistics."""
        try:
            scene_stats = self.scene.get_workflow_statistics()
        except AttributeError:
            scene_stats = {}

        return {
            'workflow_type': self.current_workflow_type,
            'phase': self.workflow_phase,
            'file_count': len(self.current_files),
            'scene_stats': scene_stats
        }