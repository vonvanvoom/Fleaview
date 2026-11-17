# `inspector.py`

**Role:** 3D Viewport (.stl/.3mf/.gcode), Syntax Code, PDF, Office, Hex & Media Player

## Source Code

```python
import os
import re
import zipfile
import tarfile
import numpy as np
import trimesh
import pyvista as pv
import pymupdf as fitz
import docx
import openpyxl
from pyvistaqt import QtInteractor
from pygments import lex
from pygments.lexers import get_lexer_for_filename, TextLexer
from pygments.styles import get_style_by_name
from pygments.util import ClassNotFound

from PySide6.QtCore import Qt, QUrl, QEvent
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QImage,
    QSyntaxHighlighter, QTextCharFormat
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QTextEdit, QLabel, QPushButton, QLineEdit, QFrame, QSlider, QScrollArea
)


class PygmentsHighlighter(QSyntaxHighlighter):
    """Applies Pygments syntax highlighting to QTextEdit."""
    def __init__(self, document):
        super().__init__(document)
        self.lexer = TextLexer()
        self.style = get_style_by_name("monokai")
        self._formats = {}

    def set_file(self, filename):
        try:
            self.lexer = get_lexer_for_filename(filename, stripall=False)
        except ClassNotFound:
            self.lexer = TextLexer()
        self.rehighlight()

    def _get_format(self, token):
        if token in self._formats:
            return self._formats[token]

        fmt = QTextCharFormat()
        style_def = self.style.style_for_token(token)
        color_hex = style_def.get("color")
        if color_hex:
            fmt.setForeground(QColor("#" + color_hex))
        if style_def.get("bold"):
            fmt.setFontWeight(QFont.Bold)
        if style_def.get("italic"):
            fmt.setFontItalic(True)

        self._formats[token] = fmt
        return fmt

    def highlightBlock(self, text):
        offset = 0
        code_part = text
        if len(text) >= 7 and text[4:7] == " | ":
            offset = 7
            code_part = text[7:]
            gutter_fmt = QTextCharFormat()
            gutter_fmt.setForeground(QColor("#6c7086"))
            self.setFormat(0, 7, gutter_fmt)

        pos = offset
        for token, value in lex(code_part, self.lexer):
            length = len(value)
            if length > 0:
                self.setFormat(pos, length, self._get_format(token))
                pos += length


class DiskTreemapWidget(QWidget):
    """Visualizes folder/drive space usage as proportional blocks."""
    def __init__(self):
        super().__init__()
        self.items = []

    def scan_folder(self, folder_path):
        entries = []
        try:
            for name in os.listdir(folder_path):
                full = os.path.join(folder_path, name)
                size = self._get_size(full)
                if size > 0:
                    entries.append((name, size, full))
        except PermissionError:
            pass
        entries.sort(key=lambda x: x, reverse=True)
        self.items = entries[:25]
        self.update()

    def _get_size(self, path):
        if os.path.isfile(path):
            return os.path.getsize(path)
        total = 0
        for root, _, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        return total

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        painter.fillRect(rect, QColor("#1e1e2e"))
        if not self.items:
            painter.setPen(Qt.white)
            painter.drawText(rect, Qt.AlignCenter, "No data or empty folder")
            return

        total = sum(x for x in self.items)
        y = 0
        palette = ["#89b4fa", "#a6e3a1", "#f9e2af", "#fab387", "#cba6f7", "#f38ba8"]
        for i, (name, size, _) in enumerate(self.items):
            h = max(18, int((size / total) * rect.height()))
            painter.fillRect(4, y + 2, rect.width() - 8, h - 4, QColor(palette[i % len(palette)]))
            painter.setPen(QColor("#11111b"))
            mb = size / (1024 * 1024)
            painter.drawText(10, y + 16, "%s (%.1f MB)" % (name, mb))
            y += h
            if y >= rect.height():
                break


class InspectorPane(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.meta_bar = QPushButton("▸ File Details")
        self.meta_bar.setCheckable(True)
        self.meta_bar.clicked.connect(self.toggle_details)
        self.meta_panel = QLabel("")
        self.meta_panel.setWordWrap(True)
        self.meta_panel.setStyleSheet("background: #181825; color: #cdd6f4; padding: 6px; border-radius: 4px;")
        self.meta_panel.hide()

        self.filter_bar = QLineEdit()
        self.filter_bar.setPlaceholderText("Filter lines in preview (Alt+Shift+F)...")
        self.filter_bar.textChanged.connect(self._filter_text_lines)
        self.filter_bar.hide()

        layout.addWidget(self.meta_bar)
        layout.addWidget(self.meta_panel)
        layout.addWidget(self.filter_bar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # Page 0: Image & PDF Preview with Zoom Controls
        self.img_page = QWidget()
        img_layout = QVBoxLayout(self.img_page)
        img_layout.setContentsMargins(0, 0, 0, 0)

        zoom_bar = QHBoxLayout()
        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setFixedWidth(32)
        self.zoom_out_btn.setToolTip("Zoom Out (Ctrl + Scroll Down)")
        self.zoom_out_btn.clicked.connect(lambda: self._adjust_zoom(0.8))

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedWidth(32)
        self.zoom_in_btn.setToolTip("Zoom In (Ctrl + Scroll Up)")
        self.zoom_in_btn.clicked.connect(lambda: self._adjust_zoom(1.25))

        self.zoom_100_btn = QPushButton("100%")
        self.zoom_100_btn.setFixedWidth(50)
        self.zoom_100_btn.clicked.connect(self._zoom_actual)

        self.zoom_fit_btn = QPushButton("Fit")
        self.zoom_fit_btn.setFixedWidth(45)
        self.zoom_fit_btn.clicked.connect(self._zoom_fit)

        self.zoom_lbl = QLabel("Fit")
        self.zoom_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        zoom_bar.addWidget(self.zoom_out_btn)
        zoom_bar.addWidget(self.zoom_in_btn)
        zoom_bar.addWidget(self.zoom_100_btn)
        zoom_bar.addWidget(self.zoom_fit_btn)
        zoom_bar.addStretch()
        zoom_bar.addWidget(self.zoom_lbl)
        img_layout.addLayout(zoom_bar)

        self.img_scroll = QScrollArea()
        self.img_scroll.setWidgetResizable(True)
        self.img_scroll.setAlignment(Qt.AlignCenter)
        self.img_label = QLabel("Select a file to inspect")
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_scroll.setWidget(self.img_label)
        self.img_scroll.viewport().installEventFilter(self)
        self.img_scroll.viewport().setCursor(Qt.OpenHandCursor)
        self._drag_pos = None
        img_layout.addWidget(self.img_scroll)

        self.current_pixmap = None
        self.zoom_factor = 1.0
        self.fit_mode = True
        self.stack.addWidget(self.img_page)

        # Page 1: Text / Code / Office / Archive / Hex View
        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setFont(QFont("Monospace", 10))
        self.text_view.setStyleSheet("QTextEdit { background: #1e1e2e; color: #cdd6f4; border: none; }")
        self.highlighter = PygmentsHighlighter(self.text_view.document())
        self.raw_text = ""
        self.stack.addWidget(self.text_view)

        # Page 2: Interactive 3D PyVista Viewport
        self.plotter_frame = QFrame()
        p_layout = QVBoxLayout(self.plotter_frame)
        p_layout.setContentsMargins(0, 0, 0, 0)
        self.plotter = QtInteractor(self.plotter_frame)
        self.plotter.set_background("#1e1e2e")
        p_layout.addWidget(self.plotter.interactor)
        self.stack.addWidget(self.plotter_frame)

        # Page 3: Disk Treemap
        self.treemap = DiskTreemapWidget()
        self.stack.addWidget(self.treemap)

        # Page 4: Audio & Video Preview Player with Loop Toggle
        self.media_page = QWidget()
        m_layout = QVBoxLayout(self.media_page)
        m_layout.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QVideoWidget()
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)

        controls = QHBoxLayout()
        self.play_btn = QPushButton("Play / Pause")
        self.play_btn.clicked.connect(self._toggle_playback)

        self.mute_btn = QPushButton("Mute")
        self.mute_btn.setCheckable(True)
        self.mute_btn.toggled.connect(self._toggle_mute)

        self.loop_btn = QPushButton("Loop: Off")
        self.loop_btn.setCheckable(True)
        self.loop_btn.toggled.connect(self._toggle_loop)

        self.time_lbl = QLabel("00:00:00.00 / 00:00:00.00")
        self.time_lbl.setFont(QFont("Monospace", 9))

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.sliderMoved.connect(self.media_player.setPosition)
        self.media_player.positionChanged.connect(self._on_media_position)
        self.media_player.durationChanged.connect(self._on_media_duration)

        controls.addWidget(self.play_btn)
        controls.addWidget(self.mute_btn)
        controls.addWidget(self.loop_btn)
        controls.addWidget(self.seek_slider)
        controls.addWidget(self.time_lbl)

        m_layout.addWidget(self.video_widget)
        m_layout.addLayout(controls)
        self.stack.addWidget(self.media_page)

    def eventFilter(self, obj, event):
        if obj == self.img_scroll.viewport():
            etype = event.type()
            if etype == QEvent.Wheel:
                delta = event.angleDelta().y()
                if delta > 0:
                    self._adjust_zoom(1.15)
                elif delta < 0:
                    self._adjust_zoom(0.85)
                return True
            elif etype == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag_pos = event.position().toPoint()
                self.img_scroll.viewport().setCursor(Qt.ClosedHandCursor)
                return True
            elif etype == QEvent.MouseMove and self._drag_pos is not None:
                delta = event.position().toPoint() - self._drag_pos
                self._drag_pos = event.position().toPoint()
                hbar = self.img_scroll.horizontalScrollBar()
                vbar = self.img_scroll.verticalScrollBar()
                hbar.setValue(hbar.value() - delta.x())
                vbar.setValue(vbar.value() - delta.y())
                return True
            elif etype == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._drag_pos = None
                self.img_scroll.viewport().setCursor(Qt.OpenHandCursor)
                return True
        return super().eventFilter(obj, event)

    def wheelEvent(self, event):
        if self.stack.currentWidget() == self.img_page and event.modifiers() == Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self._adjust_zoom(1.15)
            elif delta < 0:
                self._adjust_zoom(0.85)
            event.accept()
            return
        super().wheelEvent(event)

    def _adjust_zoom(self, multiplier):
        if not self.current_pixmap or self.current_pixmap.isNull():
            return
        if self.fit_mode:
            avail_w = max(200, self.img_scroll.viewport().width() - 16)
            self.zoom_factor = avail_w / max(1, self.current_pixmap.width())
            self.fit_mode = False
        self.zoom_factor = max(0.05, min(8.0, self.zoom_factor * multiplier))
        self._render_pixmap()

    def _zoom_actual(self):
        if not self.current_pixmap or self.current_pixmap.isNull():
            return
        self.fit_mode = False
        self.zoom_factor = 1.0
        self._render_pixmap()

    def _zoom_fit(self):
        self.fit_mode = True
        self._render_pixmap()

    def _render_pixmap(self):
        if not self.current_pixmap or self.current_pixmap.isNull():
            return
        if self.fit_mode:
            target_w = max(260, self.img_scroll.viewport().width() - 16)
            target_h = max(260, self.img_scroll.viewport().height() - 16)
            scaled = self.current_pixmap.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.zoom_lbl.setText("Fit")
        else:
            w = max(1, int(self.current_pixmap.width() * self.zoom_factor))
            h = max(1, int(self.current_pixmap.height() * self.zoom_factor))
            scaled = self.current_pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.zoom_lbl.setText(f"{int(self.zoom_factor * 100)}%")
        self.img_label.setPixmap(scaled)

    def _toggle_playback(self):
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def _toggle_mute(self, checked):
        self.audio_output.setMuted(checked)
        self.mute_btn.setText("Unmute" if checked else "Mute")

    def _toggle_loop(self, checked):
        if checked:
            self.media_player.setLoops(QMediaPlayer.Loops.Infinite)
            self.loop_btn.setText("Loop: On")
        else:
            self.media_player.setLoops(QMediaPlayer.Loops.Once)
            self.loop_btn.setText("Loop: Off")

    def _fmt_ms(self, ms):
        if ms < 0:
            ms = 0
        total_sec, rem_ms = divmod(int(ms), 1000)
        cs = rem_ms // 10
        hrs, rem_sec = divmod(total_sec, 3600)
        mins, secs = divmod(rem_sec, 60)
        return f"{hrs:02d}:{mins:02d}:{secs:02d}.{cs:02d}"

    def _on_media_position(self, pos):
        self.seek_slider.setValue(pos)
        dur = self.media_player.duration()
        self.time_lbl.setText(f"{self._fmt_ms(pos)} / {self._fmt_ms(dur)}")

    def _on_media_duration(self, dur):
        self.seek_slider.setMaximum(dur)
        pos = self.media_player.position()
        self.time_lbl.setText(f"{self._fmt_ms(pos)} / {self._fmt_ms(dur)}")

    def toggle_details(self, checked):
        self.meta_bar.setText("▾ File Details" if checked else "▸ File Details")
        self.meta_panel.setVisible(checked)

    def _filter_text_lines(self, query):
        if not query:
            self.text_view.setPlainText(self.raw_text)
            return
        matched = [
            "%d: %s" % (idx + 1, line)
            for idx, line in enumerate(self.raw_text.splitlines())
            if query.lower() in line.lower()
        ]
        self.text_view.setPlainText("\n".join(matched))

    def inspect_path(self, path, force_hex=False, show_treemap=False):
        if not path or not os.path.exists(path):
            return

        self.media_player.stop()
        self.media_player.setSource(QUrl())
        stat = os.stat(path)
        self.meta_panel.setText("Path: %s\nSize: %s bytes" % (path, format(stat.st_size, ",")))

        if os.path.isdir(path):
            if show_treemap:
                self.treemap.scan_folder(path)
                self.stack.setCurrentWidget(self.treemap)
            else:
                self.highlighter.set_file("plain.txt")
                items = sorted(os.listdir(path))
                self.raw_text = "Folder: %s\nTotal items: %d\n\n" % (path, len(items)) + "\n".join(items[:300])
                self.text_view.setPlainText(self.raw_text)
                self.stack.setCurrentWidget(self.text_view)
            return

        if force_hex:
            self.highlighter.set_file("plain.txt")
            with open(path, "rb") as f:
                data = f.read(4096)
            hex_lines = []
            for i in range(0, len(data), 16):
                chunk = data[i:i + 16]
                hex_part = " ".join("%02x" % b for b in chunk)
                asc_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                hex_lines.append("%08x  %-48s  %s" % (i, hex_part, asc_part))
            self.raw_text = "\n".join(hex_lines)
            self.text_view.setPlainText(self.raw_text)
            self.stack.setCurrentWidget(self.text_view)
            return

        ext = os.path.splitext(path)[1].lower()
        img_exts = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg")
        media_exts = (".mp4", ".mkv", ".webm", ".avi", ".mov", ".mp3", ".wav", ".ogg", ".flac", ".m4a")
        model_exts = (".stl", ".obj", ".ply", ".gltf", ".glb", ".3mf", ".dae")
        arch_exts = (".zip", ".tar", ".gz", ".tgz")

        if ext in img_exts:
            pix = QPixmap(path)
            info = "Path: %s\nDimensions: %dx%d px\nSize: %s bytes" % (
                path, pix.width(), pix.height(), format(stat.st_size, ",")
            )
            self.meta_panel.setText(info)
            self.current_pixmap = pix
            self.fit_mode = True
            self.stack.setCurrentWidget(self.img_page)
            self._render_pixmap()

        elif ext in media_exts:
            self.media_player.setSource(QUrl.fromLocalFile(path))
            self.audio_output.setVolume(0.75)
            self.media_player.setLoops(QMediaPlayer.Loops.Infinite if self.loop_btn.isChecked() else QMediaPlayer.Loops.Once)
            self.stack.setCurrentWidget(self.media_page)
            self.media_player.play()

        elif ext in model_exts:
            self.plotter.clear()
            try:
                loaded = trimesh.load(path, force="scene" if ext == ".3mf" else None)
                if isinstance(loaded, trimesh.Scene):
                    for name, geom in loaded.geometry.items():
                        if len(geom.vertices) > 0:
                            pv_mesh = pv.wrap(geom)
                            self.plotter.add_mesh(pv_mesh, color="#6c8ebf", opacity=0.9, smooth_shading=True, show_edges=False)
                else:
                    pv_mesh = pv.wrap(loaded)
                    self.plotter.add_mesh(pv_mesh, color="#6c8ebf", opacity=0.9, smooth_shading=True)
                self.plotter.add_axes()
                self.plotter.reset_camera()
                self.stack.setCurrentWidget(self.plotter_frame)
            except Exception as e:
                self.highlighter.set_file("plain.txt")
                self.text_view.setPlainText("3D Load Error: " + str(e))
                self.stack.setCurrentWidget(self.text_view)

        elif ext == ".gcode":
            self._render_gcode(path)

        elif ext in arch_exts:
            self.highlighter.set_file("plain.txt")
            lines = ["Archive Contents: " + os.path.basename(path) + "\n"]
            if ext == ".zip":
                with zipfile.ZipFile(path, "r") as zf:
                    lines.extend(zf.namelist()[:300])
            else:
                with tarfile.open(path, "r:*") as tf:
                    lines.extend(tf.getnames()[:300])
            self.raw_text = "\n".join(lines)
            self.text_view.setPlainText(self.raw_text)
            self.stack.setCurrentWidget(self.text_view)

        elif ext == ".pdf":
            try:
                doc = fitz.open(path)
                page = doc.load_page(0)
                pix_fitz = page.get_pixmap(dpi=130)
                img_fmt = QImage.Format_RGBA8888 if pix_fitz.alpha else QImage.Format_RGB888
                qimg = QImage(pix_fitz.samples, pix_fitz.width, pix_fitz.height, pix_fitz.stride, img_fmt)
                self.meta_panel.setText("Path: %s\nPDF Pages: %d\nSize: %s bytes" % (path, len(doc), format(stat.st_size, ",")))
                self.current_pixmap = QPixmap.fromImage(qimg)
                self.fit_mode = True
                self.stack.setCurrentWidget(self.img_page)
                self._render_pixmap()
            except Exception as e:
                self.highlighter.set_file("plain.txt")
                self.text_view.setPlainText("PDF Preview Error: " + str(e))
                self.stack.setCurrentWidget(self.text_view)

        elif ext == ".docx":
            try:
                self.highlighter.set_file("plain.txt")
                document = docx.Document(path)
                paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
                self.raw_text = "\n\n".join(paragraphs[:200])
                self.text_view.setPlainText(self.raw_text)
                self.stack.setCurrentWidget(self.text_view)
            except Exception as e:
                self.text_view.setPlainText("DOCX Preview Error: " + str(e))
                self.stack.setCurrentWidget(self.text_view)

        elif ext == ".xlsx":
            try:
                self.highlighter.set_file("plain.txt")
                wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                lines = ["Sheets: " + ", ".join(wb.sheetnames) + "\n"]
                sheet = wb.active
                for row in sheet.iter_rows(max_row=100, values_only=True):
                    row_str = " | ".join(str(cell) if cell is not None else "" for cell in row)
                    if row_str.strip(" |"):
                        lines.append(row_str)
                self.raw_text = "\n".join(lines)
                self.text_view.setPlainText(self.raw_text)
                self.stack.setCurrentWidget(self.text_view)
            except Exception as e:
                self.text_view.setPlainText("XLSX Preview Error: " + str(e))
                self.stack.setCurrentWidget(self.text_view)

        else:
            with open(path, "r", errors="ignore") as f:
                self.raw_text = f.read(32000)
            self.highlighter.set_file(path)
            numbered = "\n".join("%4d | %s" % (i + 1, line) for i, line in enumerate(self.raw_text.splitlines()))
            self.text_view.setPlainText(numbered)
            self.stack.setCurrentWidget(self.text_view)

    def _render_gcode(self, path):
        self.plotter.clear()
        points = []
        x = y = z = 0.0
        coord_re = re.compile(r"([XYZ])([-+]?\d*\.?\d+)")
        with open(path, "r", errors="ignore") as f:
            for line in f:
                if line.startswith(("G0 ", "G1 ")):
                    for axis, val in coord_re.findall(line):
                        v = float(val)
                        if axis == "X":
                            x = v
                        elif axis == "Y":
                            y = v
                        elif axis == "Z":
                            z = v
                    points.append([x, y, z])

        if len(points) > 1:
            pts = np.array(points)
            poly = pv.lines_from_points(pts)
            poly["Layer Height (Z)"] = pts[:, 2]
            self.plotter.add_mesh(
                poly,
                scalars="Layer Height (Z)",
                cmap="ocean",
                line_width=1.1,
                opacity=0.8,
                show_scalar_bar=False,
            )
            self.plotter.add_axes()
            self.plotter.reset_camera()
        self.stack.setCurrentWidget(self.plotter_frame)
```
