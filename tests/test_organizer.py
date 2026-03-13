"""Tests for the archive organizer."""

from datetime import datetime
from pathlib import Path

from media_ingest.organizer import target_path, move_file


def test_destination_structure(tmp_path):
    ts = datetime(2023, 7, 14, 12, 0, 0)
    dest = target_path(tmp_path, ts, "photo.jpg")
    assert dest == tmp_path / "2023" / "07" / "14" / "photo.jpg"


def test_collision_resolution(tmp_path):
    ts = datetime(2023, 7, 14)
    day_dir = tmp_path / "2023" / "07" / "14"
    day_dir.mkdir(parents=True)
    (day_dir / "photo.jpg").write_bytes(b"existing")

    dest = target_path(tmp_path, ts, "photo.jpg")
    assert dest.name == "photo_1.jpg"


def test_multiple_collisions(tmp_path):
    ts = datetime(2023, 1, 1)
    day_dir = tmp_path / "2023" / "01" / "01"
    day_dir.mkdir(parents=True)
    (day_dir / "img.png").write_bytes(b"x")
    (day_dir / "img_1.png").write_bytes(b"x")

    dest = target_path(tmp_path, ts, "img.png")
    assert dest.name == "img_2.png"


def test_move_file(tmp_path):
    src = tmp_path / "source" / "photo.jpg"
    src.parent.mkdir()
    src.write_bytes(b"content")

    dst = tmp_path / "archive" / "2023" / "01" / "photo.jpg"
    move_file(src, dst)

    assert dst.exists()
    assert not src.exists()
    assert dst.read_bytes() == b"content"
