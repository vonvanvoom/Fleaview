import os
from datetime import datetime

DOCS_DIR = "docs"
os.makedirs(DOCS_DIR, exist_ok=True)

MODULES = [
    ("main.py", "Main Window, Menus, Status Bar & Command Palette"),
    ("workspace.py", "Split Panes, Draggable Tabs & Saved Layouts"),
    ("browser_pane.py", "File Views, Filter/Search, Context Menu & File Operations"),
    ("sidebar.py", "Keyboard-Driven Places, Bookmarks & Mounts Sidebar"),
    ("inspector.py", "3D Viewport (.stl/.3mf/.gcode), Syntax Code, PDF, Office, Hex & Media Player"),
    ("archive_fs.py", "Nested Archive Virtual Filesystem (.zip/.7z/.rar/.tar/.cab)"),
    ("media_tools.py", "FFmpeg Image & Video Conversion, Rotate, Flip & Resize Studio"),
    ("batch_rename.py", "Live-Preview Batch File Renamer with Regex & Counters"),
    ("about.py", "About Dialog, Logo Banner & Shortcut Reference"),
]

# 1. Generate individual .md files for every working script
for filename, description in MODULES:
    if not os.path.exists(filename):
        continue
    with open(filename, "r", encoding="utf-8") as f:
        code = f.read()

    md_name = filename.replace(".py", ".md")
    md_path = os.path.join(DOCS_DIR, md_name)
    with open(md_path, "w", encoding="utf-8") as out:
        out.write(f"# `{filename}`\n\n")
        out.write(f"**Role:** {description}\n\n")
        out.write("## Source Code\n\n")
        out.write(f"```python\n{code.rstrip()}\n```\n")

# 2. Generate master README.md summary & build guide
readme_path = os.path.join(DOCS_DIR, "README.md")
with open(readme_path, "w", encoding="utf-8") as out:
    out.write(f"""# Fleaview File Manager

**Generated:** {datetime.now().strftime("%Y-%m-%d")}  
**Target OS:** Linux Mint 22.3 (Portable single-file executable via PyInstaller)

## Project Summary
Fleaview is a standalone, keyboard-first desktop file manager inspired by Flea and Thunar. It requires no Python environment on target Linux machines once compiled with PyInstaller.

## Key Features
- **Multi-Pane & Tabbed Workspace:** Side-by-side (`F3`) or stacked (`Shift+F3`) split panes, movable tabs, and JSON-saved workspace layouts.
- **Multiple View Modes:** Details Tree, List View, Icon Grid, Miller Columns, live type-to-filter, and recursive subfolder search (`find:query`).
- **Keyboard Sidebar (`Alt+Q`):** Navigate places and mounts with arrows, reorder bookmarks (`Alt+Up`/`Alt+Down`), rename (`F2`), and delete (`Del`).
- **3D & G-Code Viewport:** Hardware-accelerated PyVista/VTK rendering for `.stl`, `.obj`, `.3mf`, `.ply`, `.gltf`, `.glb`, `.dae`, and `.gcode` toolpaths with Z-height layer gradient coloring.
- **Rich File Inspector:** Syntax-highlighted code (`Pygments` Monokai) with line numbers and line filtering (`Alt+Shift+F`), image/SVG previews, PDF page rendering (`PyMuPDF`), `.docx`/`.xlsx` text extraction, hex viewer (`Ctrl+H`), folder disk treemap (`Ctrl+D`), and an embedded audio/video player.
- **Nested Archive Browsing:** Browse `.zip`, `.7z`, `.rar`, `.tar`, and `.cab` files (including archives inside archives) as regular folders with password prompt support.
- **FFmpeg Media Studio (`Ctrl+M`):** Convert `.webp`, `.png`, `.jpg`, `.gif`, `.mp4`, `.webm`, and rotate, flip, or resize images and videos.
- **Batch File Renamer (`Ctrl+Shift+R`):** Live preview table with Find/Replace, Python Regex capture groups, prefix/suffix, padded counters, and case conversion.
- **Full File Operations & Status Bar:** Right-click context menu, Cut/Copy/Paste, Trash (`send2trash`), permanent delete, Sublime Text/editor launch, and a Thunar-style status bar.

## Module Index
""")
    for filename, description in MODULES:
        md_name = filename.replace(".py", ".md")
        out.write(f"- **[{filename}](./{md_name})** — {description}\n")

    out.write("""
## System & Python Dependencies
### Linux System Packages (`apt`)
```bash
sudo apt install ffmpeg libxcb-cursor0 p7zip-full
```

### Python Virtual Environment Packages (`pip`)
```bash
pip install PySide6 pyvista pyvistaqt trimesh numpy py7zr rarfile pymupdf python-docx openpyxl lxml pygments send2trash pillow pyinstaller
```

## Build Standalone Executable
```bash
python3 -m PyInstaller --onefile --windowed --name fleaview \\
  --icon=icon.png \\
  --add-data "icon.png:." \\
  --collect-all pyvista \\
  --collect-all pyvistaqt \\
  --collect-all vtk \\
  --collect-all pygments \\
  --hidden-import=pymupdf \\
  --hidden-import=docx \\
  --hidden-import=openpyxl \\
  --hidden-import=py7zr \\
  --hidden-import=rarfile \\
  --hidden-import=lxml \\
  --hidden-import=send2trash \\
  main.py

cp dist/fleaview ~/.local/bin/fleaview
```
""")

# 3. Generate AI_CONTEXT.md for seamless future AI handoffs
ai_path = os.path.join(DOCS_DIR, "AI_CONTEXT.md")
with open(ai_path, "w", encoding="utf-8") as out:
    out.write("""# AI Developer Handoff Context — Fleaview

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
""")

print("All clean Markdown files generated inside:", os.path.abspath(DOCS_DIR))
