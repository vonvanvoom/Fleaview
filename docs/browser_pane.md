# `browser_pane.py`

**Role:** File Views, Filter/Search, Context Menu & File Operations

## Source Code

```python
import os
import shutil
import subprocess
from send2trash import send2trash
from batch_rename import BatchRenameDialog
from PySide6.QtCore import Qt, QDir, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox,
    QStackedWidget, QTreeView, QListView, QColumnView, QFileSystemModel,
    QPushButton, QListWidget, QListWidgetItem, QMenu, QInputDialog, QMessageBox
)
from archive_fs import is_archive

# Shared clipboard state across tabs and split panes
FILE_CLIPBOARD = {"paths": [], "cut": False}

class BrowserTab(QWidget):
    file_selected = Signal(str)
    title_changed = Signal(str)
    open_in_new_tab = Signal(str)

    def __init__(self, path, archive_manager):
        super().__init__()
        self.archive_manager = archive_manager
        self.current_dir = os.path.abspath(path)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        # Top Navigation & View Bar
        nav_bar = QHBoxLayout()
        self.up_btn = QPushButton("↑")
        self.up_btn.setFixedWidth(30)
        self.up_btn.clicked.connect(self.go_up)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Type to filter folder (prefix 'find:' to search subfolders)...")
        self.filter_input.textChanged.connect(self.on_filter_changed)

        self.view_selector = QComboBox()
        self.view_selector.addItems(["Details Tree", "List View", "Icon Grid", "Miller Columns"])
        self.view_selector.currentIndexChanged.connect(self.switch_view_mode)

        nav_bar.addWidget(self.up_btn)
        nav_bar.addWidget(self.filter_input)
        nav_bar.addWidget(self.view_selector)
        layout.addLayout(nav_bar)

        self.show_hidden = False
        self.model = QFileSystemModel()
        self.model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot | QDir.AllDirs)
        self.model.setRootPath(QDir.rootPath())
        self.model.setNameFilterDisables(False)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # Shared FileSystem Model
        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.rootPath())
        self.model.setNameFilterDisables(False)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        # Mode 0: Details Tree
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.model)
        self.tree_view.setSortingEnabled(True)
        self.tree_view.setDragEnabled(True)
        self.tree_view.setAcceptDrops(True)
        self.tree_view.setDropIndicatorShown(True)
        self.tree_view.setSelectionMode(QTreeView.ExtendedSelection)
        self._connect_view(self.tree_view)
        self.stack.addWidget(self.tree_view)

        # Mode 1: Compact List View
        self.list_view = QListView()
        self.list_view.setModel(self.model)
        self.list_view.setSelectionMode(QListView.ExtendedSelection)
        self._connect_view(self.list_view)
        self.stack.addWidget(self.list_view)

        # Mode 2: Icon Grid
        self.icon_view = QListView()
        self.icon_view.setModel(self.model)
        self.icon_view.setViewMode(QListView.IconMode)
        self.icon_view.setResizeMode(QListView.Adjust)
        self.icon_view.setSelectionMode(QListView.ExtendedSelection)
        self._connect_view(self.icon_view)
        self.stack.addWidget(self.icon_view)

        # Mode 3: Miller Columns
        self.column_view = QColumnView()
        self.column_view.setModel(self.model)
        self._connect_view(self.column_view)
        self.stack.addWidget(self.column_view)

        # Mode 4: Subfolder Search Results
        self.search_results = QListWidget()
        self.search_results.currentItemChanged.connect(self._on_search_item_selected)
        self.search_results.itemDoubleClicked.connect(self._on_search_item_activated)
        self.stack.addWidget(self.search_results)

        self._setup_shortcuts()
        self.navigate(self.current_dir)

    def _setup_shortcuts(self):
        shortcuts = [
            ("Ctrl+C", self.copy_selected),
            ("Ctrl+X", self.cut_selected),
            ("Ctrl+V", self.paste_items),
            ("F2", self.rename_selected),
            ("Delete", lambda: self.delete_selected(permanent=False)),
            ("Shift+Delete", lambda: self.delete_selected(permanent=True)),
            ("Ctrl+Shift+N", self.create_new_folder),
        ]
        for key, fn in shortcuts:
            act = QAction(self)
            act.setShortcut(QKeySequence(key))
            act.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            act.triggered.connect(fn)
            self.addAction(act)

    def _connect_view(self, view):
        view.selectionModel().currentChanged.connect(self._on_selection)
        view.clicked.connect(lambda idx: self._on_selection(idx, None))
        view.doubleClicked.connect(self._on_double_click)
        view.setContextMenuPolicy(Qt.CustomContextMenu)
        view.customContextMenuRequested.connect(lambda pos, v=view: self._show_context_menu(v, pos))

    def selected_paths(self):
        active_view = self.stack.currentWidget()
        if active_view == self.search_results:
            item = self.search_results.currentItem()
            return [item.data(Qt.UserRole)] if item else []
        sel_model = active_view.selectionModel()
        indexes = sel_model.selectedRows() if hasattr(sel_model, "selectedRows") else sel_model.selectedIndexes()
        return list(dict.fromkeys(self.model.filePath(idx) for idx in indexes if idx.isValid()))

    def current_path(self):
        paths = self.selected_paths()
        return paths if paths else self.current_dir

    # --- File Management Actions ---
    def open_selected(self):
        path = self.current_path()
        if not path or not os.path.exists(path):
            return
        if os.path.isdir(path):
            self.navigate(path)
        elif is_archive(path):
            self.navigate(self.archive_manager.open_archive(path, self))
        else:
            subprocess.Popen(["xdg-open", path])

    def copy_selected(self):
        paths = self.selected_paths()
        if paths:
            FILE_CLIPBOARD["paths"] = paths
            FILE_CLIPBOARD["cut"] = False

    def cut_selected(self):
        paths = self.selected_paths()
        if paths:
            FILE_CLIPBOARD["paths"] = paths
            FILE_CLIPBOARD["cut"] = True

    def paste_items(self):
        sources = FILE_CLIPBOARD["paths"]
        if not sources:
            return
        for src in sources:
            if not os.path.exists(src):
                continue
            name = os.path.basename(src)
            dst = os.path.join(self.current_dir, name)
            if os.path.exists(dst):
                base, ext = os.path.splitext(name)
                dst = os.path.join(self.current_dir, f"{base}_copy{ext}")
            try:
                if FILE_CLIPBOARD["cut"]:
                    shutil.move(src, dst)
                elif os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            except Exception as e:
                QMessageBox.critical(self, "Paste Error", f"Failed on {name}:\n{e}")
        if FILE_CLIPBOARD["cut"]:
            FILE_CLIPBOARD["paths"] = []
            FILE_CLIPBOARD["cut"] = False

    def rename_selected(self):
        paths = self.selected_paths()
        if not paths:
            return
        if len(paths) > 1:
            dlg = BatchRenameDialog(paths, self)
            dlg.exec()
            return

        path = paths
        if path == self.current_dir:
            return
        old_name = os.path.basename(path)
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=old_name)
        if ok and new_name.strip() and new_name != old_name:
            new_path = os.path.join(os.path.dirname(path), new_name.strip())
            try:
                 os.rename(path, new_path)
            except Exception as e:
                QMessageBox.critical(self, "Rename Error", str(e))

    def batch_rename_selected(self):
        paths = self.selected_paths()
        if not paths:
            QMessageBox.information(self, "Batch Rename", "Select one or more files/folders first (Ctrl+Click or Shift+Click).")
            return
        dlg = BatchRenameDialog(paths, self)
        dlg.exec()

    def delete_selected(self, permanent=False):
        paths = self.selected_paths()
        if not paths:
            return
        mode_label = "PERMANENTLY delete" if permanent else "move to Trash"
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to {mode_label} {len(paths)} item(s)?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        for p in paths:
            try:
                if permanent:
                    shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
                else:
                    send2trash(p)
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Failed on {os.path.basename(p)}:\n{e}")

    def create_new_folder(self):
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:", text="New Folder")
        if ok and name.strip():
            try:
                os.makedirs(os.path.join(self.current_dir, name.strip()), exist_ok=False)
            except Exception as e:
                QMessageBox.critical(self, "New Folder Error", str(e))

    def create_new_file(self):
        name, ok = QInputDialog.getText(self, "New Empty File", "File name:", text="untitled.txt")
        if ok and name.strip():
            target = os.path.join(self.current_dir, name.strip())
            try:
                with open(target, "x", encoding="utf-8"):
                    pass
            except Exception as e:
                QMessageBox.critical(self, "New File Error", str(e))

    # --- Navigation & Views ---
    def switch_view_mode(self, idx):
        self.stack.setCurrentIndex(idx)
        self.navigate(self.current_dir)

    def navigate(self, path):
        if not path or not os.path.exists(path):
            return
        self.current_dir = os.path.abspath(path)
        # Auto-enable hidden files if user navigates directly into a dot-folder (e.g. via Ctrl+L)
        if any(part.startswith(".") for part in self.current_dir.split(os.sep) if part) and not self.show_hidden:
            self.show_hidden = True
            self.model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot | QDir.AllDirs | QDir.Hidden | QDir.System)
        root_idx = self.model.index(self.current_dir)
        if self.model.canFetchMore(root_idx):
            self.model.fetchMore(root_idx)
        for v in (self.tree_view, self.list_view, self.icon_view, self.column_view):
            v.setRootIndex(root_idx)
        self.title_changed.emit(os.path.basename(self.current_dir) or "/")

    def go_up(self):
        parent = os.path.dirname(self.current_dir)
        if parent and parent != self.current_dir:
            self.navigate(parent)

    def set_show_hidden(self, enabled):
        self.show_hidden = enabled
        base_flags = QDir.AllEntries | QDir.NoDotAndDotDot | QDir.AllDirs
        if enabled:
            self.model.setFilter(base_flags | QDir.Hidden | QDir.System)
        else:
            self.model.setFilter(base_flags)
        self.refresh_view()

    def refresh_view(self):
        current = self.current_dir
        self.model.setRootPath("")
        self.model.setRootPath(QDir.rootPath())
        self.navigate(current)

    def current_path(self):
        if self.stack.currentWidget() == self.search_results:
            item = self.search_results.currentItem()
            return item.data(Qt.UserRole) if item else self.current_dir
        active_view = self.stack.currentWidget()
        idx = active_view.currentIndex()
        return self.model.filePath(idx) if idx.isValid() else self.current_dir

    def on_filter_changed(self, text):
        if text.startswith("find:"):
            query = text[5:].strip().lower()
            self.stack.setCurrentWidget(self.search_results)
            self.search_results.clear()
            if len(query) >= 2:
                count = 0
                for root, dirs, files in os.walk(self.current_dir):
                    for name in dirs + files:
                        if query in name.lower():
                            full = os.path.join(root, name)
                            item = QListWidgetItem(os.path.relpath(full, self.current_dir))
                            item.setData(Qt.UserRole, full)
                            self.search_results.addItem(item)
                            count += 1
                            if count >= 300:
                                return
        else:
            if self.stack.currentWidget() == self.search_results:
                self.stack.setCurrentIndex(self.view_selector.currentIndex())
            self.model.setNameFilters([f"*{text}*"] if text else [])

    def _on_selection(self, current, _prev=None):
        if current and current.isValid():
            path = self.model.filePath(current)
            if path:
                self.file_selected.emit(path)

    def _on_double_click(self, index):
        index = index.siblingAtColumn(0)
        path = self.model.filePath(index)
        if os.path.isdir(path):
            self.navigate(path)
        elif is_archive(path):
            extracted = self.archive_manager.open_archive(path, self)
            self.navigate(extracted)

    def _on_search_item_selected(self, current, _prev):
        if current:
            self.file_selected.emit(current.data(Qt.UserRole))

    def _on_search_item_activated(self, item):
        path = item.data(Qt.UserRole)
        if os.path.isdir(path):
            self.filter_input.clear()
            self.navigate(path)

    def _show_context_menu(self, view, pos):
        index = view.indexAt(pos)
        clicked_on_item = index.isValid()

        # Ensure right-clicking an item selects it first so Rename/Delete/Copy target the right item
        if clicked_on_item:
            view.setCurrentIndex(index)
            target_path = self.model.filePath(index)
        else:
            target_path = self.current_dir

        menu = QMenu(self)

        if clicked_on_item:
            if os.path.isdir(target_path):
                menu.addAction("Open Folder", lambda: self.navigate(target_path))
                menu.addAction("Open Folder in New Tab", lambda: self.open_in_new_tab.emit(target_path))
            else:
                menu.addAction("Open File (Default App)", lambda: subprocess.Popen(["xdg-open", target_path]))
                menu.addAction("Edit in Sublime Text / Editor", lambda: self._open_in_editor(target_path))
                if is_archive(target_path):
                    menu.addAction("Browse Archive as Folder", lambda: self.navigate(self.archive_manager.open_archive(target_path, self)))

            menu.addSeparator()
            menu.addAction("Cut (Ctrl+X)", self.cut_selected)
            menu.addAction("Copy (Ctrl+C)", self.copy_selected)

        if FILE_CLIPBOARD["paths"]:
            menu.addAction("Paste (%d item(s)) (Ctrl+V)" % len(FILE_CLIPBOARD["paths"]), self.paste_items)

        menu.addSeparator()
        menu.addAction("Refresh (F5)", self.refresh_view)
        menu.addAction("New Folder... (Ctrl+Shift+N)", self.create_new_folder)
        menu.addAction("New Empty File...", self.create_new_file)

        if clicked_on_item:
            menu.addSeparator()
            menu.addAction("Rename... (F2)", self.rename_selected)
            menu.addAction("Move to Trash (Del)", lambda: self.delete_selected(permanent=False))
            menu.addAction("Delete Permanently (Shift+Del)", lambda: self.delete_selected(permanent=True))
            menu.addAction("Rename... (F2)", self.rename_selected)
            menu.addAction("Batch Rename... (Ctrl+Shift+R)", self.batch_rename_selected)

        menu.addSeparator()
        term_dir = target_path if os.path.isdir(target_path) else os.path.dirname(target_path)
        menu.addAction("Open Terminal Here", lambda: subprocess.Popen(["xfce4-terminal", "--working-directory", term_dir]))
        menu.addAction("Copy Full Path", lambda: QApplication.clipboard().setText(target_path))

        menu.exec(view.viewport().mapToGlobal(pos))

    def _open_in_editor(self, path):
        for editor in ("subl", "xed", "mousepad", "code", "nano"):
            if shutil.which(editor):
                if editor == "nano":
                    subprocess.Popen(["xfce4-terminal", "-e", f"nano '{path}'"])
                else:
                    subprocess.Popen([editor, path])
                return
        subprocess.Popen(["xdg-open", path])
```
