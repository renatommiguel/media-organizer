"""Tests for the database layer."""

import pytest
from pathlib import Path

from media_organizer.database import ArchiveDB


@pytest.fixture
def db(tmp_path):
    database = ArchiveDB(tmp_path / "test.db")
    yield database
    database.close()


def test_file_insert_and_exists(db):
    assert not db.exists("abc123")
    db.insert("abc123", "/archive/photo.jpg", 1024)
    assert db.exists("abc123")


def test_duplicate_hash_replaces(db):
    db.insert("abc", "/old.jpg", 100)
    db.insert("abc", "/new.jpg", 200)
    rows = db.get_all_files()
    assert len(rows) == 1
    assert rows[0][1] == "/new.jpg"


def test_processed_files(db):
    assert not db.is_processed("/source/photo.jpg")
    db.mark_processed("/source/photo.jpg")
    assert db.is_processed("/source/photo.jpg")


def test_clear_processed(db):
    db.mark_processed("/a")
    db.mark_processed("/b")
    db.clear_processed()
    assert not db.is_processed("/a")
    assert not db.is_processed("/b")


def test_hash_cache(db):
    assert db.get_cached_hash("/f.jpg", 100, 1234.0) is None
    db.cache_hash("/f.jpg", 100, 1234.0, "hashval")
    assert db.get_cached_hash("/f.jpg", 100, 1234.0) == "hashval"
    assert db.get_cached_hash("/f.jpg", 101, 1234.0) is None


def test_metadata_insert(db):
    db.insert_metadata("/photo.jpg", 1700000000, "Canon EOS R5", 48.8, 2.3)


def test_perceptual_hash(db):
    db.insert_perceptual_hash("/a.jpg", "abcdef01")
    rows = db.get_all_perceptual_hashes()
    assert len(rows) == 1
    assert rows[0] == ("/a.jpg", "abcdef01")


def test_batch_mode(db):
    db.begin_batch()
    db.insert("h1", "/a.jpg", 10)
    db.insert("h2", "/b.jpg", 20)
    db.end_batch()
    assert db.exists("h1")
    assert db.exists("h2")


def test_remove_file(db):
    db.insert("h", "/x.jpg", 5)
    db.remove_file("h")
    assert not db.exists("h")
