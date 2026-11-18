# Fleaview File Manager

**Generated:** 2026-11-17  
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
- **[main.py](./main.md)** — Main Window, Menus, Status Bar & Command Palette
- **[workspace.py](./workspace.md)** — Split Panes, Draggable Tabs & Saved Layouts
- **[browser_pane.py](./browser_pane.md)** — File Views, Filter/Search, Context Menu & File Operations
- **[sidebar.py](./sidebar.md)** — Keyboard-Driven Places, Bookmarks & Mounts Sidebar
- **[inspector.py](./inspector.md)** — 3D Viewport (.stl/.3mf/.gcode), Syntax Code, PDF, Office, Hex & Media Player
- **[archive_fs.py](./archive_fs.md)** — Nested Archive Virtual Filesystem (.zip/.7z/.rar/.tar/.cab)
- **[media_tools.py](./media_tools.md)** — FFmpeg Image & Video Conversion, Rotate, Flip & Resize Studio
- **[duplicate_finder.py](./duplicate_finder.md)** — SHA-256 Duplicate File Scanner & Safe Trash Cleanup
- **[batch_rename.py](./batch_rename.md)** — Live-Preview Batch File Renamer with Regex & Counters
- **[about.py](./about.md)** — About Dialog, Logo Banner & Shortcut Reference

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
python3 -m PyInstaller --onefile --windowed --name fleaview \
  --icon=icon.png \
  --add-data "icon.png:." \
  --collect-all pyvista \
  --collect-all pyvistaqt \
  --collect-all vtk \
  --collect-all pygments \
  --hidden-import=pymupdf \
  --hidden-import=docx \
  --hidden-import=openpyxl \
  --hidden-import=py7zr \
  --hidden-import=rarfile \
  --hidden-import=lxml \
  --hidden-import=send2trash \
  main.py

cp dist/fleaview ~/.local/bin/fleaview
```
