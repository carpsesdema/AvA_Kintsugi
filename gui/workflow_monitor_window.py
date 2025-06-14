# kintsugi_ava/gui/workflow_monitor_window.py
# V4: Refactored to support the user-driven co-pilot workflow.

from PySide6.QtWidgets import QMainWindow, QGraphicsView, QVBoxLayout, QWidget, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QFont

from .components import Colors, Typography
from .workflow_monitor_scene import WorkflowMonitorScene


class WorkflowMonitorWindow(QMainWindow):
    """
    A dashboard that visualizes the status of the AI agents, refactored
    to support the user-driven co-pilot workflow.
    """

    def __init__(self, event_bus=None):
        super().__init__()
        self.event_bus = event_bus
        self.setWindowTitle("Kintsugi AvA - Agent Status Monitor")
        self.setGeometry(200, 200, 700, 450)
        self.setStyleSheet(f"background-color: {Colors.PRIMARY_BG.name()};")

        self.scene = WorkflowMonitorScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.view, 1)
        self.status_widget = self._create_status_widget()
        main_layout.addWidget(self.status_widget)
        self.setCentralWidget(main_widget)

        self.current_workflow_type = None
        self.current_files = []
        self.workflow_phase = "idle"

        if self.event_bus:
            self._connect_events()

    def _create_status_widget(self) -> QWidget:
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
        self.phase_label = QLabel("Phase: Idle")
        self.phase_label.setFont(Typography.body())
        self.file_count_label = QLabel("Files: 0")
        self.file_count_label.setFont(Typography.body())
        layout.addWidget(self.phase_label)
        layout.addWidget(QLabel("|"))
        layout.addWidget(self.file_count_label)
        layout.addStretch()
        return status_widget

    def _connect_events(self):
        """Connects to event bus for real-time workflow updates."""
        # Generation
        self.event_bus.subscribe("prepare_for_generation", self._on_prepare_for_generation)
        self.event_bus.subscribe("stream_code_chunk", self._on_stream_code_chunk)
        self.event_bus.subscribe("code_generation_complete", self._on_code_generation_complete)

        # User-driven review flow
        self.event_bus.subscribe("execution_failed", self._on_execution_failed)
        self.event_bus.subscribe("review_and_fix_requested", self._on_review_and_fix_requested)

        # General UI
        self.event_bus.subscribe("node_status_changed", self.scene.update_node_status)
        self.event_bus.subscribe("new_session_requested", self._on_new_session)

    # === EVENT HANDLERS FOR NEW CO-PILOT WORKFLOW ===

    def _on_prepare_for_generation(self, filenames: list, project_path: str = None):
        """Handles preparation for code generation."""
        self.current_files = [f for f in filenames if not f.endswith('.txt')]
        self.workflow_phase = "generating"
        self.scene.start_new_project_flow(self.current_files)
        self._update_status_display()

    def _on_stream_code_chunk(self, filename: str, chunk: str):
        """Shows real-time activity when code is being generated."""
        self.workflow_phase = "generating"
        self.scene.handle_file_streaming(filename)
        self._update_status_display()

    def _on_code_generation_complete(self, files: dict):
        """
        Handles completion of the generation phase.
        The workflow now STOPS and waits for the user.
        """
        self.workflow_phase = "Ready for User Input"
        # We no longer automatically move files to the executor.
        # self.scene.move_files_to_executor()
        self._update_status_display()

    def _on_execution_failed(self, error_report: str):
        """When execution fails, mark the executor node as 'error'."""
        self.workflow_phase = "Execution Failed"
        self.scene.update_node_status("executor", "error", "Execution Failed")
        self._update_status_display()

    def _on_review_and_fix_requested(self):
        """When the user clicks the fix button, show the reviewer as active."""
        self.workflow_phase = "Fixing Code..."
        self.scene.update_node_status("reviewer", "working", "Reviewing error...")
        # We could animate the specific failed file moving to the reviewer here in the future.
        self._update_status_display()

    def _on_new_session(self):
        """Handles new session start - resets visualization."""
        self.workflow_phase = "idle"
        self.current_files = []
        try:
            self.scene.flow_manager.clear_all_files()
        except AttributeError:
            pass  # Scene might not have flow manager
        self._update_status_display()

    def _update_status_display(self):
        """Updates the status bar with current workflow information."""
        self.phase_label.setText(f"Phase: {self.workflow_phase.title()}")
        self.file_count_label.setText(f"Active Files: {len(self.current_files)}")

    def show(self):
        """Shows the workflow monitor window and fits the scene."""
        super().show()
        # Use a QTimer to ensure the scene is fully rendered before fitting
        QTimer.singleShot(100, self.zoom_to_fit)

    def zoom_to_fit(self):
        """Zooms the view to show the entire workflow."""
        if self.scene.items():
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)