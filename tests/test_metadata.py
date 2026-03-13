"""Tests for the metadata engine."""

from datetime import datetime
from pathlib import Path

from media_ingest.metadata import extract_metadata


def test_fallback_to_mtime(tmp_path):
    """When no EXIF data exists, the file modification time is used."""
    f = tmp_path / "plain.jpg"
    f.write_bytes(b"\xff\xd8\xff\xe0bare")
    result = extract_metadata(f)
    assert result["timestamp"] is not None
    assert isinstance(result["timestamp"], datetime)


def test_returns_expected_keys(tmp_path):
    f = tmp_path / "video.mp4"
    f.write_bytes(b"\x00\x00\x00\x1c")
    result = extract_metadata(f)
    assert "timestamp" in result
    assert "camera" in result
    assert "gps_lat" in result
    assert "gps_lon" in result
