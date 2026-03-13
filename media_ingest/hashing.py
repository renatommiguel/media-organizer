"""Content hashing using BLAKE3 and optional perceptual hashing."""

from pathlib import Path
from typing import Optional

import blake3

from .utils import IMAGE_EXTENSIONS, RAW_EXTENSIONS, logger

CHUNK_SIZE = 1024 * 1024  # 1 MB


def file_hash(path: Path) -> str:
    """Return the BLAKE3 hex digest for *path*, read in 1 MB chunks."""
    hasher = blake3.blake3()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_perceptual_hash(filepath: Path) -> Optional[str]:
    """Return the perceptual hash (pHash) hex string for an image file.

    Returns ``None`` for non-image files or on failure.
    """
    if filepath.suffix.lower() not in (IMAGE_EXTENSIONS | RAW_EXTENSIONS):
        return None
    try:
        from PIL import Image
        import imagehash

        img = Image.open(filepath)
        return str(imagehash.phash(img))
    except Exception as exc:
        logger.debug("Perceptual hash failed for %s: %s", filepath, exc)
        return None


def hamming_distance(hash_a: str, hash_b: str) -> int:
    """Compute the Hamming distance between two hex-encoded hashes."""
    int_a = int(hash_a, 16)
    int_b = int(hash_b, 16)
    return bin(int_a ^ int_b).count("1")
