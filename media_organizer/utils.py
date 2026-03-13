"""Shared helpers for the media ingest tool."""

import logging

logger = logging.getLogger("media_organizer")

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".heic"})
RAW_EXTENSIONS = frozenset({".cr2", ".cr3", ".nef", ".arw", ".dng", ".raf", ".rw2", ".orf"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".avi", ".mkv", ".m4v"})
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | RAW_EXTENSIONS | VIDEO_EXTENSIONS
