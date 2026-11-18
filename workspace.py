import json
import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSplitter, QTabWidget, QInputDialog
from browser_pane import BrowserTab


LAYOUT_FILE = os.path.expanduser("~/.config/fleaview/layouts.json")


class WorkspaceManager(QSplitter):
    active_file_changed = Signal(str)

    def __init__(self, archive_manager):
        super().__init__(Qt.Horizontal)
        self.archive_manager = archive_manager

        self.left_tabs = self._make_tab_widget()
        self.right_tabs = self._make_tab_widget()
        self.right_tabs.hide()

        self.addWidget(self.left_tabs)
        self.addWidget(self.right_tabs)

        self.add_tab(os.path.expanduser("~"), target_group=self.left_tabs)
        self.add_tab(os.path.expanduser("~"), target_group=self.right_tabs)

    def _make_tab_widget(self):
        tabs = QTabWidget()
        tabs.setTabsClosable(True)
        tabs.setMovable(True)
        tabs.tabCloseRequested.connect(lambda i, t=tabs: self._close_tab(t, i))
        return tabs

    def _close_tab(self, tabs, index):
        if tabs.count() > 1:
            widget = tabs.widget(index)
            tabs.removeTab(index)
            if widget:
                widget.deleteLater()
        else:
            # If closing the last tab in the right split pane, hide the split pane
            if tabs == self.right_tabs and self.right_tabs.isVisible():
                self.right_tabs.hide()
            else:
                # Reset the single remaining tab to Home
                tabs.widget(0).navigate(os.path.expanduser("~"))

    def add_tab(self, path, target_group=None):
        group = target_group or self.active_tab_group()
        tab = BrowserTab(path, self.archive_manager)
        tab.file_selected.connect(self.active_file_changed.emit)
        tab.open_in_new_tab.connect(lambda p, g=group: self.add_tab(p, g))
        idx = group.addTab(tab, os.path.basename(path) or "/")
        tab.title_changed.connect(lambda title, t=tab, g=group: g.setTabText(g.indexOf(t), title))
        group.setCurrentIndex(idx)
        return tab

    def active_tab_group(self):
        if self.right_tabs.isVisible() and self.right_tabs.hasFocus():
            return self.right_tabs
        return self.left_tabs

    def active_browser(self):
        return self.active_tab_group().currentWidget()

    def move_tab_to_other_pane(self):
        src = self.active_tab_group()
        dst = self.right_tabs if src == self.left_tabs else self.left_tabs
        if not dst.isVisible():
            dst.show()
        if src.count() <= 1:
            return
        idx = src.currentIndex()
        widget = src.widget(idx)
        title = src.tabText(idx)
        src.removeTab(idx)
        new_idx = dst.addTab(widget, title)
        dst.setCurrentIndex(new_idx)

    def toggle_split(self, orientation=Qt.Horizontal):
        self.setOrientation(orientation)
        self.right_tabs.setVisible(not self.right_tabs.isVisible())

    def save_layout_dialog(self):
        name, ok = QInputDialog.getText(self, "Save Workspace Layout", "Layout name:")
        if not ok or not name.strip():
            return
        os.makedirs(os.path.dirname(LAYOUT_FILE), exist_ok=True)
        data = self._load_all_layouts()
        data[name.strip()] = {
            "split_visible": self.right_tabs.isVisible(),
            "orientation": "horizontal" if self.orientation() == Qt.Horizontal else "vertical",
            "left_tabs": [self.left_tabs.widget(i).current_dir for i in range(self.left_tabs.count())],
            "right_tabs": [self.right_tabs.widget(i).current_dir for i in range(self.right_tabs.count())],
        }
        with open(LAYOUT_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def restore_layout_dialog(self):
        data = self._load_all_layouts()
        if not data:
            return
        choice, ok = QInputDialog.getItem(self, "Restore Layout", "Choose layout:", list(data.keys()), 0, False)
        if not ok or choice not in data:
            return
        cfg = data[choice]
        self.setOrientation(Qt.Horizontal if cfg.get("orientation") == "horizontal" else Qt.Vertical)
        self.right_tabs.setVisible(cfg.get("split_visible", False))

        self.left_tabs.clear()
        for p in cfg.get("left_tabs", [os.path.expanduser("~")]):
            self.add_tab(p, self.left_tabs)

        self.right_tabs.clear()
        for p in cfg.get("right_tabs", [os.path.expanduser("~")]):
            self.add_tab(p, self.right_tabs)

    def _load_all_layouts(self):
        if os.path.exists(LAYOUT_FILE):
            with open(LAYOUT_FILE, "r") as f:
                return json.load(f)
        return {}
