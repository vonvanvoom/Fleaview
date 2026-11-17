# `main.py`

**Role:** Main Window, Menus, Status Bar & Command Palette

## Source Code

```python
import json
import os
import sys

os.environ["QT_FFMPEG_DECODING_HW_DEVICE_TYPES"] = ""
os.environ["QT_MEDIA_BACKEND"] = "ffmpeg"

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QInputDialog, QMessageBox
)
from about import AboutDialog
from archive_fs import ArchiveManager
from inspector import InspectorPane
from media_tools import FFmpegMediaDialog
from sidebar import KeyboardSidebar
from workspace import WorkspaceManager


HOTKEYS_FILE = os.path.expanduser("~/.config/fleaview/hotkeys.json")


class FleaMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fleaview File Manager")
        self.resize(1440, 880)

        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.archive_manager = ArchiveManager()
        self.sidebar = KeyboardSidebar()
        self.workspace = WorkspaceManager(self.archive_manager)
        self.inspector = InspectorPane()

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(self.sidebar)
        main_splitter.addWidget(self.workspace)
        main_splitter.addWidget(self.inspector)
        main_splitter.setSizes([220, 700, 520])
        self.setCentralWidget(main_splitter)

        self.sidebar.path_activated.connect(self._navigate_active)
        self.workspace.active_file_changed.connect(self.inspector.inspect_path)
        self.workspace.active_file_changed.connect(self.update_status_bar)
        self.statusBar().showMessage("Ready")

        self.hotkeys = self._load_hotkeys()
        self._build_menus()

    def _load_hotkeys(self):
        defaults = {
            "new_tab": "Ctrl+T",
            "split_horizontal": "F3",
            "split_vertical": "Shift+F3",
            "move_tab_pane": "Ctrl+Alt+Right",
            "command_palette": "Ctrl+Shift+P",
            "go_to": "Ctrl+L",
            "focus_sidebar": "Alt+Q",
            "ffmpeg_studio": "Ctrl+M",
            "inspect_hex": "Ctrl+Shift+H",
            "disk_treemap": "Ctrl+D",
            "filter_preview": "Alt+Shift+F",
        }
        if os.path.exists(HOTKEYS_FILE):
            with open(HOTKEYS_FILE, "r") as f:
                defaults.update(json.load(f))
        return defaults

    def _navigate_active(self, path):
        browser = self.workspace.active_browser()
        if browser:
            browser.navigate(path)

    def toggle_hidden_files(self, checked):
        for group in (self.workspace.left_tabs, self.workspace.right_tabs):
            for i in range(group.count()):
                tab = group.widget(i)
                if hasattr(tab, "set_show_hidden"):
                    tab.set_show_hidden(checked)

    def refresh_active_browser(self):
        browser = self.workspace.active_browser()
        if browser:
            browser.refresh_view()

    def _format_size(self, num_bytes):
        raw = num_bytes
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if num_bytes < 1024.0:
                if unit == "B":
                    return f"{int(raw)} bytes"
                return f"{num_bytes:.1f} {unit} ({raw:,} bytes)"
            num_bytes /= 1024.0
        return f"{num_bytes:.1f} PiB"

    def update_status_bar(self, path):
        if not path or not os.path.exists(path):
            self.statusBar().clearMessage()
            return

        name = os.path.basename(path) or path
        if os.path.isdir(path):
            try:
                count = len(os.listdir(path))
                self.statusBar().showMessage(f'"{name}"  |  {count} items  |  Folder')
            except PermissionError:
                self.statusBar().showMessage(f'"{name}"  |  Folder (Permission Denied)')
        else:
            size_str = self._format_size(os.path.getsize(path))
            ext = os.path.splitext(path)[1].lstrip(".").upper()
            file_type = f"{ext} file" if ext else "File"
            self.statusBar().showMessage(f'"{name}"  |  {size_str}  |  {file_type}')

    def _build_menus(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        file_menu.addAction(QAction("New &Tab", self, shortcut=self.hotkeys["new_tab"], triggered=lambda: self.workspace.add_tab(os.path.expanduser("~"))))
        file_menu.addAction(QAction("New &Folder...", self, triggered=lambda: self.workspace.active_browser().create_new_folder()))
        file_menu.addAction(QAction("New &Empty File...", self, triggered=lambda: self.workspace.active_browser().create_new_file()))
        file_menu.addSeparator()
        file_menu.addAction(QAction("&Open Selected", self, triggered=lambda: self.workspace.active_browser().open_selected()))
        file_menu.addAction(QAction("&FFmpeg Media Studio...", self, shortcut=self.hotkeys["ffmpeg_studio"], triggered=self.open_ffmpeg_studio))
        file_menu.addSeparator()
        file_menu.addAction(QAction("&Quit", self, shortcut="Ctrl+Q", triggered=self.close))

        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addAction(QAction("Cu&t", self, triggered=lambda: self.workspace.active_browser().cut_selected()))
        edit_menu.addAction(QAction("&Copy", self, triggered=lambda: self.workspace.active_browser().copy_selected()))
        edit_menu.addAction(QAction("&Paste", self, triggered=lambda: self.workspace.active_browser().paste_items()))
        edit_menu.addAction(QAction("&Rename...", self, triggered=lambda: self.workspace.active_browser().rename_selected()))
        edit_menu.addAction(QAction("&Batch Rename...", self, shortcut="Ctrl+Shift+R", triggered=lambda: self.workspace.active_browser().batch_rename_selected()))
        edit_menu.addAction(QAction("Move to &Trash", self, triggered=lambda: self.workspace.active_browser().delete_selected(permanent=False)))
        edit_menu.addSeparator()
        edit_menu.addAction(QAction("Command &Palette...", self, shortcut=self.hotkeys["command_palette"], triggered=self.open_command_palette))
        edit_menu.addAction(QAction("Filter Lines in Preview", self, shortcut=self.hotkeys["filter_preview"], triggered=lambda: (self.inspector.filter_bar.show(), self.inspector.filter_bar.setFocus())))

        view_menu = menubar.addMenu("&View")
        self.hidden_act = QAction("Show &Hidden Files", self, shortcut="Ctrl+H", checkable=True)
        self.hidden_act.toggled.connect(self.toggle_hidden_files)
        view_menu.addAction(self.hidden_act)
        view_menu.addAction(QAction("&Refresh", self, shortcut="F5", triggered=self.refresh_active_browser))
        view_menu.addAction(QAction("Toggle Image &Slideshow (4s)", self, shortcut="F6", triggered=lambda: self.inspector.slide_btn.toggle()))
        view_menu.addSeparator()
        view_menu.addAction(QAction("Split Side-by-Side", self, shortcut=self.hotkeys["split_horizontal"], triggered=lambda: self.workspace.toggle_split(Qt.Horizontal)))
        view_menu.addAction(QAction("Split Stacked", self, shortcut=self.hotkeys["split_vertical"], triggered=lambda: self.workspace.toggle_split(Qt.Vertical)))
        view_menu.addAction(QAction("Move Tab to Other Pane", self, shortcut=self.hotkeys["move_tab_pane"], triggered=self.workspace.move_tab_to_other_pane))
        view_menu.addSeparator()
        view_menu.addAction(QAction("Save Workspace Layout...", self, triggered=self.workspace.save_layout_dialog))
        view_menu.addAction(QAction("Restore Workspace Layout...", self, triggered=self.workspace.restore_layout_dialog))
        view_menu.addSeparator()
        view_menu.addAction(QAction("Inspect as Hex", self, shortcut=self.hotkeys["inspect_hex"], triggered=lambda: self.inspector.inspect_path(self.workspace.active_browser().current_path(), force_hex=True)))
        view_menu.addAction(QAction("Folder Disk Treemap", self, shortcut=self.hotkeys["disk_treemap"], triggered=lambda: self.inspector.inspect_path(self.workspace.active_browser().current_path(), show_treemap=True)))

        go_menu = menubar.addMenu("&Go")
        go_menu.addAction(QAction("&Open Location...", self, shortcut=self.hotkeys["go_to"], triggered=self.open_goto_dialog))
        go_menu.addAction(QAction("Focus &Sidebar", self, shortcut=self.hotkeys["focus_sidebar"], triggered=self.sidebar.setFocus))

        help_menu = menubar.addMenu("&Help")
        help_menu.addAction(QAction("&About Fleaview...", self, shortcut="F1", triggered=self.open_about_dialog))

    def open_goto_dialog(self):
        raw, ok = QInputDialog.getText(self, "Go To Path", "Path (~ and $ENV supported):")
        if ok and raw:
            expanded = os.path.expandvars(os.path.expanduser(raw.strip()))
            if os.path.isdir(expanded):
                self._navigate_active(expanded)
            elif os.path.isfile(expanded):
                self._navigate_active(os.path.dirname(expanded))
                self.inspector.inspect_path(expanded)

    def open_command_palette(self):
        commands = {
            "File: New Folder": lambda: self.workspace.active_browser().create_new_folder(),
            "File: New Empty File": lambda: self.workspace.active_browser().create_new_file(),
            "Edit: Rename Selected": lambda: self.workspace.active_browser().rename_selected(),
            "Edit: Batch Rename Selected": lambda: self.workspace.active_browser().batch_rename_selected(),
            "Edit: Move Selected to Trash": lambda: self.workspace.active_browser().delete_selected(permanent=False),
            "Split Pane: Side-by-Side": lambda: self.workspace.toggle_split(Qt.Horizontal),
            "Split Pane: Stacked": lambda: self.workspace.toggle_split(Qt.Vertical),
            "Tab: Move Active Tab to Other Pane": self.workspace.move_tab_to_other_pane,
            "Layout: Save Current Workspace": self.workspace.save_layout_dialog,
            "Layout: Restore Saved Workspace": self.workspace.restore_layout_dialog,
            "Media: Open FFmpeg Convert / Rotate / Resize / Flip": self.open_ffmpeg_studio,
            "Inspector: View File as Hex": lambda: self.inspector.inspect_path(self.workspace.active_browser().current_path(), force_hex=True),
            "Inspector: Folder Space Treemap": lambda: self.inspector.inspect_path(self.workspace.active_browser().current_path(), show_treemap=True),
            "Navigation: Go To Path": self.open_goto_dialog,
            "Sidebar: Focus Keyboard Sidebar": self.sidebar.setFocus,
        }
        choice, ok = QInputDialog.getItem(self, "Command Palette", "Run command:", list(commands.keys()), 0, False)
        if ok and choice in commands:
            commands[choice]()

    def open_ffmpeg_studio(self):
        browser = self.workspace.active_browser()
        path = browser.current_path() if browser else None
        if not path or os.path.isdir(path):
            QMessageBox.warning(self, "FFmpeg Media Studio", "Select an image or video file first.")
            return
        dlg = FFmpegMediaDialog(path, self)
        dlg.exec()

    def open_about_dialog(self):
        dlg = AboutDialog(self)
        dlg.exec()

    def closeEvent(self, event):
        self.archive_manager.cleanup()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = FleaMainWindow()
    win.show()
    sys.exit(app.exec())
```
