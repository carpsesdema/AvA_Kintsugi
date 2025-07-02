# src/ava/gui/file_tree_manager.py
from pathlib import Path
from typing import Optional, Callable, Set, List

from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMenu, QInputDialog, QMessageBox, QAbstractItemView, QApplication,
    QTreeWidgetItemIterator, QStyle, QWidget, QVBoxLayout, QHBoxLayout
)
from PySide6.QtCore import Qt, Signal, QPoint, QMimeData, QByteArray, QUrl, QObject
from PySide6.QtGui import QFont, QAction, QDragEnterEvent, QDropEvent, QDrag, QMouseEvent, QPixmap, \
    QDragMoveEvent
import qtawesome as qta

from .components import Colors, ModernButton
from src.ava.core.event_bus import EventBus
from src.ava.core.project_manager import ProjectManager

# --- Custom MIME Type for Internal D&D ---
INTERNAL_MIME_TYPE_PROJECT_ITEMS = "application/x-projectitems"


class CustomFileTreeWidget(QTreeWidget):
    items_dropped_internally = Signal(list, QTreeWidgetItem)
    external_files_dropped = Signal(list, QTreeWidgetItem)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.project_manager_ref: Optional[ProjectManager] = None

    def set_project_manager(self, pm: ProjectManager):
        self.project_manager_ref = pm

    def _get_relative_path(self, item: QTreeWidgetItem) -> Optional[str]:
        if not self.project_manager_ref or not self.project_manager_ref.active_project_path:
            return None
        item_abs_path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not item_abs_path_str: return None
        try:
            abs_path = Path(item_abs_path_str).resolve()
            if abs_path == self.project_manager_ref.active_project_path.resolve():
                return "."
            return abs_path.relative_to(self.project_manager_ref.active_project_path.resolve()).as_posix()
        except ValueError:
            return None

    def startDrag(self, supportedActions: Qt.DropActions):
        selected_items = self.selectedItems()
        if not selected_items:
            return

        if self.topLevelItem(0) in selected_items and len(selected_items) == 1:
            if self._get_relative_path(self.topLevelItem(0)) == ".":
                return

        drag = QDrag(self)
        mime_data = QMimeData()

        internal_data_list = []
        url_list = []

        for item in selected_items:
            abs_path_str = item.data(0, Qt.ItemDataRole.UserRole)
            if abs_path_str:
                rel_path_str = self._get_relative_path(item)
                if rel_path_str and rel_path_str != ".":
                    internal_data_list.append(rel_path_str)
                    url_list.append(QUrl.fromLocalFile(abs_path_str))

        if not internal_data_list:
            return

        encoded_data = QByteArray()
        encoded_data.append(",".join(internal_data_list).encode('utf-8'))
        mime_data.setData(INTERNAL_MIME_TYPE_PROJECT_ITEMS, encoded_data)

        if url_list:
            mime_data.setUrls(url_list)

        drag.setMimeData(mime_data)

        if selected_items:
            item_icon = selected_items[0].icon(0)
            pixmap = QPixmap()
            if not item_icon.isNull():
                temp_pixmap = item_icon.pixmap(32, 32)
                if not temp_pixmap.isNull():
                    pixmap = temp_pixmap

            if pixmap.isNull():
                pixmap = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon).pixmap(32, 32)

            if not pixmap.isNull():
                drag.setPixmap(pixmap)
                drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))

        drag.exec(supportedActions | Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasFormat(INTERNAL_MIME_TYPE_PROJECT_ITEMS) or event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasFormat(INTERNAL_MIME_TYPE_PROJECT_ITEMS) or event.mimeData().hasUrls():
            target_item = self.itemAt(event.position().toPoint())
            if self._is_valid_drop_target(target_item):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def _is_valid_drop_target(self, item: Optional[QTreeWidgetItem]) -> bool:
        if not item:
            return self.project_manager_ref is not None and self.project_manager_ref.active_project_path is not None
        return item.data(0, Qt.ItemDataRole.UserRole + 1)

    def dropEvent(self, event: QDropEvent):
        target_item = self.itemAt(event.position().toPoint())

        if not self._is_valid_drop_target(target_item):
            event.ignore()
            return

        if event.mimeData().hasFormat(INTERNAL_MIME_TYPE_PROJECT_ITEMS):
            encoded_data = event.mimeData().data(INTERNAL_MIME_TYPE_PROJECT_ITEMS)
            source_rel_paths_str = bytes(encoded_data).decode('utf-8')
            source_rel_paths = source_rel_paths_str.split(',')

            for src_path_str in source_rel_paths:
                src_item = self._find_item_by_relative_path(src_path_str)
                if src_item:
                    temp_target = target_item
                    while temp_target:
                        if temp_target == src_item:
                            QMessageBox.warning(self, "Invalid Move",
                                                "Cannot move an item into itself or one of its children.")
                            event.ignore()
                            return
                        temp_target = temp_target.parent()

            self.items_dropped_internally.emit(source_rel_paths, target_item)
            event.acceptProposedAction()

        elif event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            local_file_paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
            if local_file_paths:
                self.external_files_dropped.emit(local_file_paths, target_item)
                event.acceptProposedAction()
        else:
            event.ignore()

    def _find_item_by_relative_path(self, rel_path_to_find: str) -> Optional[QTreeWidgetItem]:
        if not self.project_manager_ref or not self.project_manager_ref.active_project_path:
            return None
        if rel_path_to_find == ".":
            return self.topLevelItem(0)
        abs_path_to_find = str((self.project_manager_ref.active_project_path / rel_path_to_find).resolve())
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            item_abs_path = item.data(0, Qt.ItemDataRole.UserRole)
            if item_abs_path == abs_path_to_find:
                return item
            iterator += 1
        return None


class FileTreeManager(QObject):
    items_renamed_internally = Signal(str, str)
    items_deleted_internally = Signal(list)
    file_created_internally = Signal(str)
    folder_created_internally = Signal(str)
    items_moved_internally = Signal(list)
    items_added_externally = Signal(list)

    def __init__(self, tree_widget_parent: QWidget, project_manager: ProjectManager, event_bus: EventBus):
        super().__init__()
        self.project_manager = project_manager
        self.event_bus = event_bus
        self.on_file_selected_callback: Optional[Callable[[Path], None]] = None
        self._ignore_dirs: Set[str] = {
            '__pycache__', 'node_modules', 'rag_db',
            '.pytest_cache', '.mypy_cache', 'htmlcov',
        }
        self._collapse_dirs: Set[str] = {
            '.venv', 'venv', '.git', '.tox', 'build', 'dist'
        }

        # Main widget and layout for this manager
        self.container_widget = QWidget(tree_widget_parent)
        self.container_layout = QVBoxLayout(self.container_widget)
        self.container_layout.setContentsMargins(0, 5, 0, 0)
        self.container_layout.setSpacing(5)

        # Action bar at the top
        self._create_action_bar()

        # The tree widget itself
        self.tree_widget = CustomFileTreeWidget(self.container_widget)
        self.tree_widget.set_project_manager(project_manager)
        self.container_layout.addWidget(self.tree_widget)

        self._setup_tree_widget_appearance()
        self._connect_custom_tree_signals()
        self._connect_event_bus_signals()

    def _create_action_bar(self):
        action_bar = QWidget()
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(0, 0, 0, 0)

        add_to_rag_btn = ModernButton("Add All to RAG", "secondary")
        add_to_rag_btn.setIcon(qta.icon("fa5s.brain", color=Colors.TEXT_PRIMARY.name()))
        add_to_rag_btn.setToolTip("Adds all current project source files to the knowledge base.")
        add_to_rag_btn.clicked.connect(lambda: self.event_bus.emit("add_active_project_to_rag_requested"))

        action_layout.addWidget(add_to_rag_btn)
        action_layout.addStretch()
        self.container_layout.addWidget(action_bar)

    def _connect_event_bus_signals(self):
        self.items_renamed_internally.connect(lambda old, new: self.event_bus.emit("file_renamed", old, new))
        self.items_deleted_internally.connect(lambda paths: self.event_bus.emit("items_deleted", paths))
        self.file_created_internally.connect(lambda path: self.event_bus.emit("file_created", path))
        self.folder_created_internally.connect(lambda path: self.event_bus.emit("folder_created", path))
        self.items_moved_internally.connect(lambda infos: self.event_bus.emit("items_moved", infos))
        self.items_added_externally.connect(lambda infos: self.event_bus.emit("items_added", infos))

    def _setup_tree_widget_appearance(self):
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
        self.tree_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self._show_context_menu)

    def _connect_custom_tree_signals(self):
        self.tree_widget.items_dropped_internally.connect(self.handle_internal_drop)
        self.tree_widget.external_files_dropped.connect(self.handle_external_drop)

    def get_widget(self) -> QWidget:
        return self.container_widget

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
        self.add_placeholders_for_new_files(filenames)
        self._populate_from_disk_enhanced(root_item, project_path)
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
            current_expanded_items = self._get_expanded_items_paths()
            current_selected_items = [self._get_relative_path(item) for item in self.tree_widget.selectedItems() if
                                      self._get_relative_path(item)]

            self.clear_tree()
            root_item = self._create_project_root_item(project_path)
            self.tree_widget.addTopLevelItem(root_item)
            self._populate_from_disk_enhanced(root_item, project_path)
            self._restore_expanded_items(current_expanded_items)
            self._restore_selected_items(current_selected_items)

            print(f"[FileTreeManager] Loaded/Refreshed project tree: {project_path.name}")
            return True
        except Exception as e:
            print(f"[FileTreeManager] Error loading project tree: {e}")
            return False

    def refresh_tree_from_disk(self):
        """Public method to trigger a refresh of the file tree."""
        if self.project_manager and self.project_manager.active_project_path:
            self.log("info", "Refreshing file tree from disk...")
            self.load_existing_project_tree(self.project_manager.active_project_path)
        else:
            self.log("warning", "Cannot refresh tree, no active project.")

    def _get_expanded_items_paths(self) -> Set[str]:
        expanded_paths = set()
        iterator = QTreeWidgetItemIterator(self.tree_widget)
        while iterator.value():
            item = iterator.value()
            if item.isExpanded():
                path = self._get_relative_path(item)
                if path is not None:
                    expanded_paths.add(path)
            iterator += 1
        return expanded_paths

    def _restore_expanded_items(self, expanded_paths: Set[str]):
        if not self.project_manager.active_project_path: return
        iterator = QTreeWidgetItemIterator(self.tree_widget)
        while iterator.value():
            item = iterator.value()
            path = self._get_relative_path(item)
            if path is not None and path in expanded_paths:
                item.setExpanded(True)
            elif item == self.tree_widget.topLevelItem(0):
                item.setExpanded(True)
            iterator += 1

    def _restore_selected_items(self, selected_paths: List[str]):
        if not self.project_manager.active_project_path: return
        for path_str in selected_paths:
            if path_str is None: continue
            if path_str == ".":
                item = self.tree_widget.topLevelItem(0)
            else:
                abs_path = self.project_manager.active_project_path / path_str
                item = self._find_item_by_abs_path(str(abs_path))
            if item:
                item.setSelected(True)
                self.tree_widget.scrollToItem(item)

    def _find_item_by_abs_path(self, abs_path_to_find: str) -> Optional[QTreeWidgetItem]:
        iterator = QTreeWidgetItemIterator(self.tree_widget)
        while iterator.value():
            item = iterator.value()
            item_abs_path = item.data(0, Qt.ItemDataRole.UserRole)
            if item_abs_path == abs_path_to_find:
                return item
            iterator += 1
        return None

    def _create_project_root_item(self, project_path: Path) -> QTreeWidgetItem:
        root_item = QTreeWidgetItem([f"{project_path.name}"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(project_path.resolve()))
        root_item.setData(0, Qt.ItemDataRole.UserRole + 1, True)
        font = root_item.font(0)
        font.setBold(True)
        root_item.setFont(0, font)
        root_icon = self.tree_widget.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        root_item.setIcon(0, root_icon)
        return root_item

    def _populate_from_disk_enhanced(self, parent_item: QTreeWidgetItem, directory_path: Path):
        try:
            entries = sorted(list(directory_path.iterdir()), key=lambda p: (p.is_file(), p.name.lower()))
            for entry in entries:
                if entry.name in self._ignore_dirs: continue
                if entry.name.startswith('.') and entry.name not in {'.env', '.gitignore', '.git'}: continue
                if self._find_child_item_by_path(parent_item, entry.resolve()): continue

                if entry.is_dir():
                    dir_item = self._create_directory_item(entry.name, entry.resolve())
                    parent_item.addChild(dir_item)
                    self._populate_from_disk_enhanced(dir_item, entry.resolve())
                else:
                    file_item = self._create_file_item(entry.name, entry.resolve())
                    parent_item.addChild(file_item)
        except Exception as e:
            print(f"[FileTreeManager] Error populating from {directory_path}: {e}")

    def _create_directory_item(self, dir_name: str, dir_path: Path) -> QTreeWidgetItem:
        dir_item = QTreeWidgetItem([f"{dir_name}"])
        dir_item.setData(0, Qt.ItemDataRole.UserRole, str(dir_path.resolve()))
        dir_item.setData(0, Qt.ItemDataRole.UserRole + 1, True)
        if dir_name in {'.venv', 'venv'}:
            font = dir_item.font(0)
            font.setItalic(True)
            dir_item.setFont(0, font)
        dir_icon = self.tree_widget.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        dir_item.setIcon(0, dir_icon)
        return dir_item

    def _create_file_item(self, filename: str, file_path: Path) -> QTreeWidgetItem:
        file_item = QTreeWidgetItem([f"{filename}"])
        file_item.setData(0, Qt.ItemDataRole.UserRole, str(file_path.resolve()))
        file_item.setData(0, Qt.ItemDataRole.UserRole + 1, False)
        file_icon = self.tree_widget.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        file_item.setIcon(0, file_icon)
        return file_item

    def _add_file_placeholder(self, parent_item: QTreeWidgetItem, path_parts: list[str], current_path: Path):
        if not path_parts: return
        part = path_parts[0]
        child_path = (current_path / part).resolve()
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
        path_str_to_find = str(path_to_find.resolve())
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child_path_str = child.data(0, Qt.ItemDataRole.UserRole)
            if child_path_str == path_str_to_find:
                return child
        return None

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        path_str = item.data(0, Qt.ItemDataRole.UserRole)
        is_dir = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not path_str or is_dir: return
        file_path = Path(path_str)
        if file_path.is_file() and self.on_file_selected_callback:
            self.on_file_selected_callback(file_path)

    def _get_relative_path(self, item: Optional[QTreeWidgetItem]) -> Optional[str]:
        if not item: return None
        if not self.project_manager.active_project_path: return None
        item_abs_path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not item_abs_path_str: return None
        try:
            abs_path = Path(item_abs_path_str).resolve()
            if abs_path == self.project_manager.active_project_path.resolve():
                return "."
            return abs_path.relative_to(self.project_manager.active_project_path.resolve()).as_posix()
        except ValueError:
            print(
                f"[FileTreeManager] Error getting relative path for {item_abs_path_str} against {self.project_manager.active_project_path}")
            return None

    def _show_context_menu(self, position: QPoint):
        menu = QMenu()
        selected_items = self.tree_widget.selectedItems()
        item_at_pos = self.tree_widget.itemAt(position)

        if item_at_pos and item_at_pos not in selected_items:
            self.tree_widget.clearSelection()
            item_at_pos.setSelected(True)
            selected_items = [item_at_pos]

        target_item_for_new = item_at_pos
        if not target_item_for_new:
            target_item_for_new = self.tree_widget.topLevelItem(0)

        actual_parent_item_for_new = target_item_for_new
        if target_item_for_new:
            is_target_dir = target_item_for_new.data(0, Qt.ItemDataRole.UserRole + 1)
            if not is_target_dir:
                actual_parent_item_for_new = target_item_for_new.parent() if target_item_for_new.parent() else self.tree_widget.topLevelItem(
                    0)

        if actual_parent_item_for_new:
            new_file_action = menu.addAction("New File")
            new_file_action.triggered.connect(lambda: self._handle_new_file(actual_parent_item_for_new))
            new_folder_action = menu.addAction("New Folder")
            new_folder_action.triggered.connect(lambda: self._handle_new_folder(actual_parent_item_for_new))
            menu.addSeparator()

        if len(selected_items) == 1:
            item = selected_items[0]
            if self._get_relative_path(item) != ".":
                rename_action = menu.addAction("Rename")
                rename_action.triggered.connect(lambda: self._handle_rename(item))

                delete_action = menu.addAction("Delete")
                delete_action.triggered.connect(lambda: self._handle_delete(selected_items))

        elif len(selected_items) > 1:
            items_for_multi_delete = [it for it in selected_items if self._get_relative_path(it) != "."]
            if items_for_multi_delete:
                delete_action = menu.addAction(f"Delete {len(items_for_multi_delete)} items")
                delete_action.triggered.connect(lambda: self._handle_delete(items_for_multi_delete))

        if not menu.isEmpty():
            menu.exec(self.tree_widget.viewport().mapToGlobal(position))

    def _handle_rename(self, item: QTreeWidgetItem):
        rel_path_str = self._get_relative_path(item)
        if not rel_path_str or rel_path_str == ".":
            QMessageBox.warning(self.tree_widget, "Rename Info", "Cannot rename the project root.")
            return
        old_name = Path(rel_path_str).name
        new_name, ok = QInputDialog.getText(self.tree_widget, "Rename Item", "Enter new name:", text=old_name)
        if ok and new_name and new_name != old_name:
            success, msg, new_rel_path = self.project_manager.rename_item(rel_path_str, new_name)
            if success and new_rel_path is not None:
                QMessageBox.information(self.tree_widget, "Rename Successful", msg)
                self.items_renamed_internally.emit(rel_path_str, new_rel_path)
                self.load_existing_project_tree(self.project_manager.active_project_path)
            else:
                QMessageBox.warning(self.tree_widget, "Rename Failed", msg)

    def _handle_delete(self, items: List[QTreeWidgetItem]):
        if not items: return
        items_to_delete = [item for item in items if self._get_relative_path(item) != "."]
        if not items_to_delete:
            if any(self._get_relative_path(item) == "." for item in items):
                QMessageBox.information(self.tree_widget, "Delete Info", "Cannot delete the project root.")
            return
        item_names = [Path(self._get_relative_path(item)).name for item in items_to_delete if
                      self._get_relative_path(item)]
        if not item_names: return
        reply = QMessageBox.question(self.tree_widget, "Confirm Delete",
                                     f"Are you sure you want to delete:\n- {', '.join(item_names)}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            paths_to_delete = [self._get_relative_path(item) for item in items_to_delete if
                               self._get_relative_path(item)]
            if not paths_to_delete: return
            success, msg = self.project_manager.delete_items(paths_to_delete)
            if success:
                QMessageBox.information(self.tree_widget, "Delete Successful", msg)
                self.items_deleted_internally.emit(paths_to_delete)
                self.load_existing_project_tree(self.project_manager.active_project_path)
            else:
                QMessageBox.warning(self.tree_widget, "Delete Failed", msg)

    def _handle_new_file(self, parent_dir_item: Optional[QTreeWidgetItem]):
        if not parent_dir_item:
            QMessageBox.warning(self.tree_widget, "Error", "Cannot determine target directory for new file.")
            return
        parent_dir_rel_path_str = self._get_relative_path(parent_dir_item)
        if parent_dir_rel_path_str is None:
            QMessageBox.warning(self.tree_widget, "Error", "Invalid parent directory for new file.")
            return
        new_filename, ok = QInputDialog.getText(self.tree_widget, "New File", "Enter file name:")
        if ok and new_filename:
            success, msg, new_file_rel_path = self.project_manager.create_file(parent_dir_rel_path_str, new_filename)
            if success and new_file_rel_path is not None:
                QMessageBox.information(self.tree_widget, "File Created", msg)
                self.file_created_internally.emit(new_file_rel_path)
                self.load_existing_project_tree(self.project_manager.active_project_path)
            else:
                QMessageBox.warning(self.tree_widget, "Create File Failed", msg)

    def _handle_new_folder(self, parent_dir_item: Optional[QTreeWidgetItem]):
        if not parent_dir_item:
            QMessageBox.warning(self.tree_widget, "Error", "Cannot determine target directory for new folder.")
            return
        parent_dir_rel_path_str = self._get_relative_path(parent_dir_item)
        if parent_dir_rel_path_str is None:
            QMessageBox.warning(self.tree_widget, "Error", "Invalid parent directory for new folder.")
            return
        new_foldername, ok = QInputDialog.getText(self.tree_widget, "New Folder", "Enter folder name:")
        if ok and new_foldername:
            success, msg, new_folder_rel_path = self.project_manager.create_folder(parent_dir_rel_path_str,
                                                                                   new_foldername)
            if success and new_folder_rel_path is not None:
                QMessageBox.information(self.tree_widget, "Folder Created", msg)
                self.folder_created_internally.emit(new_folder_rel_path)
                self.load_existing_project_tree(self.project_manager.active_project_path)
            else:
                QMessageBox.warning(self.tree_widget, "Create Folder Failed", msg)

    def handle_internal_drop(self, source_rel_paths: List[str], target_item: Optional[QTreeWidgetItem]):
        if not self.project_manager.active_project_path:
            QMessageBox.warning(self.tree_widget, "Move Error", "No active project.")
            return

        target_dir_rel_path = "."
        if target_item:
            is_target_dir = target_item.data(0, Qt.ItemDataRole.UserRole + 1)
            if not is_target_dir:
                target_item = target_item.parent()
            if target_item:
                target_dir_rel_path = self._get_relative_path(target_item)
            if target_dir_rel_path is None: target_dir_rel_path = "."

        if not source_rel_paths: return

        moved_paths_info = []
        all_successful = True
        error_messages = []

        for src_rel_path in source_rel_paths:
            if Path(target_dir_rel_path).is_relative_to(Path(src_rel_path)) and Path(
                    self.project_manager.active_project_path / src_rel_path).is_dir():
                error_messages.append(
                    f"Cannot move directory '{Path(src_rel_path).name}' into itself or one of its subdirectories.")
                all_successful = False
                continue

            original_item_name = Path(src_rel_path).name
            success, msg, new_actual_rel_path = self.project_manager.move_item(src_rel_path, target_dir_rel_path,
                                                                               original_item_name)

            if success and new_actual_rel_path:
                moved_paths_info.append({"old": src_rel_path, "new": new_actual_rel_path})
            else:
                all_successful = False
                error_messages.append(f"Failed to move '{Path(src_rel_path).name}': {msg}")

        if error_messages:
            QMessageBox.warning(self.tree_widget, "Move Operation Issues", "\n".join(error_messages))

        if moved_paths_info:
            self.items_moved_internally.emit(moved_paths_info)
            self.load_existing_project_tree(self.project_manager.active_project_path)
        elif not all_successful and not moved_paths_info:
            self.load_existing_project_tree(self.project_manager.active_project_path)

    def handle_external_drop(self, local_file_paths: List[str], target_item: Optional[QTreeWidgetItem]):
        if not self.project_manager.active_project_path:
            QMessageBox.warning(self.tree_widget, "Drop Error", "No active project to drop files into.")
            return

        target_dir_rel_path = "."
        if target_item:
            is_target_dir = target_item.data(0, Qt.ItemDataRole.UserRole + 1)
            if not is_target_dir:
                target_item = target_item.parent()
            if target_item:
                target_dir_rel_path = self._get_relative_path(target_item)
            if target_dir_rel_path is None: target_dir_rel_path = "."

        success, msg, new_copied_infos = self.project_manager.copy_external_items(local_file_paths, target_dir_rel_path)

        if success:
            QMessageBox.information(self.tree_widget, "Drop Successful", msg)
            self.items_added_externally.emit(new_copied_infos)
            self.load_existing_project_tree(self.project_manager.active_project_path)
        else:
            QMessageBox.warning(self.tree_widget, "Drop Failed", msg)

    def log(self, level, message):
        self.event_bus.emit(f"log_message_received", "FileTreeManager", level, message)