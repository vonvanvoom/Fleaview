import os
import re
import shutil
import subprocess
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

from PySide6.QtCore import Qt, QUrl, QEvent, QTimer, Signal, QRect, QSize
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QImage, QTransform, QIcon,
    QSyntaxHighlighter, QTextCharFormat, QKeySequence, QShortcut
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QTextEdit, QLabel, QPushButton, QLineEdit, QFrame, QSlider,
    QScrollArea, QSpinBox, QMessageBox, QFileDialog, QGraphicsView, QGraphicsScene, QListWidget, QListWidgetItem, QSplitter
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
    """Interactive folder/drive space treemap with click-to-drill-down."""
    folder_clicked = Signal(str)

    def __init__(self):
        super().__init__()
        self.items = []
        self.hit_boxes = []
        self.setCursor(Qt.PointingHandCursor)

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
        entries.sort(key=lambda x: x[1], reverse=True)
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

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            for rect, full_path in self.hit_boxes:
                if rect.contains(pos) and os.path.isdir(full_path):
                    self.scan_folder(full_path)
                    self.folder_clicked.emit(full_path)
                    return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        painter.fillRect(rect, QColor("#1e1e2e"))
        self.hit_boxes = []
        if not self.items:
            painter.setPen(Qt.white)
            painter.drawText(rect, Qt.AlignCenter, "No data or empty folder")
            return

        total = sum(x[1] for x in self.items)
        y = 0
        palette = ["#89b4fa", "#a6e3a1", "#f9e2af", "#fab387", "#cba6f7", "#f38ba8"]
        for i, (name, size, full_path) in enumerate(self.items):
            h = max(20, int((size / total) * rect.height()))
            box = QRect(4, y + 2, rect.width() - 8, h - 4)
            self.hit_boxes.append((box, full_path))
            painter.fillRect(box, QColor(palette[i % len(palette)]))
            painter.setPen(QColor("#11111b"))
            mb = size / (1024 * 1024)
            prefix = "📁 " if os.path.isdir(full_path) else ""
            painter.drawText(10, y + 16, "%s%s (%.1f MB)" % (prefix, name, mb))
            y += h
            if y >= rect.height():
                break


class InspectorPane(QWidget):
    navigate_requested = Signal(str)

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

        # Page 0: Image & Multi-Page PDF Preview
        self.img_page = QWidget()
        img_layout = QVBoxLayout(self.img_page)
        img_layout.setContentsMargins(0, 0, 0, 0)

        zoom_bar = QHBoxLayout()
        zoom_bar.setSpacing(6)
        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setMinimumWidth(32)
        self.zoom_out_btn.clicked.connect(lambda: self._adjust_zoom(0.8))

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setMinimumWidth(32)
        self.zoom_in_btn.clicked.connect(lambda: self._adjust_zoom(1.25))

        self.zoom_100_btn = QPushButton("100%")
        self.zoom_100_btn.clicked.connect(self._zoom_actual)

        self.zoom_fit_btn = QPushButton("Fit")
        self.zoom_fit_btn.clicked.connect(self._zoom_fit)

        self.prev_img_btn = QPushButton("◀")
        self.prev_img_btn.setMinimumWidth(32)
        self.prev_img_btn.clicked.connect(lambda: self.step_slideshow(-1))

        self.next_img_btn = QPushButton("▶")
        self.next_img_btn.setMinimumWidth(32)
        self.next_img_btn.clicked.connect(lambda: self.step_slideshow(1))

        self.slide_btn = QPushButton("Slide (4s)")
        self.slide_btn.setCheckable(True)
        self.slide_btn.toggled.connect(self.toggle_slideshow)

        self.filmstrip_btn = QPushButton("Filmstrip")
        self.filmstrip_btn.setCheckable(True)
        self.filmstrip_btn.setToolTip("Show thumbnail strip for images and multi-page PDFs")
        self.filmstrip_btn.toggled.connect(self._toggle_filmstrip)

        self.pdf_prev_btn = QPushButton("◀ Pg")
        self.pdf_prev_btn.clicked.connect(lambda: self._step_pdf_page(-1))
        self.pdf_page_spin = QSpinBox()
        self.pdf_page_spin.setMinimum(1)
        self.pdf_page_spin.valueChanged.connect(self._render_pdf_page)
        self.pdf_total_lbl = QLabel("/ 1")
        self.pdf_next_btn = QPushButton("Pg ▶")
        self.pdf_next_btn.clicked.connect(lambda: self._step_pdf_page(1))
        self.pdf_widgets = (self.pdf_prev_btn, self.pdf_page_spin, self.pdf_total_lbl, self.pdf_next_btn)
        for w in self.pdf_widgets:
            w.hide()

        self.zoom_lbl = QLabel("Fit")
        self.zoom_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        zoom_bar.addWidget(self.zoom_out_btn, 1)
        zoom_bar.addWidget(self.zoom_in_btn, 1)
        zoom_bar.addWidget(self.zoom_100_btn, 1)
        zoom_bar.addWidget(self.zoom_fit_btn, 1)
        zoom_bar.addWidget(self.prev_img_btn, 1)
        zoom_bar.addWidget(self.slide_btn, 2)
        zoom_bar.addWidget(self.next_img_btn, 1)
        for w in self.pdf_widgets:
            zoom_bar.addWidget(w, 1)
        zoom_bar.addWidget(self.filmstrip_btn, 1)
        zoom_bar.addWidget(self.zoom_lbl)
        img_layout.addLayout(zoom_bar)

        self.img_edit_bar = QHBoxLayout()
        self.rot_left_btn = QPushButton("↺ 90°")
        self.rot_left_btn.clicked.connect(lambda: self._transform_image(rotate_deg=-90))
        self.rot_right_btn = QPushButton("↻ 90°")
        self.rot_right_btn.clicked.connect(lambda: self._transform_image(rotate_deg=90))
        self.flip_h_btn = QPushButton("⇄ Flip H")
        self.flip_h_btn.clicked.connect(lambda: self._transform_image(flip_h=True))
        self.flip_v_btn = QPushButton("⇅ Flip V")
        self.flip_v_btn.clicked.connect(lambda: self._transform_image(flip_v=True))
        self.save_img_btn = QPushButton("Save As / Rename...")
        self.save_img_btn.clicked.connect(self._save_image_copy)

        self.img_edit_widgets = (
            self.rot_left_btn, self.rot_right_btn,
            self.flip_h_btn, self.flip_v_btn, self.save_img_btn
        )
        self.img_edit_bar.setSpacing(6)
        for w in self.img_edit_widgets:
            self.img_edit_bar.addWidget(w, 1)
        img_layout.addLayout(self.img_edit_bar)

        self.img_scroll = QScrollArea()
        self.img_scroll.setWidgetResizable(True)
        self.img_scroll.setAlignment(Qt.AlignCenter)
        self.img_label = QLabel("Select a file to inspect")
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_scroll.setWidget(self.img_label)
        self.img_scroll.viewport().installEventFilter(self)
        self.img_scroll.viewport().setCursor(Qt.OpenHandCursor)
        self._drag_pos = None
        self.filmstrip = QListWidget()
        self.filmstrip.setViewMode(QListWidget.IconMode)
        self.filmstrip.setFlow(QListWidget.LeftToRight)
        self.filmstrip.setWrapping(False)
        self.filmstrip.setMovement(QListWidget.Static)
        self.filmstrip.setResizeMode(QListWidget.Adjust)
        self.filmstrip.setMinimumHeight(76)
        self.filmstrip.setIconSize(QSize(72, 72))
        self.filmstrip.setSpacing(6)
        self.filmstrip.setStyleSheet("QListWidget { background: #181825; color: #cdd6f4; border-top: 1px solid #313244; }")
        self.filmstrip.itemClicked.connect(self._on_filmstrip_clicked)
        self.filmstrip.hide()

        self.img_splitter = QSplitter(Qt.Vertical)
        self.img_splitter.addWidget(self.img_scroll)
        self.img_splitter.addWidget(self.filmstrip)
        self.img_splitter.setStretchFactor(0, 1)
        self.img_splitter.setStretchFactor(1, 0)
        self.img_splitter.splitterMoved.connect(self._on_filmstrip_resized)
        img_layout.addWidget(self.img_splitter)

        self.current_pixmap = None
        self.current_img_path = None
        self.zoom_factor = 1.0
        self.fit_mode = True
        self.pdf_doc = None
        self.slide_images = []
        self.slide_index = -1
        self.slide_timer = QTimer(self)
        self.slide_timer.setInterval(4000)
        self.slide_timer.timeout.connect(lambda: self.step_slideshow(1, from_timer=True))
        self.stack.addWidget(self.img_page)

        # Page 1: Syntax-Highlighted Code & Inline Quick-Editor
        self.text_page = QWidget()
        t_layout = QVBoxLayout(self.text_page)
        t_layout.setContentsMargins(0, 0, 0, 0)

        code_bar = QHBoxLayout()
        self.edit_mode_btn = QPushButton("Edit File")
        self.edit_mode_btn.setCheckable(True)
        self.edit_mode_btn.toggled.connect(self._toggle_code_edit)

        self.save_code_btn = QPushButton("Save (Ctrl+S)")
        self.save_code_btn.setEnabled(False)
        self.save_code_btn.clicked.connect(self._save_code_file)

        self.code_status_lbl = QLabel("Read-Only")
        code_bar.addWidget(self.edit_mode_btn)
        code_bar.addWidget(self.save_code_btn)
        code_bar.addStretch()
        code_bar.addWidget(self.code_status_lbl)
        t_layout.addLayout(code_bar)

        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setFont(QFont("Monospace", 10))
        self.text_view.setStyleSheet("QTextEdit { background: #1e1e2e; color: #cdd6f4; border: none; }")
        self.highlighter = PygmentsHighlighter(self.text_view.document())
        self.raw_text = ""
        self.current_text_path = None
        self.is_editable_text = False
        t_layout.addWidget(self.text_view)

        save_sc = QShortcut(QKeySequence("Ctrl+S"), self.text_page)
        save_sc.activated.connect(self._save_code_file)
        self.stack.addWidget(self.text_page)

        # Page 2: Interactive 3D PyVista Viewport
        self.plotter_frame = QFrame()
        p_layout = QVBoxLayout(self.plotter_frame)
        p_layout.setContentsMargins(0, 0, 0, 0)

        bar_3d = QHBoxLayout()
        self.wireframe_btn = QPushButton("Wireframe")
        self.wireframe_btn.setCheckable(True)
        self.wireframe_btn.toggled.connect(self._toggle_3d_wireframe)

        self.bbox_btn = QPushButton("Bounding Box")
        self.bbox_btn.setCheckable(True)
        self.bbox_btn.toggled.connect(self._toggle_3d_bbox)

        self.reset_cam_btn = QPushButton("Reset View")
        self.reset_cam_btn.clicked.connect(lambda: self.plotter.reset_camera())

        self.dims_3d_lbl = QLabel("")
        bar_3d.addWidget(self.wireframe_btn)
        bar_3d.addWidget(self.bbox_btn)
        bar_3d.addWidget(self.reset_cam_btn)
        bar_3d.addStretch()
        bar_3d.addWidget(self.dims_3d_lbl)
        p_layout.addLayout(bar_3d)

        self.plotter = QtInteractor(self.plotter_frame)
        self.plotter.set_background("#1e1e2e")
        p_layout.addWidget(self.plotter.interactor)
        self.mesh_actors = []
        self.bbox_actor = None
        self.stack.addWidget(self.plotter_frame)

        # Page 3: Interactive Disk Treemap
        self.treemap = DiskTreemapWidget()
        self.treemap.folder_clicked.connect(self.navigate_requested.emit)
        self.stack.addWidget(self.treemap)

        # Page 4: Audio & Video Preview Player with Rotate, Flip & Save Copy
        self.media_page = QWidget()
        m_layout = QVBoxLayout(self.media_page)
        m_layout.setContentsMargins(0, 0, 0, 0)

        media_edit_bar = QHBoxLayout()
        self.vid_rot_l_btn = QPushButton("↺ 90°")
        self.vid_rot_l_btn.clicked.connect(lambda: self._queue_media_transform(rot_delta=-90))
        self.vid_rot_r_btn = QPushButton("↻ 90°")
        self.vid_rot_r_btn.clicked.connect(lambda: self._queue_media_transform(rot_delta=90))
        self.vid_flip_h_btn = QPushButton("⇄ Flip H")
        self.vid_flip_h_btn.setCheckable(True)
        self.vid_flip_h_btn.toggled.connect(lambda _: self._update_media_transform_label())
        self.vid_flip_v_btn = QPushButton("⇅ Flip V")
        self.vid_flip_v_btn.setCheckable(True)
        self.vid_flip_v_btn.toggled.connect(lambda _: self._update_media_transform_label())
        self.save_media_btn = QPushButton("Save As / Rename...")
        self.save_media_btn.clicked.connect(self._save_media_copy)

        self.media_tx_lbl = QLabel("Transform: None")
        self.current_media_path = None
        self.media_rot_deg = 0

        media_edit_bar.addWidget(self.vid_rot_l_btn)
        media_edit_bar.addWidget(self.vid_rot_r_btn)
        media_edit_bar.addWidget(self.vid_flip_h_btn)
        media_edit_bar.addWidget(self.vid_flip_v_btn)
        media_edit_bar.addWidget(self.save_media_btn)
        media_edit_bar.addStretch()
        media_edit_bar.addWidget(self.media_tx_lbl)
        m_layout.addLayout(media_edit_bar)

        self.video_scene = QGraphicsScene(self)
        self.video_view = QGraphicsView(self.video_scene)
        self.video_view.setStyleSheet("background: #11111b; border: none;")
        self.video_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.video_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.video_item = QGraphicsVideoItem()
        self.video_scene.addItem(self.video_item)
        self.video_item.nativeSizeChanged.connect(self._fit_video_item)

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_item)

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
        m_layout.addWidget(self.video_view)
        m_layout.addLayout(controls)
        self.stack.addWidget(self.media_page)

    def _transform_image(self, rotate_deg=0, flip_h=False, flip_v=False):
        if not self.current_pixmap or self.current_pixmap.isNull():
            return
        tx = QTransform()
        if rotate_deg:
            tx.rotate(rotate_deg)
        if flip_h or flip_v:
            tx.scale(-1.0 if flip_h else 1.0, -1.0 if flip_v else 1.0)
        self.current_pixmap = self.current_pixmap.transformed(tx, Qt.SmoothTransformation)
        self._render_pixmap()

    def _save_image_copy(self):
        if not self.current_pixmap or self.current_pixmap.isNull():
            return
        base_path = self.current_img_path or os.path.expanduser("~/image.png")
        stem, ext = os.path.splitext(base_path)
        if not ext or ext.lower() == ".svg":
            ext = ".png"
        suggested = f"{stem}_edited{ext}"
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save Image Copy / Rename", suggested,
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)"
        )
        if not out_path:
            return
        if self.current_pixmap.save(out_path):
            self.navigate_requested.emit(os.path.dirname(out_path))
            QMessageBox.information(self, "Saved", f"Saved image to:\n{out_path}")
        else:
            QMessageBox.critical(self, "Save Error", "Could not save image to selected format.")

    def _fit_video_item(self, _size=None):
        nat = self.video_item.nativeSize()
        if nat.width() <= 0 or nat.height() <= 0:
            return
        self.video_item.setSize(nat)
        self.video_item.setTransformOriginPoint(nat.width() / 2.0, nat.height() / 2.0)
        tx = QTransform()
        sx = -1.0 if self.vid_flip_h_btn.isChecked() else 1.0
        sy = -1.0 if self.vid_flip_v_btn.isChecked() else 1.0
        tx.translate(nat.width() / 2.0, nat.height() / 2.0)
        tx.rotate(self.media_rot_deg)
        tx.scale(sx, sy)
        tx.translate(-nat.width() / 2.0, -nat.height() / 2.0)
        self.video_item.setTransform(tx)
        self.video_view.setSceneRect(self.video_item.mapRectToScene(self.video_item.boundingRect()))
        self.video_view.fitInView(self.video_view.sceneRect(), Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.stack.currentWidget() == self.media_page:
            self._fit_video_item()

    def _queue_media_transform(self, rot_delta=0):
        self.media_rot_deg = (self.media_rot_deg + rot_delta) % 360
        self._update_media_transform_label()

    def _update_media_transform_label(self):
        parts = []
        if self.media_rot_deg:
            parts.append(f"Rot {self.media_rot_deg}°")
        if self.vid_flip_h_btn.isChecked():
            parts.append("Flip H")
        if self.vid_flip_v_btn.isChecked():
            parts.append("Flip V")
        self.media_tx_lbl.setText("Transform: " + (", ".join(parts) if parts else "None"))
        self._fit_video_item()

    def _save_media_copy(self):
        if not self.current_media_path or not os.path.exists(self.current_media_path):
            return
        if not shutil.which("ffmpeg"):
            QMessageBox.critical(self, "FFmpeg Missing", "FFmpeg is not installed on this system.")
            return

        stem, ext = os.path.splitext(self.current_media_path)
        suggested = f"{stem}_edited{ext}"
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save Media Copy / Rename", suggested,
            "Media Files (*.mp4 *.mkv *.webm *.mov *.avi *.mp3 *.wav *.ogg *.flac);;All Files (*)"
        )
        if not out_path:
            return

        vf_filters = []
        if self.media_rot_deg == 90:
            vf_filters.append("transpose=1")
        elif self.media_rot_deg == 180:
            vf_filters.extend(["transpose=1", "transpose=1"])
        elif self.media_rot_deg == 270:
            vf_filters.append("transpose=2")
        if self.vid_flip_h_btn.isChecked():
            vf_filters.append("hflip")
        if self.vid_flip_v_btn.isChecked():
            vf_filters.append("vflip")

        size_mb = os.path.getsize(self.current_media_path) / (1024 * 1024)
        warn_msg = (
            f"File size: {size_mb:.1f} MB\n\n"
            "Converting or re-encoding a large media file with FFmpeg may take a while "
            "and temporarily slow down system performance.\n\n"
            "Do you want to proceed?"
        )
        reply = QMessageBox.warning(
            self, "FFmpeg Processing Notice", warn_msg,
            QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Ok
        )
        if reply != QMessageBox.Ok:
            return

        cmd = ["ffmpeg", "-y", "-i", self.current_media_path]
        if vf_filters:
            cmd.extend(["-vf", ",".join(vf_filters), "-c:a", "copy"])
        else:
            cmd.extend(["-c", "copy"])
        cmd.append(out_path)

        try:
            self.media_tx_lbl.setText("Saving...")
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self._update_media_transform_label()
            if res.returncode == 0:
                self.navigate_requested.emit(os.path.dirname(out_path))
                QMessageBox.information(self, "Saved", f"Saved media file to:\n{out_path}")
            else:
                QMessageBox.critical(self, "FFmpeg Error", res.stderr[-500:])
        except Exception as e:
            self._update_media_transform_label()
            QMessageBox.critical(self, "Error", str(e))

    def _toggle_code_edit(self, editing):
        if not self.is_editable_text or not self.current_text_path:
            self.edit_mode_btn.setChecked(False)
            return
        if editing:
            self.text_view.setReadOnly(False)
            self.text_view.setPlainText(self.raw_text)
            self.save_code_btn.setEnabled(True)
            self.code_status_lbl.setText("Editing (Ctrl+S to save)")
            self.text_view.setFocus()
        else:
            self.text_view.setReadOnly(True)
            self.save_code_btn.setEnabled(False)
            self.code_status_lbl.setText("Read-Only")
            numbered = "\n".join("%4d | %s" % (i + 1, line) for i, line in enumerate(self.raw_text.splitlines()))
            self.text_view.setPlainText(numbered)

    def _save_code_file(self):
        if not self.edit_mode_btn.isChecked() or not self.current_text_path:
            return
        try:
            updated = self.text_view.toPlainText()
            with open(self.current_text_path, "w", encoding="utf-8") as f:
                f.write(updated)
            self.raw_text = updated
            self.code_status_lbl.setText("Saved!")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _toggle_3d_wireframe(self, enabled):
        for actor in self.mesh_actors:
            actor.GetProperty().SetRepresentationToWireframe() if enabled else actor.GetProperty().SetRepresentationToSurface()
        self.plotter.render()

    def _toggle_3d_bbox(self, enabled):
        if enabled:
            self.bbox_actor = self.plotter.add_bounding_box(color="#f9e2af", line_width=1.5)
        elif self.bbox_actor is not None:
            self.plotter.remove_actor(self.bbox_actor)
            self.bbox_actor = None
        self.plotter.render()

    # --- PDF & Image Thumbnail Filmstrip ---
    def _on_filmstrip_resized(self, _pos=0, _index=0):
        h = self.filmstrip.height()
        icon_dim = max(48, min(260, h - 30))
        self.filmstrip.setIconSize(QSize(icon_dim, icon_dim))
        for i in range(self.filmstrip.count()):
            item = self.filmstrip.item(i)
            src_pix = item.data(Qt.UserRole + 1)
            if isinstance(src_pix, QPixmap) and not src_pix.isNull():
                scaled = src_pix.scaled(icon_dim, icon_dim, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                item.setIcon(QIcon(scaled))
        self.filmstrip.doItemsLayout()
        if self.fit_mode:
            self._render_pixmap()

    def _toggle_filmstrip(self, visible):
        self.filmstrip.setVisible(visible)
        if visible:
            total_h = max(300, self.img_splitter.height())
            self.img_splitter.setSizes([total_h - 120, 120])
            self._populate_filmstrip()
            self._on_filmstrip_resized()
        elif self.fit_mode:
            self._render_pixmap()

    def _populate_filmstrip(self):
        if not self.filmstrip_btn.isChecked():
            return
        self.filmstrip.clear()
        icon_dim = max(48, min(260, self.filmstrip.height() - 30))

        if self.pdf_doc is not None:
            max_pages = min(len(self.pdf_doc), 60)
            cur_pg = self.pdf_page_spin.value()
            for idx in range(max_pages):
                page = self.pdf_doc.load_page(idx)
                pix_fitz = page.get_pixmap(dpi=72)
                img_fmt = QImage.Format_RGBA8888 if pix_fitz.alpha else QImage.Format_RGB888
                qimg = QImage(pix_fitz.samples, pix_fitz.width, pix_fitz.height, pix_fitz.stride, img_fmt)
                src_pix = QPixmap.fromImage(qimg)
                scaled = src_pix.scaled(icon_dim, icon_dim, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                item = QListWidgetItem(QIcon(scaled), f"Pg {idx + 1}")
                item.setData(Qt.UserRole, ("pdf", idx + 1))
                item.setData(Qt.UserRole + 1, src_pix)
                self.filmstrip.addItem(item)
                if (idx + 1) == cur_pg:
                    self.filmstrip.setCurrentItem(item)
            return

        if self.slide_images:
            total = len(self.slide_images)
            center = max(0, self.slide_index)
            start = max(0, center - 30)
            end = min(total, start + 60)
            for idx in range(start, end):
                img_p = self.slide_images[idx]
                pix = QPixmap(img_p)
                if not pix.isNull():
                    src_pix = pix.scaled(260, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    thumb = src_pix.scaled(icon_dim, icon_dim, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    icon = QIcon(thumb)
                else:
                    src_pix = None
                    icon = QIcon()
                item = QListWidgetItem(icon, os.path.basename(img_p)[:14])
                item.setToolTip(os.path.basename(img_p))
                item.setData(Qt.UserRole, ("img", idx))
                item.setData(Qt.UserRole + 1, src_pix)
                self.filmstrip.addItem(item)
                if idx == self.slide_index:
                    self.filmstrip.setCurrentItem(item)

    def _on_filmstrip_clicked(self, item):
        payload = item.data(Qt.UserRole)
        if not payload:
            return
        kind, val = payload
        if kind == "pdf":
            self.pdf_page_spin.setValue(val)
        elif kind == "img" and 0 <= val < len(self.slide_images):
            self.slide_index = val
            self.inspect_path(self.slide_images[val], from_slide=True)

    def _step_pdf_page(self, delta):
        if not self.pdf_doc:
            return
        new_pg = max(1, min(len(self.pdf_doc), self.pdf_page_spin.value() + delta))
        self.pdf_page_spin.setValue(new_pg)

    def _render_pdf_page(self, page_num):
        if not self.pdf_doc:
            return
        idx = max(0, min(len(self.pdf_doc) - 1, page_num - 1))
        page = self.pdf_doc.load_page(idx)
        pix_fitz = page.get_pixmap(dpi=140)
        img_fmt = QImage.Format_RGBA8888 if pix_fitz.alpha else QImage.Format_RGB888
        qimg = QImage(pix_fitz.samples, pix_fitz.width, pix_fitz.height, pix_fitz.stride, img_fmt)
        self.current_pixmap = QPixmap.fromImage(qimg)
        self._render_pixmap()

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

    def keyPressEvent(self, event):
        if self.stack.currentWidget() == self.img_page and self.slide_images:
            if event.key() == Qt.Key_Right:
                self.step_slideshow(1)
                event.accept()
                return
            elif event.key() == Qt.Key_Left:
                self.step_slideshow(-1)
                event.accept()
                return
            elif event.key() == Qt.Key_Space:
                self.slide_btn.toggle()
                event.accept()
                return
        super().keyPressEvent(event)

    def toggle_slideshow(self, active):
        if active and len(self.slide_images) > 1:
            self.slide_btn.setText("Stop Slide")
            self.slide_timer.start()
            self.img_scroll.setFocus()
        else:
            self.slide_btn.setChecked(False)
            self.slide_btn.setText("Slide (4s)")
            self.slide_timer.stop()

    def step_slideshow(self, delta, from_timer=False):
        if not self.slide_images:
            return
        self.slide_index = (self.slide_index + delta) % len(self.slide_images)
        next_path = self.slide_images[self.slide_index]
        if not from_timer and self.slide_timer.isActive():
            self.slide_timer.start()
        self.inspect_path(next_path, from_slide=True)

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
            self.zoom_lbl.setText("%d%%" % int(self.zoom_factor * 100))
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
        return "%02d:%02d:%02d.%02d" % (hrs, mins, secs, cs)

    def _on_media_position(self, pos):
        self.seek_slider.setValue(pos)
        dur = self.media_player.duration()
        self.time_lbl.setText("%s / %s" % (self._fmt_ms(pos), self._fmt_ms(dur)))

    def _on_media_duration(self, dur):
        self.seek_slider.setMaximum(dur)
        pos = self.media_player.position()
        self.time_lbl.setText("%s / %s" % (self._fmt_ms(pos), self._fmt_ms(dur)))

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

    def _set_text_page(self, content, path=None, editable=False, lexer_file="plain.txt"):
        self.edit_mode_btn.blockSignals(True)
        self.edit_mode_btn.setChecked(False)
        self.edit_mode_btn.setEnabled(editable)
        self.edit_mode_btn.blockSignals(False)
        self.save_code_btn.setEnabled(False)
        self.code_status_lbl.setText("Read-Only" if editable else "Preview Only")
        self.text_view.setReadOnly(True)
        self.current_text_path = path
        self.is_editable_text = editable
        self.raw_text = content
        self.highlighter.set_file(lexer_file)
        if editable:
            numbered = "\n".join("%4d | %s" % (i + 1, line) for i, line in enumerate(content.splitlines()))
            self.text_view.setPlainText(numbered)
        else:
            self.text_view.setPlainText(content)
        self.stack.setCurrentWidget(self.text_page)

    def inspect_path(self, path, force_hex=False, show_treemap=False, from_slide=False):
        if not path or not os.path.exists(path):
            return

        if not from_slide and self.slide_timer.isActive():
            self.slide_btn.setChecked(False)

        self.media_player.stop()
        self.media_player.setSource(QUrl())
        self.pdf_doc = None
        for w in self.pdf_widgets:
            w.hide()

        stat = os.stat(path)
        self.meta_panel.setText("Path: %s\nSize: %s bytes" % (path, format(stat.st_size, ",")))

        if os.path.isdir(path):
            if show_treemap:
                self.treemap.scan_folder(path)
                self.stack.setCurrentWidget(self.treemap)
            else:
                items = sorted(os.listdir(path))
                listing = "Folder: %s\nTotal items: %d\n\n" % (path, len(items)) + "\n".join(items[:300])
                self._set_text_page(listing, editable=False)
            return

        if force_hex:
            with open(path, "rb") as f:
                data = f.read(4096)
            hex_lines = []
            for i in range(0, len(data), 16):
                chunk = data[i:i + 16]
                hex_part = " ".join("%02x" % b for b in chunk)
                asc_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                hex_lines.append("%08x  %-48s  %s" % (i, hex_part, asc_part))
            self._set_text_page("\n".join(hex_lines), editable=False)
            return

        ext = os.path.splitext(path)[1].lower()
        img_exts = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg")
        media_exts = (".mp4", ".mkv", ".webm", ".avi", ".mov", ".mp3", ".wav", ".ogg", ".flac", ".m4a")

        if ext in img_exts:
            for w in (self.prev_img_btn, self.slide_btn, self.next_img_btn):
                w.show()
            for w in self.img_edit_widgets:
                w.show()
            if not from_slide:
                folder = os.path.dirname(os.path.abspath(path))
                try:
                    self.slide_images = [
                        os.path.join(folder, name)
                        for name in sorted(os.listdir(folder), key=str.lower)
                        if os.path.splitext(name)[1].lower() in img_exts
                    ]
                    abs_p = os.path.abspath(path)
                    self.slide_index = self.slide_images.index(abs_p) if abs_p in self.slide_images else 0
                except OSError:
                    self.slide_images = [path]
                    self.slide_index = 0
            pix = QPixmap(path)
            dim_s = "%dx%d px" % (pix.width(), pix.height())
            sz_s = format(stat.st_size, ",")
            self.meta_panel.setText("Path: %s\nDimensions: %s\nSize: %s bytes" % (path, dim_s, sz_s))
            self.current_pixmap = pix
            self.current_img_path = path
            self.fit_mode = True
            self.stack.setCurrentWidget(self.img_page)
            self._render_pixmap()
            self._populate_filmstrip()

        elif ext in media_exts:
            self.current_media_path = path
            self.media_rot_deg = 0
            self.vid_flip_h_btn.setChecked(False)
            self.vid_flip_v_btn.setChecked(False)
            self._update_media_transform_label()
            is_video = ext in (".mp4", ".mkv", ".webm", ".avi", ".mov")
            for w in (self.vid_rot_l_btn, self.vid_rot_r_btn, self.vid_flip_h_btn, self.vid_flip_v_btn, self.media_tx_lbl):
                w.setVisible(is_video)
            self.media_player.setSource(QUrl.fromLocalFile(path))
            self.audio_output.setVolume(0.75)
            self.media_player.setLoops(QMediaPlayer.Loops.Infinite if self.loop_btn.isChecked() else QMediaPlayer.Loops.Once)
            self.stack.setCurrentWidget(self.media_page)
            self.media_player.play()

        elif ext in (".stl", ".obj", ".ply", ".gltf", ".glb", ".3mf", ".dae"):
            self.plotter.clear()
            self.mesh_actors = []
            self.bbox_actor = None
            self.wireframe_btn.setChecked(False)
            self.bbox_btn.setChecked(False)
            try:
                loaded = trimesh.load(path, force="scene" if ext == ".3mf" else None)
                bounds = loaded.bounds
                dims = bounds[1] - bounds[0] if bounds is not None else [0.0, 0.0, 0.0]
                dim_txt = "%.2f x %.2f x %.2f" % (dims[0], dims[1], dims[2])
                self.dims_3d_lbl.setText("Size: " + dim_txt)
                self.meta_panel.setText("Path: %s\n3D Dimensions: %s\nSize: %s bytes" % (path, dim_txt, format(stat.st_size, ",")))

                if isinstance(loaded, trimesh.Scene):
                    for name, geom in loaded.geometry.items():
                        if len(geom.vertices) > 0:
                            pv_mesh = pv.wrap(geom)
                            act = self.plotter.add_mesh(pv_mesh, color="#6c8ebf", opacity=0.9, smooth_shading=True, show_edges=False)
                            self.mesh_actors.append(act)
                else:
                    pv_mesh = pv.wrap(loaded)
                    act = self.plotter.add_mesh(pv_mesh, color="#6c8ebf", opacity=0.9, smooth_shading=True)
                    self.mesh_actors.append(act)
                self.plotter.add_axes()
                self.plotter.reset_camera()
                self.stack.setCurrentWidget(self.plotter_frame)
            except Exception as e:
                self._set_text_page("3D Load Error: " + str(e), editable=False)

        elif ext == ".gcode":
            self._render_gcode(path)

        elif ext in (".zip", ".tar", ".gz", ".tgz"):
            lines = ["Archive Contents: " + os.path.basename(path) + "\n"]
            if ext == ".zip":
                with zipfile.ZipFile(path, "r") as zf:
                    lines.extend(zf.namelist()[:300])
            else:
                with tarfile.open(path, "r:*") as tf:
                    lines.extend(tf.getnames()[:300])
            self._set_text_page("\n".join(lines), editable=False)

        elif ext == ".pdf":
            try:
                for w in (self.prev_img_btn, self.slide_btn, self.next_img_btn):
                    w.hide()
                for w in self.img_edit_widgets:
                    w.hide()
                self.current_img_path = None
                self.pdf_doc = fitz.open(path)
                total_pg = len(self.pdf_doc)
                self.pdf_page_spin.blockSignals(True)
                self.pdf_page_spin.setMaximum(max(1, total_pg))
                self.pdf_page_spin.setValue(1)
                self.pdf_page_spin.blockSignals(False)
                self.pdf_total_lbl.setText("/ %d" % total_pg)
                for w in self.pdf_widgets:
                    w.show()
                self.meta_panel.setText("Path: %s\nPDF Pages: %d\nSize: %s bytes" % (path, total_pg, format(stat.st_size, ",")))
                self.fit_mode = True
                self.stack.setCurrentWidget(self.img_page)
                self._render_pdf_page(1)
                self._populate_filmstrip()
            except Exception as e:
                self._set_text_page("PDF Preview Error: " + str(e), editable=False)

        elif ext == ".docx":
            try:
                document = docx.Document(path)
                paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
                self._set_text_page("\n\n".join(paragraphs[:200]), editable=False)
            except Exception as e:
                self._set_text_page("DOCX Preview Error: " + str(e), editable=False)

        elif ext == ".xlsx":
            try:
                wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                lines = ["Sheets: " + ", ".join(wb.sheetnames) + "\n"]
                sheet = wb.active
                for row in sheet.iter_rows(max_row=100, values_only=True):
                    row_str = " | ".join(str(cell) if cell is not None else "" for cell in row)
                    if row_str.strip(" |"):
                        lines.append(row_str)
                self._set_text_page("\n".join(lines), editable=False)
            except Exception as e:
                self._set_text_page("XLSX Preview Error: " + str(e), editable=False)

        else:
            with open(path, "r", errors="ignore") as f:
                content = f.read(64000)
            self._set_text_page(content, path=path, editable=True, lexer_file=path)

    def _render_gcode(self, path):
        self.plotter.clear()
        self.mesh_actors = []
        self.bbox_actor = None
        self.wireframe_btn.setChecked(False)
        self.bbox_btn.setChecked(False)
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
            mins, maxs = pts.min(axis=0), pts.max(axis=0)
            dims = maxs - mins
            self.dims_3d_lbl.setText("Travel: %.1f x %.1f x %.1f mm" % (dims[0], dims[1], dims[2]))
            poly = pv.lines_from_points(pts)
            poly["Layer Height (Z)"] = pts[:, 2]
            act = self.plotter.add_mesh(
                poly,
                scalars="Layer Height (Z)",
                cmap="ocean",
                line_width=1.1,
                opacity=0.8,
                show_scalar_bar=False,
            )
            self.mesh_actors.append(act)
            self.plotter.add_axes()
            self.plotter.reset_camera()
            self.stack.setCurrentWidget(self.plotter_frame)

