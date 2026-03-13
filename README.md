# Media Organizer

A command-line tool that ingests unstructured photos and videos and organizes them into a date-based archive using metadata timestamps.

## Features

- **Metadata-based organization** — files are sorted into `archive/YYYY/MM/DD/` using EXIF timestamps (DateTimeOriginal > CreateDate > MediaCreateDate > file modification time).
- **Exact duplicate detection** — BLAKE3 content hashing identifies and removes identical files across ingests.
- **Perceptual duplicate detection** — optional pHash-based comparison finds visually similar images (hamming distance threshold ≤ 5).
- **Persistent archive index** — SQLite database tracks all ingested files, enabling cross-session deduplication and integrity verification.
- **Archive verification** — recomputes hashes to detect bit rot, disk corruption, or accidental modification.
- **Crash-safe resume** — interrupted ingests pick up where they left off.
- **Streaming pipeline** — generator-based scanning and bounded worker pools keep memory usage constant regardless of archive size.
- **Parallel processing** — configurable thread pool for concurrent hashing, metadata extraction, and file moves.
- **Broad format support** — JPEG, PNG, HEIC, RAW (CR2, CR3, NEF, ARW, DNG, RAF, RW2, ORF), and video (MP4, MOV, AVI, MKV, M4V).

## Requirements

- Python 3.11+
- [ExifTool](https://exiftool.org/) (recommended, for best metadata extraction; falls back to Pillow and file modification time)

## Installation

```bash
uv sync
```

Or with pip:

```bash
pip install -r requirements.txt
```

## Usage

### Ingest media

```bash
uv run media-organizer <source> <archive>
```

This scans `<source>` for media files, extracts timestamps, removes duplicates, and moves files into `<archive>/YYYY/MM/DD/`.

### Options

| Flag | Description |
|---|---|
| `--dry-run` | Preview what would happen without moving files |
| `--workers N` | Number of parallel workers (default: 4) |
| `--resume` | Skip files already processed in a previous run |
| `--perceptual` | Enable perceptual (visual) duplicate detection |
| `--verify` | Verify archive integrity instead of ingesting |

### Examples

```bash
# Basic ingest
uv run media-organizer ~/Photos/Camera ~/Photos/Archive

# Preview without moving anything
uv run media-organizer ~/Photos/Camera ~/Photos/Archive --dry-run

# Fast ingest with 8 workers
uv run media-organizer ~/Photos/Camera ~/Photos/Archive --workers 8

# Resume an interrupted ingest
uv run media-organizer ~/Photos/Camera ~/Photos/Archive --resume

# Detect visually similar images too
uv run media-organizer ~/Photos/Camera ~/Photos/Archive --perceptual

# Verify archive integrity (detect corruption)
uv run media-organizer ~/Photos/Archive --verify
```

## Archive structure

```
archive/
  2023/
    07/
      14/
        photo.jpg
        photo_1.jpg    # filename collision resolved automatically
        video.mp4
    08/
      02/
        IMG_1234.cr2
```

## Project structure

```
media_organizer/
  cli.py          # Command-line interface
  pipeline.py     # Ingest orchestration and verification
  scanner.py      # Generator-based filesystem scanning
  hashing.py      # BLAKE3 content hashing and perceptual hashing
  metadata.py     # ExifTool / Pillow / mtime metadata extraction
  organizer.py    # Date-based archive path computation
  database.py     # Thread-safe SQLite access layer
  utils.py        # Shared constants and logger
```

## Running tests

```bash
uv run pytest
```
