"""Shared helpers for the media ingest tool."""

import logging

logger = logging.getLogger("media_organizer")

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".heic", ".gif", ".webp", ".bmp", ".pdf", ".tiff", ".tif"})
RAW_EXTENSIONS = frozenset({".cr2", ".cr3", ".nef", ".arw", ".dng", ".raf", ".rw2", ".orf"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".mpg", ".mov", ".avi", ".mkv", ".m4v", ".3gp", ".wmv"})
AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"})
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | RAW_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS
