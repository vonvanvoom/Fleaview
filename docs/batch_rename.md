# `batch_rename.py`

**Role:** Live-Preview Batch File Renamer with Regex & Counters

## Source Code

```python
import os
import re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QSpinBox, QCheckBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox
)


class BatchRenameDialog(QDialog):
    def __init__(self, paths, parent=None):
        super().__init__(parent)
        self.paths = [p for p in paths if os.path.exists(p)]
        self.setWindowTitle(f"Batch Rename ({len(self.paths)} items)")
        self.resize(720, 500)

        layout = QVBoxLayout(self)

        # Row 1: Find & Replace + Regex Toggle
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Find:"))
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Text or regex pattern (e.g. ^IMG_(\\d+))...")
        row1.addWidget(self.find_input)

        row1.addWidget(QLabel("Replace with:"))
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replacement (supports \\1, \\2 in regex)...")
        row1.addWidget(self.replace_input)

        self.regex_check = QCheckBox("Use Regex")
        self.regex_check.setToolTip("Enable Python regular expressions (e.g. Find: '(\\d+)', Replace: 'Part_\\1')")
        row1.addWidget(self.regex_check)

        self.case_ins_check = QCheckBox("Ignore Case")
        row1.addWidget(self.case_ins_check)
        layout.addLayout(row1)

        # Row 2: Prefix & Suffix
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Prefix:"))
        self.prefix_input = QLineEdit()
        row2.addWidget(self.prefix_input)

        row2.addWidget(QLabel("Suffix (before ext):"))
        self.suffix_input = QLineEdit()
        row2.addWidget(self.suffix_input)
        layout.addLayout(row2)

        # Row 3: Numbering & Case Options
        row3 = QHBoxLayout()
        self.num_check = QCheckBox("Append Counter")
        row3.addWidget(self.num_check)

        row3.addWidget(QLabel("Start:"))
        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, 99999)
        self.start_spin.setValue(1)
        row3.addWidget(self.start_spin)

        row3.addWidget(QLabel("Digits:"))
        self.pad_spin = QSpinBox()
        self.pad_spin.setRange(1, 6)
        self.pad_spin.setValue(3)
        row3.addWidget(self.pad_spin)

        row3.addWidget(QLabel("Case:"))
        self.case_box = QComboBox()
        self.case_box.addItems(["Keep Original", "lowercase", "UPPERCASE", "Title Case"])
        row3.addWidget(self.case_box)
        layout.addLayout(row3)

        # Status Label for Regex Validation
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #f38ba8;")
        self.status_lbl.hide()
        layout.addWidget(self.status_lbl)

        # Live Preview Table (Original -> New Name)
        self.table = QTableWidget(len(self.paths), 2)
        self.table.setHorizontalHeaderLabels(["Current Name", "New Name (Preview)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        # Action Buttons
        btn_row = QHBoxLayout()
        apply_btn = QPushButton("Apply Rename")
        apply_btn.clicked.connect(self.apply_renames)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

        # Connect live preview triggers
        for w in (self.find_input, self.replace_input, self.prefix_input, self.suffix_input):
            w.textChanged.connect(self.update_preview)
        self.regex_check.toggled.connect(self.update_preview)
        self.case_ins_check.toggled.connect(self.update_preview)
        self.num_check.toggled.connect(self.update_preview)
        self.start_spin.valueChanged.connect(self.update_preview)
        self.pad_spin.valueChanged.connect(self.update_preview)
        self.case_box.currentIndexChanged.connect(self.update_preview)

        self.preview_map = []
        self.update_preview()

    def _compute_new_name(self, old_name, index, compiled_re=None):
        is_dir = os.path.isdir(self.paths[index])
        if is_dir:
            stem, ext = old_name, ""
        else:
            stem, ext = os.path.splitext(old_name)

        find_txt = self.find_input.text()
        repl_txt = self.replace_input.text()

        if find_txt:
            if self.regex_check.isChecked():
                if compiled_re is not None:
                    try:
                        stem = compiled_re.sub(repl_txt, stem)
                    except re.error:
                        pass
            else:
                if self.case_ins_check.isChecked():
                    stem = re.sub(re.escape(find_txt), lambda _: repl_txt, stem, flags=re.IGNORECASE)
                else:
                    stem = stem.replace(find_txt, repl_txt)

        stem = f"{self.prefix_input.text()}{stem}{self.suffix_input.text()}"

        if self.num_check.isChecked():
            num = self.start_spin.value() + index
            pad = self.pad_spin.value()
            stem = f"{stem}_{str(num).zfill(pad)}"

        case_mode = self.case_box.currentText()
        if case_mode == "lowercase":
            stem = stem.lower()
            ext = ext.lower()
        elif case_mode == "UPPERCASE":
            stem = stem.upper()
            ext = ext.upper()
        elif case_mode == "Title Case":
            stem = stem.title()

        return f"{stem}{ext}"

    def update_preview(self):
        self.preview_map = []
        compiled_re = None
        find_txt = self.find_input.text()

        if self.regex_check.isChecked() and find_txt:
            flags = re.IGNORECASE if self.case_ins_check.isChecked() else 0
            try:
                compiled_re = re.compile(find_txt, flags)
                self.status_lbl.hide()
            except re.error as e:
                self.status_lbl.setText(f"Regex syntax warning: {e}")
                self.status_lbl.show()
        else:
            self.status_lbl.hide()

        for i, path in enumerate(self.paths):
            old_name = os.path.basename(path)
            new_name = self._compute_new_name(old_name, i, compiled_re)
            self.preview_map.append((path, os.path.join(os.path.dirname(path), new_name)))

            self.table.setItem(i, 0, QTableWidgetItem(old_name))
            new_item = QTableWidgetItem(new_name)
            if new_name != old_name:
                new_item.setForeground(Qt.cyan)
            self.table.setItem(i, 1, new_item)

    def apply_renames(self):
        changes = [(src, dst) for src, dst in self.preview_map if src != dst]
        if not changes:
            self.accept()
            return

        targets = [dst for _, dst in changes]
        if len(targets) != len(set(targets)):
            QMessageBox.warning(self, "Name Collision", "Two or more items would end up with the exact same name.")
            return

        errors = []
        for src, dst in changes:
            try:
                if os.path.exists(dst):
                    errors.append(f"Already exists: {os.path.basename(dst)}")
                else:
                    os.rename(src, dst)
            except Exception as e:
                errors.append(f"{os.path.basename(src)}: {e}")

        if errors:
            QMessageBox.warning(self, "Rename Issues", "\n".join(errors[:15]))
        self.accept()
```
