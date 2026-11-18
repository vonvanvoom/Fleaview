# `archive_fs.py`

**Role:** Nested Archive Virtual Filesystem (.zip/.7z/.rar/.tar/.cab)

## Source Code

```python
import os
import shutil
import subprocess
import tempfile
import zipfile
import tarfile
import py7zr
import rarfile
from PySide6.QtWidgets import QInputDialog


ARCHIVE_EXTS = {".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".cab"}


def is_archive(path):
    if not os.path.isfile(path):
        return False
    lower = path.lower()
    return any(lower.endswith(ext) for ext in ARCHIVE_EXTS)


class ArchiveManager:
    """Extracts archives (including nested archives) into managed temp directories."""

    def __init__(self):
        self.temp_root = tempfile.mkdtemp(prefix="fleaview_arch_")
        self.extracted_map = {}  # archive_path -> temp_dir

    def open_archive(self, archive_path, parent_widget=None):
        archive_path = os.path.abspath(archive_path)
        if archive_path in self.extracted_map and os.path.exists(self.extracted_map[archive_path]):
            return self.extracted_map[archive_path]

        out_dir = tempfile.mkdtemp(dir=self.temp_root, prefix=os.path.basename(archive_path) + "_")
        lower = archive_path.lower()

        try:
            if lower.endswith(".zip"):
                self._extract_zip(archive_path, out_dir, parent_widget)
            elif lower.endswith(".7z"):
                self._extract_7z(archive_path, out_dir, parent_widget)
            elif lower.endswith(".rar"):
                self._extract_rar(archive_path, out_dir, parent_widget)
            elif lower.endswith((".tar", ".gz", ".tgz", ".bz2", ".xz")):
                with tarfile.open(archive_path, "r:*") as tf:
                    tf.extractall(out_dir)
            elif lower.endswith(".cab"):
                subprocess.run(["7z", "x", f"-o{out_dir}", "-y", archive_path], check=True)
        except Exception as e:
            # Fallback to system 7z CLI if installed (handles encrypted 7z/RAR/CAB)
            if shutil.which("7z"):
                pwd, ok = QInputDialog.getText(
                    parent_widget, "Archive Password",
                    f"Enter password for {os.path.basename(archive_path)} (or leave blank):"
                )
                cmd = ["7z", "x", f"-o{out_dir}", "-y", archive_path]
                if ok and pwd:
                    cmd.append(f"-p{pwd}")
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                raise e

        self.extracted_map[archive_path] = out_dir
        return out_dir

    def _extract_zip(self, path, out_dir, parent):
        with zipfile.ZipFile(path, "r") as zf:
            try:
                zf.extractall(out_dir)
            except RuntimeError:
                pwd, ok = QInputDialog.getText(parent, "ZIP Password", "Enter password:")
                if ok and pwd:
                    zf.extractall(out_dir, pwd=pwd.encode("utf-8"))

    def _extract_7z(self, path, out_dir, parent):
        try:
            with py7zr.SevenZipFile(path, mode="r") as sz:
                sz.extractall(path=out_dir)
        except Exception:
            pwd, ok = QInputDialog.getText(parent, "7z Password", "Enter password:")
            if ok and pwd:
                with py7zr.SevenZipFile(path, mode="r", password=pwd) as sz:
                    sz.extractall(path=out_dir)

    def _extract_rar(self, path, out_dir, parent):
        with rarfile.RarFile(path) as rf:
            if rf.needs_password():
                pwd, ok = QInputDialog.getText(parent, "RAR Password", "Enter password:")
                if ok and pwd:
                    rf.setpassword(pwd)
            rf.extractall(out_dir)

    def cleanup(self):
        shutil.rmtree(self.temp_root, ignore_errors=True)
```
