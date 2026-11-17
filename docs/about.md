# `about.py`

**Role:** About Dialog, Logo Banner & Shortcut Reference

## Source Code

```python
import os
import sys
import platform
import shutil
import PySide6
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit
)


APP_NAME = "Fleaview Manager"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Von Van Vooom, 2026"
APP_URL = "https://github.com/vonvanvoom/Fleaview"
APP_LICENSE = "MIT License"
APP_DESCRIPTION = (
    "A standalone, keyboard-first file manager for Linux built with Python, "
    "PySide6, PyVista, and FFmpeg."
)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.resize(480, 480)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # App Logo Banner (Loads icon.png from folder or PyInstaller bundle)
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, "icon.png")
        if os.path.exists(icon_path):
            logo_lbl = QLabel()
            pix = QPixmap(icon_path).scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
            logo_lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(logo_lbl)

        # Title & Version
        title_lbl = QLabel(f"{APP_NAME}  v{APP_VERSION}")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_lbl.setFont(title_font)
        title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_lbl)

        # Description & Clickable Author Hyperlink
        desc_lbl = QLabel(
            f"{APP_DESCRIPTION}<br><br>"
            f"Author: <a href='{APP_URL}' style='color: #89b4fa;'>{APP_AUTHOR}</a>"
            f" &nbsp;|&nbsp; License: {APP_LICENSE}"
        )
        desc_lbl.setTextFormat(Qt.RichText)
        desc_lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
        desc_lbl.setOpenExternalLinks(True)
        desc_lbl.setWordWrap(True)
        desc_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc_lbl)

        # System Info & Shortcut Quick Reference
        ffmpeg_status = "Installed" if shutil.which("ffmpeg") else "Not Found"
        info_box = QTextEdit()
        info_box.setReadOnly(True)
        info_box.setPlainText(
            "=== Runtime Environment ===\n"
            f"OS: {platform.system()} {platform.release()} ({platform.machine()})\n"
            f"Python: {platform.python_version()}\n"
            f"PySide6 (Qt): {PySide6.__version__}\n"
            f"FFmpeg Backend: {ffmpeg_status}\n\n"
            "=== Key Shortcuts ===\n"
            "Ctrl+T            New Tab\n"
            "F3 / Shift+F3     Toggle Split Pane (Side-by-Side / Stacked)\n"
            "Alt+Q             Focus Keyboard Sidebar\n"
            "Ctrl+L            Go To Path\n"
            "Ctrl+Shift+P      Command Palette\n"
            "Ctrl+M            FFmpeg Media Studio (Convert/Rotate/Flip/Resize)\n"
            "Ctrl+H            Inspect File as Hex\n"
            "Ctrl+D            Folder Space Treemap\n"
            "Alt+Shift+F       Filter Lines in Preview\n"
            "F2 / Ctrl+Shift+R Rename / Batch Rename (Regex)\n"
            "Del               Move to Trash"
        )
        layout.addWidget(info_box)

        # Close Button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
```
