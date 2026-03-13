"""Metadata extraction — timestamps, camera info, and GPS coordinates.

Primary tool: ExifTool (via subprocess).
Fallback chain: Pillow EXIF → filesystem modification time.
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .utils import IMAGE_EXTENSIONS, RAW_EXTENSIONS, logger


def _exiftool_path() -> str:
    """Return the path to the bundled ExifTool executable.

    Resolution order:
    1. PyInstaller frozen bundle (``sys._MEIPASS``)
    2. ``vendor/`` directory relative to the project root
    3. Fall back to bare ``exiftool`` on the system PATH
    """
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent
    exe = base / "vendor" / "exiftool.exe"
    if exe.exists():
        return str(exe)
    return "exiftool"

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


def write_metadata(
    filepath: Path,
    *,
    timestamp: Optional[datetime] = None,
    location: Optional[str] = None,
) -> None:
    """Write metadata overrides back into the file using ExifTool.

    If *timestamp* is given, updates DateTimeOriginal and CreateDate.
    If *location* is given, forward-geocodes the city name to GPS
    coordinates and writes GPSLatitude / GPSLongitude.
    """
    args: list[str] = [_exiftool_path(), "-overwrite_original"]

    if timestamp is not None:
        dt_str = timestamp.strftime("%Y:%m:%d %H:%M:%S")
        args += [f"-DateTimeOriginal={dt_str}", f"-CreateDate={dt_str}"]

    if location is not None:
        coords = _forward_geocode_nominatim(location)
        if coords:
            lat, lon = coords
            lat_ref = "N" if lat >= 0 else "S"
            lon_ref = "E" if lon >= 0 else "W"
            args += [
                f"-GPSLatitude={abs(lat)}",
                f"-GPSLatitudeRef={lat_ref}",
                f"-GPSLongitude={abs(lon)}",
                f"-GPSLongitudeRef={lon_ref}",
            ]
        else:
            logger.warning(
                "Could not forward-geocode '%s' — GPS metadata not written", location
            )

    if len(args) <= 2:
        return

    args.append(str(filepath))
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            logger.warning("ExifTool write failed for %s: %s", filepath, proc.stderr)
    except FileNotFoundError:
        logger.warning("ExifTool not found — metadata not written for %s", filepath)
    except Exception as exc:
        logger.warning("Failed to write metadata for %s: %s", filepath, exc)


def reverse_geocode(lat: Optional[float], lon: Optional[float]) -> str:
    """Resolve GPS coordinates to a city name.

    Fallback chain: Nominatim (online) → reverse_geocoder (offline)
    → ``"Unknown_location"``.  The returned string is sanitized for
    safe use in filenames.
    """
    if lat is None or lon is None:
        return "Unknown_location"

    city = _geocode_nominatim(lat, lon)
    if city is None:
        city = _geocode_offline(lat, lon)

    return _sanitize_for_filename(city) if city else "Unknown_location"


# ------------------------------------------------------------------
# Geocoding backends
# ------------------------------------------------------------------


def _geocode_nominatim(lat: float, lon: float) -> Optional[str]:
    """Online reverse geocode via OpenStreetMap Nominatim."""
    url = (
        f"https://nominatim.openstreetmap.org/reverse"
        f"?lat={lat}&lon={lon}&format=json&zoom=10"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "media-organizer/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        addr = data.get("address", {})
        return (
            addr.get("city")
            or addr.get("town")
            or addr.get("village")
            or addr.get("municipality")
        )
    except Exception:
        logger.debug("Nominatim lookup failed for (%s, %s)", lat, lon)
        return None


def _geocode_offline(lat: float, lon: float) -> Optional[str]:
    """Offline reverse geocode via the reverse_geocoder library."""
    try:
        import reverse_geocoder as rg

        result = rg.search((lat, lon), verbose=False)
        if result:
            return result[0].get("name")
    except Exception:
        logger.debug("Offline geocoder failed for (%s, %s)", lat, lon)
    return None


def _forward_geocode_nominatim(city: str) -> Optional[tuple[float, float]]:
    """Forward geocode a city name to (lat, lon) via Nominatim."""
    url = (
        f"https://nominatim.openstreetmap.org/search"
        f"?q={urllib.request.quote(city)}&format=json&limit=1"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "media-organizer/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        logger.debug("Nominatim forward geocode failed for '%s'", city)
    return None


def _sanitize_for_filename(name: str) -> str:
    """Replace whitespace with underscores and strip non-alphanumeric chars."""
    name = name.strip().replace(" ", "_")
    name = re.sub(r"[^\w\-]", "", name, flags=re.UNICODE)
    return name or "Unknown_location"


# ------------------------------------------------------------------
# ExifTool backend
# ------------------------------------------------------------------


def _extract_with_exiftool(filepath: Path) -> dict:
    proc = subprocess.run(
        [_exiftool_path(), "-json", "-dateFormat", "%Y:%m:%d %H:%M:%S", str(filepath)],
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
