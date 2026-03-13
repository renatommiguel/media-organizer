"""Metadata extraction — timestamps, camera info, and GPS coordinates.

Primary tool: ExifTool (via subprocess).
Fallback chain: Pillow EXIF → filesystem modification time.
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .utils import IMAGE_EXTENSIONS, RAW_EXTENSIONS, logger

_EXIF_DATE_TAGS = (
    "EXIF:DateTimeOriginal",
    "EXIF:CreateDate",
    "H264:DateTimeOriginal",
    "QuickTime:CreateDate",
    "QuickTime:MediaCreateDate",
)

_DATE_FORMATS = (
    "%Y:%m:%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y:%m:%d %H:%M:%S%z",
)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def extract_metadata(filepath: Path) -> dict:
    """Return a metadata dict for *filepath*.

    Keys: ``timestamp`` (datetime | None), ``camera`` (str),
    ``gps_lat`` (float | None), ``gps_lon`` (float | None).
    """
    result: dict = {
        "timestamp": None,
        "camera": "",
        "gps_lat": None,
        "gps_lon": None,
    }

    try:
        result = _extract_with_exiftool(filepath)
    except Exception:
        logger.debug("ExifTool unavailable/failed for %s, trying Pillow", filepath)
        try:
            result = _extract_with_pillow(filepath)
        except Exception:
            logger.debug("Pillow extraction failed for %s", filepath)

    if result["timestamp"] is None:
        result["timestamp"] = _file_mtime(filepath)

    return result


# ------------------------------------------------------------------
# ExifTool backend
# ------------------------------------------------------------------


def _extract_with_exiftool(filepath: Path) -> dict:
    proc = subprocess.run(
        ["exiftool", "-json", "-dateFormat", "%Y:%m:%d %H:%M:%S", str(filepath)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)

    data = json.loads(proc.stdout)[0]

    timestamp = None
    for tag in _EXIF_DATE_TAGS:
        short = tag.split(":")[-1]
        raw = data.get(tag) or data.get(short)
        if raw:
            timestamp = _parse_date(str(raw))
            if timestamp:
                break

    camera = data.get("Model", "") or data.get("EXIF:Model", "")
    gps_lat = _to_float(data.get("GPSLatitude"))
    gps_lon = _to_float(data.get("GPSLongitude"))

    return {
        "timestamp": timestamp,
        "camera": camera,
        "gps_lat": gps_lat,
        "gps_lon": gps_lon,
    }


# ------------------------------------------------------------------
# Pillow fallback
# ------------------------------------------------------------------


def _extract_with_pillow(filepath: Path) -> dict:
    if filepath.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError("Pillow only handles standard image formats")

    from PIL import Image
    from PIL.ExifTags import TAGS

    img = Image.open(filepath)
    exif_data = img.getexif()
    if not exif_data:
        raise ValueError("No EXIF data")

    tag_map = {TAGS.get(k, k): v for k, v in exif_data.items()}

    timestamp = None
    for key in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
        raw = tag_map.get(key)
        if raw:
            timestamp = _parse_date(str(raw))
            if timestamp:
                break

    return {
        "timestamp": timestamp,
        "camera": str(tag_map.get("Model", "")),
        "gps_lat": None,
        "gps_lon": None,
    }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _file_mtime(filepath: Path) -> datetime:
    mtime = os.path.getmtime(filepath)
    return datetime.fromtimestamp(mtime, tz=timezone.utc)


def _parse_date(raw: str) -> Optional[datetime]:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def _to_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
