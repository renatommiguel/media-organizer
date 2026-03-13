"""SQLite access layer — all database logic lives here."""

import sqlite3
import threading
from pathlib import Path
from typing import Optional


class ArchiveDB:
    """Thread-safe SQLite wrapper for the archive index."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
        self._batch_depth = 0
        self._create_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        with self._lock:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS files (
                    hash  TEXT PRIMARY KEY,
                    path  TEXT NOT NULL,
                    size  INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS metadata (
                    path      TEXT PRIMARY KEY,
                    timestamp INTEGER,
                    camera    TEXT,
                    gps_lat   REAL,
                    gps_lon   REAL
                );

                CREATE TABLE IF NOT EXISTS processed_files (
                    path TEXT PRIMARY KEY
                );

                CREATE TABLE IF NOT EXISTS hash_cache (
                    path  TEXT PRIMARY KEY,
                    size  INTEGER NOT NULL,
                    mtime REAL NOT NULL,
                    hash  TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS phashes (
                    path TEXT PRIMARY KEY,
                    hash TEXT NOT NULL
                );
            """)

    # ------------------------------------------------------------------
    # Batch helpers
    # ------------------------------------------------------------------

    def begin_batch(self) -> None:
        """Enter batch mode — commits are deferred until ``end_batch``."""
        self._batch_depth += 1

    def end_batch(self) -> None:
        """Commit outstanding writes and leave batch mode."""
        self._batch_depth = max(0, self._batch_depth - 1)
        if self._batch_depth == 0:
            with self._lock:
                self.conn.commit()

    def _maybe_commit(self) -> None:
        if self._batch_depth == 0:
            self.conn.commit()

    # ------------------------------------------------------------------
    # Files table
    # ------------------------------------------------------------------

    def exists(self, file_hash: str) -> bool:
        with self._lock:
            row = self.conn.execute(
                "SELECT 1 FROM files WHERE hash = ?", (file_hash,)
            ).fetchone()
        return row is not None

    def insert(self, file_hash: str, path: str, size: int) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO files (hash, path, size) VALUES (?, ?, ?)",
                (file_hash, path, size),
            )
            self._maybe_commit()

    def get_all_files(self) -> list[tuple[str, str, int]]:
        with self._lock:
            return self.conn.execute(
                "SELECT hash, path, size FROM files"
            ).fetchall()

    def remove_file(self, file_hash: str) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM files WHERE hash = ?", (file_hash,))
            self._maybe_commit()

    # ------------------------------------------------------------------
    # Metadata table
    # ------------------------------------------------------------------

    def insert_metadata(
        self,
        path: str,
        timestamp: int,
        camera: str = "",
        gps_lat: Optional[float] = None,
        gps_lon: Optional[float] = None,
    ) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO metadata "
                "(path, timestamp, camera, gps_lat, gps_lon) "
                "VALUES (?, ?, ?, ?, ?)",
                (path, timestamp, camera, gps_lat, gps_lon),
            )
            self._maybe_commit()

    # ------------------------------------------------------------------
    # Processed files (crash-safe resume)
    # ------------------------------------------------------------------

    def is_processed(self, path: str) -> bool:
        with self._lock:
            row = self.conn.execute(
                "SELECT 1 FROM processed_files WHERE path = ?", (path,)
            ).fetchone()
        return row is not None

    def mark_processed(self, path: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR IGNORE INTO processed_files (path) VALUES (?)",
                (path,),
            )
            self._maybe_commit()

    def clear_processed(self) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM processed_files")
            self.conn.commit()

    # ------------------------------------------------------------------
    # Hash cache (performance optimisation)
    # ------------------------------------------------------------------

    def get_cached_hash(
        self, path: str, size: int, mtime: float
    ) -> Optional[str]:
        with self._lock:
            row = self.conn.execute(
                "SELECT hash FROM hash_cache "
                "WHERE path = ? AND size = ? AND mtime = ?",
                (path, size, mtime),
            ).fetchone()
        return row[0] if row else None

    def cache_hash(
        self, path: str, size: int, mtime: float, file_hash: str
    ) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO hash_cache "
                "(path, size, mtime, hash) VALUES (?, ?, ?, ?)",
                (path, size, mtime, file_hash),
            )
            self._maybe_commit()

    # ------------------------------------------------------------------
    # Perceptual hashes
    # ------------------------------------------------------------------

    def insert_perceptual_hash(self, path: str, phash: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO phashes (path, hash) "
                "VALUES (?, ?)",
                (path, phash),
            )
            self._maybe_commit()

    def get_all_perceptual_hashes(self) -> list[tuple[str, str]]:
        with self._lock:
            return self.conn.execute(
                "SELECT path, hash FROM phashes"
            ).fetchall()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self.conn.close()
