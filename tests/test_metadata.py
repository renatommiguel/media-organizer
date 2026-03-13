"""Tests for the metadata engine."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from media_organizer.metadata import extract_metadata, reverse_geocode


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


# ------------------------------------------------------------------
# reverse_geocode tests
# ------------------------------------------------------------------


def test_reverse_geocode_no_gps():
    assert reverse_geocode(None, None) == "Unknown_location"


def test_reverse_geocode_partial_gps():
    assert reverse_geocode(48.8, None) == "Unknown_location"
    assert reverse_geocode(None, 2.3) == "Unknown_location"


def test_reverse_geocode_nominatim_success():
    fake_response = b'{"address": {"city": "Paris"}}'
    with patch("media_organizer.metadata.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__ = lambda s: s
        mock_urlopen.return_value.__exit__ = lambda *a: None
        mock_urlopen.return_value.read.return_value = fake_response
        assert reverse_geocode(48.8566, 2.3522) == "Paris"


def test_reverse_geocode_falls_back_to_offline():
    fake_rg_result = [{"name": "Lyon"}]
    with patch("media_organizer.metadata._geocode_nominatim", return_value=None):
        with patch("media_organizer.metadata._geocode_offline", return_value="Lyon"):
            assert reverse_geocode(45.76, 4.84) == "Lyon"


def test_reverse_geocode_all_fail():
    with patch("media_organizer.metadata._geocode_nominatim", return_value=None):
        with patch("media_organizer.metadata._geocode_offline", return_value=None):
            assert reverse_geocode(0.0, 0.0) == "Unknown_location"


def test_reverse_geocode_sanitizes_name():
    with patch("media_organizer.metadata._geocode_nominatim", return_value="São Paulo"):
        result = reverse_geocode(23.5, -46.6)
        assert " " not in result
        assert result == "São_Paulo"


def test_reverse_geocode_sanitizes_special_chars():
    with patch("media_organizer.metadata._geocode_nominatim", return_value="City/Town (East)"):
        result = reverse_geocode(1.0, 1.0)
        assert "/" not in result
        assert "(" not in result
        assert ")" not in result
