"""Orchestrates the ingest pipeline — connects all modules."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from tqdm import tqdm

from .database import ArchiveDB
from .hashing import file_hash, compute_perceptual_hash, hamming_distance
from .metadata import extract_metadata, reverse_geocode, write_metadata
from .organizer import target_path, move_file
from .scanner import scan
from .utils import logger

PERCEPTUAL_THRESHOLD = 5
BATCH_SIZE = 50


@dataclass
class IngestStats:
    processed: int = 0
    duplicates: int = 0
    perceptual_dupes: int = 0
    errors: int = 0
    skipped: int = 0


@dataclass
class _FileResult:
    source: Path
    outcome: str  # "moved", "duplicate", "perceptual_dup", "error", "skipped"
    dest: Optional[str] = None
    error: Optional[str] = None


# ------------------------------------------------------------------
# Single-file processor (runs inside worker threads)
# ------------------------------------------------------------------


def _process_file(
    filepath: Path,
    archive_root: Path,
    db: ArchiveDB,
    *,
    dry_run: bool = False,
    perceptual: bool = False,
    location: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> _FileResult:
    try:
        stat = filepath.stat()

        # --- hash (with cache) ---
        cached = db.get_cached_hash(str(filepath), stat.st_size, stat.st_mtime)
        if cached:
            content_hash = cached
        else:
            content_hash = file_hash(filepath)
            db.cache_hash(str(filepath), stat.st_size, stat.st_mtime, content_hash)

        # --- exact duplicate check ---
        if db.exists(content_hash):
            if not dry_run:
                filepath.unlink()
            return _FileResult(filepath, "duplicate")

        # --- perceptual duplicate check ---
        if perceptual:
            phash = compute_perceptual_hash(filepath)
            if phash:
                for stored_path, stored_phash in db.get_all_perceptual_hashes():
                    if hamming_distance(phash, stored_phash) <= PERCEPTUAL_THRESHOLD:
                        logger.debug(
                            "Perceptual duplicate: %s ≈ %s", filepath, stored_path
                        )
                        if not dry_run:
                            filepath.unlink()
                        return _FileResult(filepath, "perceptual_dup")

        # --- metadata ---
        meta = extract_metadata(filepath)
        timestamp = meta["timestamp"]

        # --- apply CLI overrides for year/month ---
        if year is not None or month is not None:
            timestamp = timestamp.replace(
                year=year if year is not None else timestamp.year,
                month=month if month is not None else timestamp.month,
            )

        # --- resolve city name ---
        city = location if location is not None else reverse_geocode(meta["gps_lat"], meta["gps_lon"])

        # --- write overrides back to file metadata ---
        needs_write = (year is not None or month is not None or location is not None)
        if needs_write and not dry_run:
            write_metadata(
                filepath,
                timestamp=timestamp if (year is not None or month is not None) else None,
                location=location,
            )

        # --- build filename: DDd_HHh_MMmin_SSs_City.ext ---
        new_name = f"{timestamp:%d_%Hh%Mm%Ss}_{city}{filepath.suffix.lower()}"

        # --- destination ---
        dest = target_path(archive_root, timestamp, new_name)

        if dry_run:
            logger.info("[dry-run] Would move %s → %s", filepath, dest)
        else:
            move_file(filepath, dest)

            db.begin_batch()
            db.insert(content_hash, str(dest), stat.st_size)
            db.insert_metadata(
                str(dest),
                int(timestamp.timestamp()),
                meta.get("camera", ""),
                meta.get("gps_lat"),
                meta.get("gps_lon"),
            )
            if perceptual and phash:
                db.insert_perceptual_hash(str(dest), phash)
            db.mark_processed(str(filepath))
            db.end_batch()

        return _FileResult(filepath, "moved", dest=str(dest))

    except Exception as exc:
        logger.error("Failed to process %s: %s", filepath, exc)
        return _FileResult(filepath, "error", error=str(exc))


# ------------------------------------------------------------------
# Main ingest pipeline
# ------------------------------------------------------------------


def run_pipeline(
    source: str | Path,
    archive: str | Path,
    *,
    workers: int = 4,
    dry_run: bool = False,
    resume: bool = False,
    perceptual: bool = False,
    location: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> IngestStats:
    """Run the full ingest pipeline.

    Streams files from *source*, hashes, deduplicates, extracts metadata,
    and moves them into the date-based archive under *archive*.
    """
    source = Path(source)
    archive = Path(archive)
    archive.mkdir(parents=True, exist_ok=True)

    db_path = archive / ".media_ingest.db"
    db = ArchiveDB(db_path)
    stats = IngestStats()
    progress = tqdm(desc="Processing media", unit="file")

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            pending: set = set()
            max_pending = workers * 2

            for filepath in scan(source):
                if resume and db.is_processed(str(filepath)):
                    stats.skipped += 1
                    continue

                future = executor.submit(
                    _process_file,
                    filepath,
                    archive,
                    db,
                    dry_run=dry_run,
                    perceptual=perceptual,
                    location=location,
                    year=year,
                    month=month,
                )
                pending.add(future)

                if len(pending) >= max_pending:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for f in done:
                        _tally(f, stats, progress)

            for f in as_completed(pending):
                _tally(f, stats, progress)
    finally:
        progress.close()
        db.close()

    _print_summary(stats)
    return stats


def _tally(future, stats: IngestStats, progress: tqdm) -> None:
    progress.update(1)
    try:
        result: _FileResult = future.result()
    except Exception as exc:
        stats.errors += 1
        logger.error("Unexpected worker error: %s", exc)
        return

    match result.outcome:
        case "moved":
            stats.processed += 1
        case "duplicate":
            stats.duplicates += 1
        case "perceptual_dup":
            stats.perceptual_dupes += 1
        case "error":
            stats.errors += 1
        case "skipped":
            stats.skipped += 1

    progress.set_postfix(
        processed=stats.processed,
        duplicates=stats.duplicates,
        errors=stats.errors,
    )


def _print_summary(stats: IngestStats) -> None:
    print("\n--- Ingest Summary ---")
    print(f"  Files moved:            {stats.processed}")
    print(f"  Exact duplicates:       {stats.duplicates}")
    print(f"  Perceptual duplicates:  {stats.perceptual_dupes}")
    print(f"  Errors:                 {stats.errors}")
    print(f"  Skipped (resumed):      {stats.skipped}")


# ------------------------------------------------------------------
# Archive verification
# ------------------------------------------------------------------


def run_verify(
    archive: str | Path,
    *,
    workers: int = 4,
) -> list[tuple[str, str, str, str]]:
    """Verify archive integrity by recomputing hashes.

    Returns a list of ``(status, path, expected, actual)`` tuples for
    every mismatch or missing file.
    """
    archive = Path(archive)
    db_path = archive / ".media_ingest.db"
    if not db_path.exists():
        logger.error("No database found at %s", db_path)
        return []

    db = ArchiveDB(db_path)
    records = db.get_all_files()
    mismatches: list[tuple[str, str, str, str]] = []

    progress = tqdm(records, desc="Verifying archive", unit="file")
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_verify_one, stored_hash, path): (stored_hash, path)
                for stored_hash, path, _size in records
            }
            for future in as_completed(futures):
                progress.update(1)
                entry = future.result()
                if entry:
                    mismatches.append(entry)
    finally:
        progress.close()
        db.close()

    if mismatches:
        print(f"\n{len(mismatches)} integrity issue(s) found:")
        for status, path, expected, actual in mismatches:
            print(f"  [{status}] {path}  expected={expected}  actual={actual}")
    else:
        print(f"\nAll {len(records)} files verified OK.")

    return mismatches


def _verify_one(
    stored_hash: str, path: str
) -> Optional[tuple[str, str, str, str]]:
    filepath = Path(path)
    if not filepath.exists():
        return ("MISSING", path, stored_hash, "")
    try:
        actual = file_hash(filepath)
    except Exception as exc:
        return ("ERROR", path, stored_hash, str(exc))
    if actual != stored_hash:
        return ("CORRUPTED", path, stored_hash, actual)
    return None
