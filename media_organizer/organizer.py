"""Archive path creation — determines where each file is stored."""

import shutil
from datetime import datetime
from pathlib import Path

from .utils import logger


def target_path(dest: str | Path, date: datetime, name: str) -> Path:
    """Return the target path inside the archive for a file.

    Structure: ``archive/YYYY/MM/name``.
    If a file with the same name already exists the suffix is incremented
    (``photo.jpg`` → ``photo_1.jpg`` → ``photo_2.jpg`` …).
    """
    root = Path(dest)
    month_dir = root / f"{date.year:04d}" / f"{date.month:02d}"
    month_dir.mkdir(parents=True, exist_ok=True)

    target = month_dir / name
    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    counter = 1
    while True:
        candidate = month_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def move_file(source: Path, destination: Path) -> None:
    """Move *source* to *destination*, creating parent dirs as needed."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        source.rename(destination)
    except OSError:
        shutil.move(str(source), str(destination))
    logger.debug("Moved %s → %s", source, destination)
