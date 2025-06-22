from pathlib import Path
from typing import Optional, Callable, Set
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from .components import Colors


class FileTreeManager:
    """
    Manages the file tree widget and its operations.
    Single responsibility: Handle file tree display, population, and user interactions.
    """

    def __init__(self, tree_widget: QTreeWidget):
        self.tree_widget = tree_widget
        self.on_file_selected: Optional[Callable[[Path], None]] = None
        self._ignore_dirs: Set[str] = {
            '__pycache__', 'node_modules', 'rag_db',
            '.pytest_cache', '.mypy_cache', 'htmlcov',
        }
        self._collapse_dirs: Set[str] = {
            '.venv', 'venv', '.git', '.tox', 'build', 'dist'
        }
        self._setup_tree_widget()

    def _setup_tree_widget(self):
        self.tree_widget.setHeaderLabel("Project Files")
        self.tree_widget.setStyleSheet(f"""
            QTreeWidget {{ 
                border: none; 
                background-color: {Colors.SECONDARY_BG.name()}; 
                font-size: 11px;
            }}
            QHeaderView::section {{ 
                background-color: {Colors.SECONDARY_BG.name()}; 
                color: {Colors.TEXT_SECONDARY.name()}; 
                border: none; 
                padding: 4px; 
                font-weight: bold;
            }}
            QTreeWidget::item {{ padding: 2px; border: none; }}
            QTreeWidget::item:selected {{
                background-color: {Colors.ACCENT_BLUE.name()};
                color: {Colors.TEXT_PRIMARY.name()};
            }}
        """)
        self.tree_widget.itemDoubleClicked.connect(self._on_item_double_clicked)

    def set_file_selection_callback(self, callback: Callable[[Path], None]):
        self.on_file_selected = callback

    def clear_tree(self):
        self.tree_widget.clear()
        print("[FileTreeManager] Tree cleared")

    def setup_new_project_tree(self, project_path: Path, filenames: list[str]) -> bool:
        """Sets up the tree for a brand-new project being generated."""
        self.clear_tree()
        root_item = self._create_project_root_item(project_path)
        self.tree_widget.addTopLevelItem(root_item)
        root_item.setExpanded(True)
        # For a new project, populate from placeholders and disk
        self.add_placeholders_for_new_files(filenames)
        self._populate_from_disk_enhanced(root_item, project_path)
        print(f"[FileTreeManager] New project tree set up for: {project_path.name}")
        return True

    def add_placeholders_for_new_files(self, filenames: list[str]):
        """Adds tree items for files that are planned for creation."""
        root = self.tree_widget.topLevelItem(0)
        if not root: return

        project_path_str = root.data(0, Qt.ItemDataRole.UserRole)
        if not project_path_str: return
        project_root = Path(project_path_str)

        for filename in filenames:
            self._add_file_placeholder(root, filename.split('/'), project_root)

    def load_existing_project_tree(self, project_path: Path) -> bool:
        """Loads or re-loads an existing project's file structure from disk."""
        try:
            if not project_path.is_dir():
                print(f"[FileTreeManager] Error: Not a directory: {project_path}")
                return False
            self.clear_tree()
            root_item = self._create_project_root_item(project_path)
            self.tree_widget.addTopLevelItem(root_item)
            root_item.setExpanded(True)
            self._populate_from_disk_enhanced(root_item, project_path)
            print(f"[FileTreeManager] Loaded/Refreshed project tree: {project_path.name}")
            return True
        except Exception as e:
            print(f"[FileTreeManager] Error loading project tree: {e}")
            return False

    def _create_project_root_item(self, project_path: Path) -> QTreeWidgetItem:
        root_item = QTreeWidgetItem([f"📁 {project_path.name}"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(project_path))
        font = root_item.font(0)
        font.setBold(True)
        root_item.setFont(0, font)
        return root_item

    def _populate_from_disk_enhanced(self, parent_item: QTreeWidgetItem, directory_path: Path):
        """Recursively populates the tree from disk, skipping specified ignores."""
        try:
            entries = sorted(list(directory_path.iterdir()), key=lambda p: (p.is_file(), p.name.lower()))
            for entry in entries:
                if entry.name in self._ignore_dirs:
                    continue
                if entry.name.startswith('.') and entry.name not in {'.env', '.gitignore', '.git'}:
                    continue
                if self._find_child_item_by_path(parent_item, entry):
                    continue  # Avoid duplicating items that are already there (e.g., placeholders)

                if entry.is_dir():
                    dir_item = self._create_directory_item(entry.name, entry)
                    parent_item.addChild(dir_item)
                    self._populate_from_disk_enhanced(dir_item, entry)
                    dir_item.setExpanded(entry.name not in self._collapse_dirs)
                else:
                    file_item = self._create_file_item(entry.name, entry)
                    parent_item.addChild(file_item)
        except Exception as e:
            print(f"[FileTreeManager] Error populating from {directory_path}: {e}")

    def _create_directory_item(self, dir_name: str, dir_path: Path) -> QTreeWidgetItem:
        icon = self._get_directory_icon(dir_name)
        dir_item = QTreeWidgetItem([f"{icon} {dir_name}"])
        dir_item.setData(0, Qt.ItemDataRole.UserRole, str(dir_path))
        if dir_name in {'.venv', 'venv'}:
            font = dir_item.font(0)
            font.setItalic(True)
            dir_item.setFont(0, font)
        return dir_item

    def _create_file_item(self, filename: str, file_path: Path) -> QTreeWidgetItem:
        icon = self._get_file_icon(filename)
        file_item = QTreeWidgetItem([f"{icon} {filename}"])
        file_item.setData(0, Qt.ItemDataRole.UserRole, str(file_path))
        return file_item

    def _get_directory_icon(self, dir_name: str) -> str:
        # Simplified icon logic
        return '📁'

    def _get_file_icon(self, filename: str) -> str:
        # Simplified icon logic
        return '📄'

    def _add_file_placeholder(self, parent_item: QTreeWidgetItem, path_parts: list[str], current_path: Path):
        if not path_parts: return

        part = path_parts[0]
        child_path = current_path / part
        child_item = self._find_child_item_by_path(parent_item, child_path)

        if not child_item:
            if len(path_parts) == 1:
                child_item = self._create_file_item(part, child_path)
            else:
                child_item = self._create_directory_item(part, child_path)
            parent_item.addChild(child_item)

        if len(path_parts) > 1:
            self._add_file_placeholder(child_item, path_parts[1:], child_path)

    def _find_child_item_by_path(self, parent_item: QTreeWidgetItem, path_to_find: Path) -> Optional[QTreeWidgetItem]:
        """Finds a direct child item by matching its stored path data."""
        path_str_to_find = str(path_to_find)
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child_path_str = child.data(0, Qt.ItemDataRole.UserRole)
            if child_path_str == path_str_to_find:
                return child
        return None

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not path_str: return
        file_path = Path(path_str)
        if file_path.is_file() and self.on_file_selected:
            self.on_file_selected(file_path)