"""Tests for the metadata engine."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from media_organizer.metadata import (
    extract_metadata,
    reverse_geocode,
    write_metadata,
    _forward_geocode_nominatim,
)


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


# ------------------------------------------------------------------
# forward geocoding tests
# ------------------------------------------------------------------


def test_forward_geocode_success():
    fake_response = b'[{"lat": "48.8566", "lon": "2.3522"}]'
    with patch("media_organizer.metadata.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__ = lambda s: s
        mock_urlopen.return_value.__exit__ = lambda *a: None
        mock_urlopen.return_value.read.return_value = fake_response
        result = _forward_geocode_nominatim("Paris")
        assert result is not None
        assert abs(result[0] - 48.8566) < 0.001
        assert abs(result[1] - 2.3522) < 0.001


def test_forward_geocode_no_results():
    fake_response = b"[]"
    with patch("media_organizer.metadata.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__ = lambda s: s
        mock_urlopen.return_value.__exit__ = lambda *a: None
        mock_urlopen.return_value.read.return_value = fake_response
        assert _forward_geocode_nominatim("NonExistentPlace12345") is None


def test_forward_geocode_network_error():
    with patch(
        "media_organizer.metadata.urllib.request.urlopen",
        side_effect=Exception("timeout"),
    ):
        assert _forward_geocode_nominatim("Paris") is None


# ------------------------------------------------------------------
# write_metadata tests
# ------------------------------------------------------------------


def test_write_metadata_timestamp(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"\xff\xd8\xff\xe0data")
    ts = datetime(2024, 6, 15, 10, 30, 0)

    with patch("media_organizer.metadata.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        write_metadata(f, timestamp=ts)
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "-DateTimeOriginal=2024:06:15 10:30:00" in call_args
        assert "-CreateDate=2024:06:15 10:30:00" in call_args
        assert "-overwrite_original" in call_args


def test_write_metadata_location_with_gps(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"\xff\xd8\xff\xe0data")

    with patch(
        "media_organizer.metadata._forward_geocode_nominatim",
        return_value=(48.8566, 2.3522),
    ):
        with patch("media_organizer.metadata.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            write_metadata(f, location="Paris")
            call_args = mock_run.call_args[0][0]
            assert f"-GPSLatitude={48.8566}" in call_args
            assert "-GPSLatitudeRef=N" in call_args
            assert f"-GPSLongitude={2.3522}" in call_args
            assert "-GPSLongitudeRef=E" in call_args


def test_write_metadata_location_geocode_fails(tmp_path):
    """When forward geocoding fails, GPS is not written but no error."""
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"\xff\xd8\xff\xe0data")

    with patch(
        "media_organizer.metadata._forward_geocode_nominatim", return_value=None
    ):
        with patch("media_organizer.metadata.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            write_metadata(f, location="UnknownPlace")
            mock_run.assert_not_called()


def test_write_metadata_no_overrides(tmp_path):
    """No-op when neither timestamp nor location is provided."""
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"\xff\xd8\xff\xe0data")

    with patch("media_organizer.metadata.subprocess.run") as mock_run:
        write_metadata(f)
        mock_run.assert_not_called()


def test_write_metadata_exiftool_missing(tmp_path):
    """Gracefully handles ExifTool not being installed."""
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"\xff\xd8\xff\xe0data")
    ts = datetime(2024, 1, 1, 0, 0, 0)

    with patch(
        "media_organizer.metadata.subprocess.run",
        side_effect=FileNotFoundError("exiftool not found"),
    ):
        write_metadata(f, timestamp=ts)
