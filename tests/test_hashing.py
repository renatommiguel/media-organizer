"""Tests for the hashing engine."""

from pathlib import Path

from media_organizer.hashing import file_hash, hamming_distance


def test_deterministic_hash(tmp_path):
    f = tmp_path / "data.bin"
    f.write_bytes(b"hello world")
    h1 = file_hash(f)
    h2 = file_hash(f)
    assert h1 == h2


def test_different_content_different_hash(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"aaa")
    b.write_bytes(b"bbb")
    assert file_hash(a) != file_hash(b)


def test_hash_is_hex_string(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"test")
    h = file_hash(f)
    assert isinstance(h, str)
    int(h, 16)  # must be valid hex


def test_hamming_distance_identical():
    assert hamming_distance("ff", "ff") == 0


def test_hamming_distance_one_bit():
    assert hamming_distance("fe", "ff") == 1
