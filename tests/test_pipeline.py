"""Integration tests for the ingest pipeline."""

import pytest
from pathlib import Path

from media_ingest.pipeline import run_pipeline, run_verify
from media_ingest.database import ArchiveDB


@pytest.fixture
def ingest_env(tmp_path):
    source = tmp_path / "ingest"
    archive = tmp_path / "archive"
    source.mkdir()
    archive.mkdir()
    return source, archive


def _create_fake_image(path: Path, content: bytes = b"\xff\xd8\xff\xe0data"):
    path.write_bytes(content)


def test_ingest_moves_file(ingest_env):
    source, archive = ingest_env
    _create_fake_image(source / "photo.jpg")

    stats = run_pipeline(source, archive, workers=1)
    assert stats.processed == 1
    assert stats.errors == 0
    assert not (source / "photo.jpg").exists()


def test_ingest_detects_duplicate(ingest_env):
    source, archive = ingest_env
    _create_fake_image(source / "a.jpg", b"same-content")
    _create_fake_image(source / "b.jpg", b"same-content")

    stats = run_pipeline(source, archive, workers=1)
    assert stats.duplicates == 1
    assert stats.processed == 1


def test_dry_run_does_not_move(ingest_env):
    source, archive = ingest_env
    _create_fake_image(source / "photo.jpg")

    stats = run_pipeline(source, archive, workers=1, dry_run=True)
    assert (source / "photo.jpg").exists()


def test_resume_skips_processed(ingest_env):
    source, archive = ingest_env
    _create_fake_image(source / "a.jpg", b"content-a")

    run_pipeline(source, archive, workers=1)

    _create_fake_image(source / "b.jpg", b"content-b")
    stats = run_pipeline(source, archive, workers=1, resume=True)
    assert stats.processed == 1
    assert stats.skipped == 0  # a.jpg no longer in source so not encountered


def test_verify_clean_archive(ingest_env):
    source, archive = ingest_env
    _create_fake_image(source / "photo.jpg")
    run_pipeline(source, archive, workers=1)

    mismatches = run_verify(archive, workers=1)
    assert mismatches == []


def test_empty_source(ingest_env):
    source, archive = ingest_env
    stats = run_pipeline(source, archive, workers=1)
    assert stats.processed == 0
    assert stats.errors == 0
