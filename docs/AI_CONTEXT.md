# AI Developer Handoff Context — Fleaview

Use this file when starting a new AI session to add features or refactor **Fleaview** without repeating past setup steps.

## Architecture Rules & Constraints
1. **Tech Stack:** Python 3.12, `PySide6` (Qt6), `pyvista` + `pyvistaqt` + `trimesh` (3D), `pygments` (syntax highlighting), `pymupdf` (PDF), `python-docx`, `openpyxl`, `send2trash`, and system `ffmpeg` via `subprocess`.
2. **Linux Mint 22.3 / X11 Compatibility:**
   - Requires `libxcb-cursor0` on target machines.
   - `os.environ["QT_FFMPEG_DECODING_HW_DEVICE_TYPES"] = ""` is set at the top of `main.py` before importing PySide6 to prevent VA-API hardware decode freezes alongside VTK OpenGL widgets.
   - `QSlider.durationChanged` must connect to `setMaximum` (not `setRange`).
3. **PyInstaller Packaging:**
   - All asset paths (such as `icon.png`) must resolve via `getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))`.
   - Always use 4-space indentation (never tabs) and avoid splitting `os.path.splitext(path)` tuple indexing.
4. **Module Responsibilities:**
   - `main.py`: `QMainWindow`, top menus, `QStatusBar`, `Command Palette`, `Go To` dialog, hotkey loading (`~/.config/fleaview/hotkeys.json`).
   - `workspace.py`: `QSplitter` dual-pane container, `QTabWidget` tab management, JSON layout save/restore (`~/.config/fleaview/layouts.json`).
   - `browser_pane.py`: `BrowserTab` hosting `QTreeView`, `QListView` (List & Icon), `QColumnView` (Miller), recursive `find:` search, right-click menu, and `FILE_CLIPBOARD`.
   - `sidebar.py`: `KeyboardSidebar` (`Alt+Q`), places, mounts (with `/media/root` `PermissionError` guard), bookmark reorder/rename/delete.
   - `inspector.py`: `InspectorPane` (`QStackedWidget` with Image/PDF label, `PygmentsHighlighter` `QTextEdit`, `QtInteractor` 3D viewport, `DiskTreemapWidget`, and `QMediaPlayer`).
   - `archive_fs.py`: `ArchiveManager` extracting `.zip`, `.7z`, `.rar`, `.tar`, `.cab` to managed temp folders.
   - `media_tools.py`: `FFmpegMediaDialog` building `-vf` filter chains for format conversion, rotation, flipping, and scaling.
   - `batch_rename.py`: `BatchRenameDialog` with live `QTableWidget` preview, `re.compile` regex support, counters, and case transforms.
   - `about.py`: `AboutDialog` displaying `icon.png`, clickable author hyperlink, runtime versions, and hotkey cheat sheet.
