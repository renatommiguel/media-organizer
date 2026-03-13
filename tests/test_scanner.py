"""Tests for the filesystem scanner."""

import pytest
from pathlib import Path

from media_ingest.scanner import scan


@pytest.fixture
def media_tree(tmp_path):
    """Create a small directory tree with mixed files."""
    (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    (tmp_path / "video.mp4").write_bytes(b"\x00\x00\x00\x1c")
    (tmp_path / "raw.cr2").write_bytes(b"raw-data")
    (tmp_path / "readme.txt").write_text("ignore me")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "nested.png").write_bytes(b"\x89PNG")
    return tmp_path


def test_yields_supported_extensions(media_tree):
    results = list(scan(media_tree))
    names = {p.name for p in results}
    assert names == {"photo.jpg", "video.mp4", "raw.cr2", "nested.png"}


def test_ignores_unsupported_files(media_tree):
    results = list(scan(media_tree))
    assert all(p.name != "readme.txt" for p in results)


def test_returns_generator(media_tree):
    import types
    gen = scan(media_tree)
    assert isinstance(gen, types.GeneratorType)


def test_nonexistent_directory(tmp_path):
    results = list(scan(tmp_path / "no_such_dir"))
    assert results == []


def test_empty_directory(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    results = list(scan(empty))
    assert results == []
