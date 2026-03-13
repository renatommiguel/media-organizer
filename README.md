# Media Organizer

**Turn your chaotic camera dumps into a beautifully organized, deduplicated, GPS-tagged archive — in seconds.**

Media Organizer is a blazing-fast CLI tool that scans unstructured folders of photos and videos, extracts rich metadata, eliminates duplicates, and files everything into a clean date-based archive. Files are automatically renamed with their capture time and location, so you always know *when* and *where* a photo was taken just by looking at the filename.

```
Before:                          After:
DCIM/                            archive/
  IMG_4021.jpg                     2024/
  IMG_4021 (1).jpg                   03/
  DSC00382.ARW                         15/
  random/                                14_30_00_Paris.jpg
    MVI_0042.mp4                         14_30_00_Paris_1.jpg   (collision resolved)
    IMG_4021.jpg   (duplicate)           17_22_10_Lyon.mp4
  old_trip/                          08/
    photo.jpg                          22/
                                         09_15_33_Unknown_location.arw
                                         11_00_00_Barcelona.jpg
```

---

## Features

### Smart file naming

Every file is renamed to `DDd_HHh_MMmin_SSs_City.ext` using EXIF timestamps and GPS coordinates. The city is resolved automatically via a two-tier geocoding system:

1. **Nominatim** (OpenStreetMap) — online, high accuracy
2. **reverse_geocoder** — offline fallback, works without internet
3. Falls back to `Unknown_location` when no GPS data is available

### Manual metadata overrides

Know where your photos were taken but the GPS is missing? Override it from the CLI:

```bash
uv run media-organizer ~/Photos/Trip ~/Archive --location "Tokyo"
```

Need to fix the year or month on a batch of files? These flags update both the filename **and** the EXIF metadata inside the file, so the correction is permanent:

```bash
uv run media-organizer ~/Photos/Old ~/Archive --year 2019 --month 8
```

All three flags can be combined and work together with every other option.

### Duplicate detection

- **Exact duplicates** — BLAKE3 content hashing (one of the fastest hash algorithms available) catches byte-identical files instantly, even across separate ingest sessions.
- **Perceptual duplicates** (optional) — pHash-based visual comparison finds near-identical images with a configurable hamming distance threshold.

### Date-based archive structure

Files are organized into `archive/YYYY/MM/DD/` directories using the best available timestamp:

`DateTimeOriginal > CreateDate > MediaCreateDate > file modification time`

### Resilient by design

- **Crash-safe resume** — every processed file is tracked in SQLite. If an ingest is interrupted, just run it again with `--resume`.
- **Archive verification** — recompute hashes across the entire archive to detect bit rot, disk corruption, or accidental edits.
- **Hash caching** — previously computed hashes are cached by file size + modification time, making re-runs near-instant.

### Built for scale

- **Streaming pipeline** — generator-based scanning never loads the full file list into memory.
- **Parallel workers** — configurable thread pool (`--workers N`) for concurrent hashing, metadata extraction, and file moves.
- **Batched database writes** — SQLite commits are grouped for throughput.
- Constant memory usage whether you have 100 or 1,000,000 files.

### Broad format support

| Category | Formats |
|---|---|
| Images | JPEG, PNG, HEIC |
| RAW | CR2, CR3, NEF, ARW, DNG, RAF, RW2, ORF |
| Video | MP4, MOV, AVI, MKV, M4V |

---

## Requirements

- **Python 3.11+**
- **[ExifTool](https://exiftool.org/)** (recommended) — provides the richest metadata extraction including GPS. Without it, the tool falls back to Pillow EXIF reading and file modification time.

## Installation

```bash
uv sync
```

Or with pip:

```bash
pip install -r requirements.txt
```

---

## Usage

### Ingest media

```bash
uv run media-organizer <source> <archive>
```

Scans `<source>` recursively for media files, deduplicates, renames with time + location, and moves them into `<archive>/YYYY/MM/DD/`.

### Options

| Flag | Description |
|---|---|
| `--dry-run` | Preview what would happen without moving files |
| `--workers N` | Number of parallel workers (default: 4) |
| `--resume` | Skip files already processed in a previous run |
| `--perceptual` | Enable perceptual (visual) duplicate detection |
| `--verify` | Verify archive integrity instead of ingesting |
| `--location CITY` | Override location for all files (also writes GPS to EXIF) |
| `--year YYYY` | Override year in timestamps (also updates EXIF metadata) |
| `--month MM` | Override month (1-12) in timestamps (also updates EXIF metadata) |

### Examples

```bash
# Basic ingest
uv run media-organizer ~/Photos/Camera ~/Photos/Archive

# See what would happen first
uv run media-organizer ~/Photos/Camera ~/Photos/Archive --dry-run

# Max speed with 8 workers
uv run media-organizer ~/Photos/Camera ~/Photos/Archive --workers 8

# Pick up where you left off after a crash
uv run media-organizer ~/Photos/Camera ~/Photos/Archive --resume

# Catch near-identical photos too
uv run media-organizer ~/Photos/Camera ~/Photos/Archive --perceptual

# Check your archive for corruption
uv run media-organizer ~/Photos/Archive --verify

# Override location when GPS is missing
uv run media-organizer ~/Photos/Rome ~/Photos/Archive --location "Rome"

# Fix year and month on old scanned photos
uv run media-organizer ~/Scans ~/Archive --year 2018 --month 3

# Combine everything
uv run media-organizer ~/Trip ~/Archive --location "Barcelona" --year 2023 --month 6 --perceptual
```

### Live progress

The ingest shows real-time stats as it works:

```
Processing media: 142file [00:08, 17.3file/s, processed=128, duplicates=12, errors=2]
```

---

## How it works

```
scan source/        Recursively find all media files (generator-based, constant memory)
       |
   file_hash()      BLAKE3 content hash, read in 1 MB chunks
       |
   db.exists()      Check SQLite index for exact duplicates
       |
extract_metadata()  ExifTool -> Pillow -> file mtime fallback chain
       |
  apply overrides   --year, --month, --location replace extracted values
       |
 write_metadata()   Write corrected EXIF data back to the file (via ExifTool)
       |
reverse_geocode()   Nominatim (online) -> reverse_geocoder (offline) -> Unknown_location
       |
  target_path()     Build archive/YYYY/MM/DDd_HHh_MMmin_SSs_City.ext with collision handling
       |
   move_file()      Move to archive, record in database
```

---

## Project structure

```
media_organizer/
  cli.py          Command-line interface
  pipeline.py     Ingest orchestration and verification
  scanner.py      Generator-based filesystem scanning
  hashing.py      BLAKE3 content hashing and perceptual hashing
  metadata.py     ExifTool / Pillow / mtime extraction + GPS reverse geocoding
  organizer.py    Date-based archive path computation
  database.py     Thread-safe SQLite access layer
  utils.py        Shared constants and logger
```

## Running tests

```bash
uv run pytest
```
