# src/ava/gui/file_tree_manager.py
from pathlib import Path
from typing import Optional, Callable, Set, List

from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMenu, QInputDialog, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QFont, QAction

from .components import Colors
from src.ava.core.event_bus import EventBus  # Added EventBus
from src.ava.core.project_manager import ProjectManager  # Added ProjectManager


class FileTreeManager:
    """
    Manages the file tree widget and its operations, including context menus
    for renaming, deleting, and creating files/folders.
    """

    # Define signals for file operations
    file_renamed = Signal(str, str)  # old_rel_path, new_rel_path
    items_deleted = Signal(list)  # list of deleted relative paths
    file_created = Signal(str)  # new_rel_path
    folder_created = Signal(str)  # new_rel_path

    def __init__(self, tree_widget: QTreeWidget, project_manager: ProjectManager,
                 event_bus: EventBus):  # Added ProjectManager and EventBus
        self.tree_widget = tree_widget
        self.project_manager = project_manager  # Store ProjectManager
        self.event_bus = event_bus  # Store EventBus
        self.on_file_selected_callback: Optional[Callable[[Path], None]] = None  # Renamed for clarity
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

        # Enable multi-selection
        self.tree_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # Enable context menu
        self.tree_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self._show_context_menu)

    def set_file_selection_callback(self, callback: Callable[[Path], None]):
        self.on_file_selected_callback = callback

    def clear_tree(self):
        self.tree_widget.clear()
        print("[FileTreeManager] Tree cleared")

    def setup_new_project_tree(self, project_path: Path, filenames: list[str]) -> bool:
        self.clear_tree()
        root_item = self._create_project_root_item(project_path)
        self.tree_widget.addTopLevelItem(root_item)
        root_item.setExpanded(True)
        self.add_placeholders_for_new_files(filenames)  # Should be called after root is set
        self._populate_from_disk_enhanced(root_item, project_path)  # Populate after placeholders
        print(f"[FileTreeManager] New project tree set up for: {project_path.name}")
        return True

    def add_placeholders_for_new_files(self, filenames: list[str]):
        root = self.tree_widget.topLevelItem(0)
        if not root: return
        project_path_str = root.data(0, Qt.ItemDataRole.UserRole)
        if not project_path_str: return
        project_root = Path(project_path_str)
        for filename in filenames:
            self._add_file_placeholder(root, filename.split('/'), project_root)

    def load_existing_project_tree(self, project_path: Path) -> bool:
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
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(project_path))  # Store full path
        root_item.setData(0, Qt.ItemDataRole.UserRole + 1, True)  # Mark as directory
        font = root_item.font(0)
        font.setBold(True)
        root_item.setFont(0, font)
        return root_item

    def _populate_from_disk_enhanced(self, parent_item: QTreeWidgetItem, directory_path: Path):
        try:
            entries = sorted(list(directory_path.iterdir()), key=lambda p: (p.is_file(), p.name.lower()))
            for entry in entries:
                if entry.name in self._ignore_dirs: continue
                if entry.name.startswith('.') and entry.name not in {'.env', '.gitignore', '.git'}: continue
                if self._find_child_item_by_path(parent_item, entry): continue

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
        icon = '📁'
        dir_item = QTreeWidgetItem([f"{icon} {dir_name}"])
        dir_item.setData(0, Qt.ItemDataRole.UserRole, str(dir_path))  # Store full path
        dir_item.setData(0, Qt.ItemDataRole.UserRole + 1, True)  # Mark as directory
        if dir_name in {'.venv', 'venv'}:
            font = dir_item.font(0)
            font.setItalic(True)
            dir_item.setFont(0, font)
        return dir_item

    def _create_file_item(self, filename: str, file_path: Path) -> QTreeWidgetItem:
        icon = '📄'
        file_item = QTreeWidgetItem([f"{icon} {filename}"])
        file_item.setData(0, Qt.ItemDataRole.UserRole, str(file_path))  # Store full path
        file_item.setData(0, Qt.ItemDataRole.UserRole + 1, False)  # Mark as file
        return file_item

    def _add_file_placeholder(self, parent_item: QTreeWidgetItem, path_parts: list[str], current_path: Path):
        if not path_parts: return
        part = path_parts[0]
        child_path = current_path / part
        child_item = self._find_child_item_by_path(parent_item, child_path)
        if not child_item:
            if len(path_parts) == 1:  # It's a file
                child_item = self._create_file_item(part, child_path)
            else:  # It's a directory
                child_item = self._create_directory_item(part, child_path)
            parent_item.addChild(child_item)
        if len(path_parts) > 1:
            self._add_file_placeholder(child_item, path_parts[1:], child_path)

    def _find_child_item_by_path(self, parent_item: QTreeWidgetItem, path_to_find: Path) -> Optional[QTreeWidgetItem]:
        path_str_to_find = str(path_to_find)
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child_path_str = child.data(0, Qt.ItemDataRole.UserRole)
            if child_path_str == path_str_to_find:
                return child
        return None

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        path_str = item.data(0, Qt.ItemDataRole.UserRole)
        is_dir = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not path_str or is_dir: return  # Only open files on double click

        file_path = Path(path_str)
        if file_path.is_file() and self.on_file_selected_callback:
            self.on_file_selected_callback(file_path)

    def _get_relative_path(self, item: QTreeWidgetItem) -> Optional[str]:
        """Gets the item's path relative to the project root."""
        if not self.project_manager.active_project_path: return None
        item_abs_path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not item_abs_path_str: return None
        try:
            return Path(item_abs_path_str).relative_to(self.project_manager.active_project_path).as_posix()
        except ValueError:  # Should not happen if paths are correct
            return None

    def _show_context_menu(self, position: QPoint):
        menu = QMenu()
        selected_items = self.tree_widget.selectedItems()
        item_at_pos = self.tree_widget.itemAt(position)

        # Ensure the clicked item is part of the selection, or make it the selection
        if item_at_pos and item_at_pos not in selected_items:
            self.tree_widget.clearSelection()
            item_at_pos.setSelected(True)
            selected_items = [item_at_pos]

        if not selected_items:  # No item selected or clicked on empty space
            # Context menu for project root or empty space
            root_item = self.tree_widget.topLevelItem(0)
            if root_item:
                new_file_action = menu.addAction("New File")
                new_file_action.triggered.connect(lambda: self._handle_new_file(root_item))
                new_folder_action = menu.addAction("New Folder")
                new_folder_action.triggered.connect(lambda: self._handle_new_folder(root_item))

        elif len(selected_items) == 1:
            item = selected_items[0]
            is_dir = item.data(0, Qt.ItemDataRole.UserRole + 1)

            rename_action = menu.addAction("Rename")
            rename_action.triggered.connect(lambda: self._handle_rename(item))

            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(lambda: self._handle_delete(selected_items))

            if is_dir:
                menu.addSeparator()
                new_file_action = menu.addAction("New File in Folder")
                new_file_action.triggered.connect(lambda: self._handle_new_file(item))
                new_folder_action = menu.addAction("New Subfolder")
                new_folder_action.triggered.connect(lambda: self._handle_new_folder(item))

        elif len(selected_items) > 1:  # Multiple items selected
            delete_action = menu.addAction(f"Delete {len(selected_items)} items")
            delete_action.triggered.connect(lambda: self._handle_delete(selected_items))

        if not menu.isEmpty():
            menu.exec(self.tree_widget.viewport().mapToGlobal(position))

    def _handle_rename(self, item: QTreeWidgetItem):
        rel_path_str = self._get_relative_path(item)
        if not rel_path_str: return

        old_name = Path(rel_path_str).name
        new_name, ok = QInputDialog.getText(self.tree_widget, "Rename Item", "Enter new name:", text=old_name)

        if ok and new_name and new_name != old_name:
            success, msg, new_rel_path = self.project_manager.rename_item(rel_path_str, new_name)
            if success:
                QMessageBox.information(self.tree_widget, "Rename Successful", msg)
                self.event_bus.emit("file_renamed", rel_path_str, new_rel_path)  # Emit with old and new relative paths
                self.load_existing_project_tree(self.project_manager.active_project_path)  # Refresh tree
            else:
                QMessageBox.warning(self.tree_widget, "Rename Failed", msg)

    def _handle_delete(self, items: List[QTreeWidgetItem]):
        if not items: return

        item_names = [Path(self._get_relative_path(item)).name for item in items if self._get_relative_path(item)]
        if not item_names: return

        reply = QMessageBox.question(self.tree_widget, "Confirm Delete",
                                     f"Are you sure you want to delete:\n- {', '.join(item_names)}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            paths_to_delete = [self._get_relative_path(item) for item in items if self._get_relative_path(item)]
            if not paths_to_delete: return

            success, msg = self.project_manager.delete_items(paths_to_delete)
            if success:
                QMessageBox.information(self.tree_widget, "Delete Successful", msg)
                self.event_bus.emit("items_deleted", paths_to_delete)
                self.load_existing_project_tree(self.project_manager.active_project_path)  # Refresh tree
            else:
                QMessageBox.warning(self.tree_widget, "Delete Failed", msg)

    def _handle_new_file(self, parent_dir_item: QTreeWidgetItem):
        parent_dir_rel_path_str = self._get_relative_path(parent_dir_item)
        if parent_dir_rel_path_str is None:  # Should be project root if None
            if self.project_manager.active_project_path:
                parent_dir_rel_path_str = "."  # Represent project root
            else:
                return

        new_filename, ok = QInputDialog.getText(self.tree_widget, "New File", "Enter file name:")
        if ok and new_filename:
            success, msg, new_file_rel_path = self.project_manager.create_file(parent_dir_rel_path_str, new_filename)
            if success:
                QMessageBox.information(self.tree_widget, "File Created", msg)
                self.event_bus.emit("file_created", new_file_rel_path)
                self.load_existing_project_tree(self.project_manager.active_project_path)  # Refresh tree
            else:
                QMessageBox.warning(self.tree_widget, "Create File Failed", msg)

    def _handle_new_folder(self, parent_dir_item: QTreeWidgetItem):
        parent_dir_rel_path_str = self._get_relative_path(parent_dir_item)
        if parent_dir_rel_path_str is None:
            if self.project_manager.active_project_path:
                parent_dir_rel_path_str = "."
            else:
                return

        new_foldername, ok = QInputDialog.getText(self.tree_widget, "New Folder", "Enter folder name:")
        if ok and new_foldername:
            success, msg, new_folder_rel_path = self.project_manager.create_folder(parent_dir_rel_path_str,
                                                                                   new_foldername)
            if success:
                QMessageBox.information(self.tree_widget, "Folder Created", msg)
                self.event_bus.emit("folder_created", new_folder_rel_path)
                self.load_existing_project_tree(self.project_manager.active_project_path)  # Refresh tree
            else:
                QMessageBox.warning(self.tree_widget, "Create Folder Failed", msg)