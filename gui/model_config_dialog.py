# kintsugi_ava/gui/model_config_dialog.py
# V3: Added Architect role to the configuration.

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from .components import Colors, Typography, ModernButton
from core.llm_client import LLMClient

class ModelConfigurationDialog(QDialog):
    def __init__(self, llm_client: LLMClient, parent=None):
        super().__init__(parent)
        self.llm_client = llm_client
        self.setWindowTitle("Configure AI Models")
        self.setMinimumSize(500, 350)
        self.setStyleSheet(f"background-color: {Colors.SECONDARY_BG.name()};")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("AI Specialist Configuration")
        title.setFont(Typography.get_font(16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")
        main_layout.addWidget(title)

        self.role_combos = {}
        # --- ADDED ARCHITECT ROLE ---
        roles_to_configure = ["architect", "coder", "chat", "reviewer"]

        for role in roles_to_configure:
            layout, combo = self._create_role_selector(role.title())
            main_layout.addLayout(layout)
            self.role_combos[role] = combo

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        cancel_button = ModernButton("Cancel", "secondary")
        cancel_button.clicked.connect(self.reject)
        apply_button = ModernButton("Apply", "primary")
        apply_button.clicked.connect(self.apply_changes)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(apply_button)
        main_layout.addLayout(button_layout)
        self._populate_models()

    def _create_role_selector(self, role_name: str) -> tuple[QHBoxLayout, QComboBox]:
        layout = QHBoxLayout()
        label = QLabel(f"{role_name}:")
        label.setFont(Typography.body())
        combo = QComboBox()
        combo.setFont(Typography.body())
        layout.addWidget(label)
        layout.addWidget(combo)
        return layout, combo

    def _populate_models(self):
        available_models = self.llm_client.get_available_models()
        current_assignments = self.llm_client.get_role_assignments()
        for role, combo in self.role_combos.items():
            combo.clear()
            current_model_key = current_assignments.get(role)
            current_index = 0
            for i, (key, name) in enumerate(available_models.items()):
                combo.addItem(name, key)
                if key == current_model_key:
                    current_index = i
            combo.setCurrentIndex(current_index)

    def apply_changes(self):
        new_assignments = {}
        for role, combo in self.role_combos.items():
            new_assignments[role] = combo.currentData()
        self.llm_client.set_role_assignments(new_assignments)
        self.llm_client.save_assignments()
        QMessageBox.information(self, "Success", "Model configuration saved.")
        self.accept()