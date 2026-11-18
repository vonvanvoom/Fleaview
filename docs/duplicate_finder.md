# `duplicate_finder.py`

**Role:** SHA-256 Duplicate File Scanner & Safe Trash Cleanup

## Source Code

```python
import hashlib
import os
from collections import defaultdict
from send2trash import send2trash
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QCheckBox, QMessageBox, QApplication
)


class DuplicateFinderDialog(QDialog):
    def __init__(self, folder_path, parent=None):
        super().__init__(parent)
        self.folder_path = os.path.abspath(folder_path)
        self.setWindowTitle(f"Find Duplicate Files — {os.path.basename(self.folder_path) or '/'}")
        self.resize(780, 520)

        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        self.recursive_check = QCheckBox("Include Subfolders")
        self.recursive_check.setChecked(True)
        self.scan_btn = QPushButton("Scan Now")
        self.scan_btn.clicked.connect(self.run_scan)
        self.status_lbl = QLabel(f"Target: {self.folder_path}")

        top_bar.addWidget(self.recursive_check)
        top_bar.addWidget(self.scan_btn)
        top_bar.addSpacing(12)
        top_bar.addWidget(self.status_lbl, 1)
        layout.addLayout(top_bar)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["File / Group", "Size", "Full Path"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self.tree)

        btn_bar = QHBoxLayout()
        self.auto_select_btn = QPushButton("Auto-Check Copies (Keep First)")
        self.auto_select_btn.clicked.connect(self.auto_check_copies)
        self.trash_btn = QPushButton("Move Checked to Trash")
        self.trash_btn.clicked.connect(self.trash_checked)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)

        btn_bar.addWidget(self.auto_select_btn)
        btn_bar.addWidget(self.trash_btn)
        btn_bar.addStretch()
        btn_bar.addWidget(close_btn)
        layout.addLayout(btn_bar)

        self.run_scan()

    def _hash_file(self, path, chunk_size=65536):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def run_scan(self):
        self.tree.clear()
        self.status_lbl.setText("Scanning file sizes...")
        QApplication.processEvents()

        size_map = defaultdict(list)
        if self.recursive_check.isChecked():
            for root, _, files in os.walk(self.folder_path):
                for name in files:
                    full = os.path.join(root, name)
                    try:
                        if not os.path.islink(full):
                            sz = os.path.getsize(full)
                            if sz > 0:
                                size_map[sz].append(full)
                    except OSError:
                        pass
        else:
            try:
                for name in os.listdir(self.folder_path):
                    full = os.path.join(self.folder_path, name)
                    if os.path.isfile(full) and not os.path.islink(full):
                        sz = os.path.getsize(full)
                        if sz > 0:
                            size_map[sz].append(full)
            except OSError:
                pass

        candidates = {sz: paths for sz, paths in size_map.items() if len(paths) > 1}
        self.status_lbl.setText(f"Hashing {sum(len(v) for v in candidates.values())} candidate files...")
        QApplication.processEvents()

        dup_groups = []
        for sz, paths in sorted(candidates.items(), key=lambda x: x[0], reverse=True):
            hash_map = defaultdict(list)
            for p in paths:
                try:
                    digest = self._hash_file(p)
                    hash_map[digest].append(p)
                except OSError:
                    pass
            for digest, identical in hash_map.items():
                if len(identical) > 1:
                    dup_groups.append((sz, sorted(identical)))

        total_wasted = 0
        for idx, (sz, files) in enumerate(dup_groups, start=1):
            wasted = sz * (len(files) - 1)
            total_wasted += wasted
            kb = sz / 1024.0
            size_txt = f"{kb / 1024.0:.2f} MiB" if kb >= 1024 else f"{kb:.1f} KiB"

            group_item = QTreeWidgetItem([f"Group #{idx} ({len(files)} identical files)", size_txt, ""])
            group_item.setExpanded(True)
            self.tree.addTopLevelItem(group_item)

            for f_idx, fpath in enumerate(files):
                child = QTreeWidgetItem([os.path.basename(fpath), size_txt, fpath])
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Checked if f_idx > 0 else Qt.Unchecked)
                child.setData(0, Qt.UserRole, fpath)
                group_item.addChild(child)

        wasted_mb = total_wasted / (1024 * 1024)
        self.status_lbl.setText(f"Found {len(dup_groups)} duplicate group(s) — {wasted_mb:.2f} MiB reclaimable")

    def auto_check_copies(self):
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            for c in range(group.childCount()):
                group.child(c).setCheckState(0, Qt.Checked if c > 0 else Qt.Unchecked)

    def trash_checked(self):
        to_trash = []
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            for c in range(group.childCount()):
                child = group.child(c)
                if child.checkState(0) == Qt.Checked:
                    to_trash.append(child.data(0, Qt.UserRole))

        if not to_trash:
            QMessageBox.information(self, "No Files Checked", "Check one or more duplicate copies to move to Trash.")
            return

        reply = QMessageBox.question(
            self, "Move Duplicates to Trash",
            f"Move {len(to_trash)} checked duplicate file(s) to Trash?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        for p in to_trash:
            try:
                if os.path.exists(p):
                    send2trash(p)
            except Exception as e:
                QMessageBox.warning(self, "Trash Error", f"Failed on {os.path.basename(p)}: {e}")

        self.run_scan()
```
