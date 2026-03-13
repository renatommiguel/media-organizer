"""Filesystem scanning with generator-based streaming."""

from pathlib import Path
from typing import Iterator

from .utils import SUPPORTED_EXTENSIONS, logger


def scan(source: str | Path) -> Iterator[Path]:
    """Stream media files from *source* using a generator.

    Yields one ``Path`` per supported media file found anywhere under
    *source*.  The generator never materialises the full file list,
    keeping memory usage constant regardless of archive size.
    """
    root = Path(source)
    if not root.is_dir():
        logger.error("Source directory does not exist: %s", root)
        return

    for entry in root.rglob("*"):
        if entry.is_file() and entry.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield entry
