"""Discover crawler document folders under a path."""

import os
from pathlib import Path

from app.core.logging import logger

REQUIRED = ("thuoc_tinh.json", "muc_luc.json", "van_ban.md")


def is_document_folder(path: Path) -> bool:
    return path.is_dir() and all((path / name).is_file() for name in REQUIRED)


def discover_document_folders(root: Path | str) -> list[Path]:
    """Return folders that contain the required crawler artifacts.

    If ``root`` itself is a document folder, return ``[root]``.
    Otherwise walk recursively and collect matching subfolders.
    """
    root = Path(root).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Path not found: {root}")

    if is_document_folder(root):
        return [root]

    found: list[Path] = []
    for dirpath, dirnames, _filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        p = Path(dirpath)
        if is_document_folder(p):
            found.append(p)
            dirnames.clear()

    found.sort(key=lambda p: str(p).lower())
    if not found:
        logger.warning("No legal document folders found under %s", root)
    else:
        logger.info("Discovered %s legal document folder(s) under %s", len(found), root)
    return found
