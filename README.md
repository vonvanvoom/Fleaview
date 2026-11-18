<p align="center">
  <img src="icon.png" alt="Fleaview Logo" width="120" />
</p>

<h1 align="center">Fleaview</h1>

<p align="center">
  <a href="https://github.comvonvanvoom/Fleaview/releases"><img src="https://shields.iovonvanvoom/Fleaview?style=for-the-badge&color=89b4fa" alt="Latest Release" /></a>
  <a href="https://github.comvonvanvoom/Fleaview/releases"><img src="https://shields.iovonvanvoom/Fleaview/total?style=for-the-badge&color=a6e3a1" alt="Total Downloads" /></a>
  <img src="https://shields.io" alt="Linux" />
  <img src="https://shields.io" alt="MIT License" />
</p>

<p align="center">
  A fast, standalone, keyboard-first file manager for Linux built with Python, PySide6, PyVista, and FFmpeg.
</p>

---

## What's New in v1.2.0

- **Multi-Page PDF Navigation:** Page scrubber (`◀ Pg` / `Pg ▶` and page spinbox) directly in the Inspector.
- **3D Viewport Controls:** Toggle **Wireframe**, **Bounding Box**, and **Reset View**, plus live `X × Y × Z` model dimensions.
- **Inline Code & Text Editor:** Edit code or text files right inside the Inspector and save with `Ctrl+S`.
- **Interactive Disk Treemap (`Ctrl+D`):** Click any folder block to drill down into subfolders.
- **Duplicate File Finder:** Scan folders by size and SHA-256 hash (`Edit > Find Duplicate Files...`) and move copies to Trash.

---

## Key Features

- **Multi-Pane & Tabbed Workspace:** Toggle side-by-side (`F3`) or stacked (`Shift+F3`) split panes, drag tabs between panes, and save/restore workspace layouts.
- **Multiple View Modes:** Switch seamlessly between **Details Tree**, **List View**, **Icon Grid**, and **Miller Columns**, with live type-to-filter and recursive subfolder search (`find:query`).
- **Keyboard-Driven Sidebar (`Alt+Q`):** Navigate places and mounted drives with arrow keys, reorder bookmarks (`Alt+Up`/`Alt+Down`), rename (`F2`), and delete (`Del`).
- **Interactive 3D & G-Code Viewport:** Hardware-accelerated PyVista/VTK rendering for `.stl`, `.obj`, `.3mf`, `.ply`, `.gltf`, `.glb`, `.dae`, and `.gcode` toolpaths with Z-height layer gradient coloring.
- **Rich File Inspector:**
  - **Images & PDFs:** Smooth mouse-wheel zoom, click-and-drag panning, `100%`/`Fit` toggles, and multi-page PDF rendering (`PyMuPDF`).
  - **Code & Office Previews:** Syntax-highlighted source code (`Pygments` Monokai) with line numbers and line filtering (`Alt+Shift+F`), `.docx`/`.xlsx` text extraction, hex viewer (`Ctrl+Shift+H`), and folder disk treemap (`Ctrl+D`).
  - **Audio & Video Player:** Embedded playback with seek bar, **Mute** toggle, **Loop** mode, and `hh:mm:ss.ss` timestamp readout.
- **Nested Archive Browsing:** Browse `.zip`, `.7z`, `.rar`, `.tar`, and `.cab` files (including archives inside archives) as regular folders with password prompt support.
- **FFmpeg Media Studio (`Ctrl+M`):** Convert `.webp`, `.png`, `.jpg`, `.gif`, `.mp4`, `.webm`, and rotate, flip, or resize media files.
- **Batch File Renamer (`Ctrl+Shift+R`):** Live preview table supporting Find/Replace, Python **Regex** capture groups, prefix/suffix, padded counters, and case transforms.
- **Full File Operations & Status Bar:** Right-click context menu, Cut/Copy/Paste, safe Trash (`send2trash`), permanent delete, show hidden files (`Ctrl+H`), refresh (`F5`), and a Thunar-style status bar.

---

## Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Ctrl+T` | Open New Tab |
| `F3` / `Shift+F3` | Toggle Split Pane (Side-by-Side / Stacked) |
| `Alt+Q` | Focus Keyboard Sidebar |
| `Ctrl+L` | Go To Path (`~` and `$ENV` supported) |
| `Ctrl+Shift+P` | Open Command Palette |
| `Ctrl+H` | Toggle Show Hidden Files |
| `F5` | Refresh Current Folder |
| `Ctrl+M` | Open FFmpeg Media Studio |
| `Ctrl+Shift+R` | Open Batch File Renamer (with Regex) |
| `Ctrl+Shift+H` | Inspect Selected File as Hex |
| `Ctrl+D` | Show Folder Space Treemap |
| `Alt+Shift+F` | Filter Lines in Code/Text Preview |
| `F2` / `Del` | Rename / Move to Trash |
| `F1` | About Fleaview |

---

## Installation & Building from Source (Linux)

### 1. System Dependencies (Debian / Ubuntu / Linux Mint)
```bash
sudo apt update
sudo apt install python3-venv ffmpeg libxcb-cursor0 p7zip-full
```

### 2. Python Virtual Environment Setup
```bash
git clone https://github.com/vonvanvoom/Fleaview.git
cd Fleaview

python3 -m venv fvenv
source fvenv/bin/activate
pip install -r requirements.txt
```

### 3. Run from Source
```bash
python3 main.py
```

### 4. Compile Standalone Single-File Executable
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
```

---

## Documentation
Detailed per-module code documentation and AI architecture notes are available in the [`docs/`](./docs/) folder.

---

## Copyright & License

Copyright © 2026 **vonvanvoom**.  
Source code is released under the [MIT License](./LICENSE). The **Fleaview™** name and custom application icon (`icon.png`) are original works of the author.
