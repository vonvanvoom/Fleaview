# `media_tools.py`

**Role:** FFmpeg Image & Video Conversion, Rotate, Flip & Resize Studio

## Source Code

```python
import os
import shutil
import subprocess
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QMessageBox
)


class FFmpegMediaDialog(QDialog):
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle(f"FFmpeg Media Studio — {os.path.basename(file_path)}")
        self.resize(440, 260)

        layout = QVBoxLayout(self)

        # Output Format
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Convert Format:"))
        self.format_box = QComboBox()
        self.format_box.addItems([
            "Keep Original Extension",
            "PNG Image (.png)",
            "JPEG Image (.jpg)",
            "Animated / Static GIF (.gif)",
            "WebP Image (.webp)",
            "MP4 Video H.264 (.mp4)",
            "WebM Video (.webm)",
        ])
        fmt_row.addWidget(self.format_box)
        layout.addLayout(fmt_row)

        # Rotation & Flip
        rot_row = QHBoxLayout()
        rot_row.addWidget(QLabel("Rotate / Flip:"))
        self.transform_box = QComboBox()
        self.transform_box.addItems([
            "None",
            "Rotate 90° Clockwise",
            "Rotate 90° Counter-Clockwise",
            "Rotate 180°",
            "Flip Horizontal (Mirror)",
            "Flip Vertical",
        ])
        rot_row.addWidget(self.transform_box)
        layout.addLayout(rot_row)

        # Resize
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Resize (e.g. 50%, 1280:-1, 800:600):"))
        self.resize_input = QLineEdit()
        self.resize_input.setPlaceholderText("Leave blank to keep original size")
        size_row.addWidget(self.resize_input)
        layout.addLayout(size_row)

        # Run Button
        run_btn = QPushButton("Process with FFmpeg")
        run_btn.clicked.connect(self.run_ffmpeg)
        layout.addWidget(run_btn)

    def run_ffmpeg(self):
        if not shutil.which("ffmpeg"):
            QMessageBox.critical(self, "Missing FFmpeg", "FFmpeg is not installed. Run: sudo apt install ffmpeg")
            return

        base, orig_ext = os.path.splitext(self.file_path)
        ext_map = {
            "Keep Original Extension": orig_ext,
            "PNG Image (.png)": ".png",
            "JPEG Image (.jpg)": ".jpg",
            "Animated / Static GIF (.gif)": ".gif",
            "WebP Image (.webp)": ".webp",
            "MP4 Video H.264 (.mp4)": ".mp4",
            "WebM Video (.webm)": ".webm",
        }
        out_ext = ext_map[self.format_box.currentText()]
        out_path = f"{base}_edited{out_ext}"

        vf_filters = []
        transform = self.transform_box.currentText()
        if "90° Clockwise" in transform:
            vf_filters.append("transpose=1")
        elif "90° Counter-Clockwise" in transform:
            vf_filters.append("transpose=2")
        elif "180°" in transform:
            vf_filters.append("transpose=2,transpose=2")
        elif "Flip Horizontal" in transform:
            vf_filters.append("hflip")
        elif "Flip Vertical" in transform:
            vf_filters.append("vflip")

        resize_val = self.resize_input.text().strip()
        if resize_val:
            if resize_val.endswith("%"):
                pct = float(resize_val[:-1]) / 100.0
                vf_filters.append(f"scale=trunc(iw*{pct}/2)*2:trunc(ih*{pct}/2)*2")
            else:
                vf_filters.append(f"scale={resize_val}")

        cmd = ["ffmpeg", "-y", "-i", self.file_path]
        if vf_filters:
            cmd += ["-vf", ",".join(vf_filters)]
        cmd.append(out_path)

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            QMessageBox.information(self, "Success", f"Saved output to:\n{out_path}")
            self.accept()
        else:
            QMessageBox.critical(self, "FFmpeg Error", res.stderr[-600:])
```
