import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QInputDialog


class KeyboardSidebar(QTreeWidget):
    path_activated = Signal(str)

    def __init__(self):
        super().__init__()
        self.setHeaderHidden(True)
        self.setStyleSheet("QTreeWidget { background: #181825; color: #cdd6f4; border: none; }")
        self._populate_defaults()
        self.itemActivated.connect(self._on_activate)

    def _populate_defaults(self):
        places = QTreeWidgetItem(self, ["Places"])
        home = os.path.expanduser("~")
        for label, sub in [("Home", ""), ("Desktop", "Desktop"), ("Documents", "Documents"), ("Downloads", "Downloads")]:
            item = QTreeWidgetItem(places, [label])
            item.setData(0, Qt.UserRole, os.path.join(home, sub))
        places.setExpanded(True)

        drives = QTreeWidgetItem(self, ["Devices & Mounts"])
        root_item = QTreeWidgetItem(drives, ["File System (/)"])
        root_item.setData(0, Qt.UserRole, "/")
        if os.path.exists("/media"):
            try:
                user_dirs = os.listdir("/media")
            except PermissionError:
                user_dirs = []
            for user_dir in user_dirs:
                full_user = os.path.join("/media", user_dir)
                if os.path.isdir(full_user):
                    try:
                        mounts = os.listdir(full_user)
                    except PermissionError:
                        continue
                    for mnt in mounts:
                        m_item = QTreeWidgetItem(drives, [mnt])
                        m_item.setData(0, Qt.UserRole, os.path.join(full_user, mnt))
        drives.setExpanded(True)

    def _on_activate(self, item, _col):
        target = item.data(0, Qt.UserRole)
        if target and os.path.exists(target):
            self.path_activated.emit(target)

    def keyPressEvent(self, event):
        item = self.currentItem()
        if not item:
            return super().keyPressEvent(event)

        # Alt+Up / Alt+Down to reorder bookmarks & places
        if event.modifiers() == Qt.AltModifier and event.key() in (Qt.Key_Up, Qt.Key_Down):
            parent = item.parent()
            if parent:
                idx = parent.indexOfChild(item)
                new_idx = idx - 1 if event.key() == Qt.Key_Up else idx + 1
                if 0 <= new_idx < parent.childCount():
                    parent.takeChild(idx)
                    parent.insertChild(new_idx, item)
                    self.setCurrentItem(item)
            return

        # F2 to rename bookmark label
        if event.key() == Qt.Key_F2:
            new_name, ok = QInputDialog.getText(self, "Rename Place", "Label:", text=item.text(0))
            if ok and new_name:
                item.setText(0, new_name)
            return

        # Delete to remove bookmark
        if event.key() == Qt.Key_Delete and item.parent():
            item.parent().removeChild(item)
            return

        super().keyPressEvent(event)
