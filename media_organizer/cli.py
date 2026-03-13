"""Command-line interface for the media ingest tool."""

import argparse
import logging
import sys

from .pipeline import run_pipeline, run_verify
from .utils import logger


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="media-organizer",
        description="Ingest and organise media files into a structured archive.",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="PATH",
        help="source and archive directories (ingest), or archive directory (--verify)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without moving files",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip files already processed in a previous run",
    )
    parser.add_argument(
        "--perceptual",
        action="store_true",
        help="Enable perceptual (visual) duplicate detection",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify archive integrity instead of ingesting",
    )
    parser.add_argument(
        "--location",
        type=str,
        default=None,
        metavar="CITY",
        help="Override location for all files (e.g. 'Paris'). "
        "Also writes GPS coordinates back to file metadata.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        metavar="YYYY",
        help="Override year in file timestamps (also updates EXIF metadata)",
    )
    parser.add_argument(
        "--month",
        type=int,
        default=None,
        choices=range(1, 13),
        metavar="MM",
        help="Override month in file timestamps (1-12, also updates EXIF metadata)",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if args.verify:
        if len(args.paths) != 1:
            parser.error("--verify requires exactly one argument: archive directory")
        mismatches = run_verify(args.paths[0], workers=args.workers)
        sys.exit(1 if mismatches else 0)
    else:
        if len(args.paths) != 2:
            parser.error("ingest requires two arguments: source and archive directories")
        source, archive = args.paths
        stats = run_pipeline(
            source,
            archive,
            workers=args.workers,
            dry_run=args.dry_run,
            resume=args.resume,
            perceptual=args.perceptual,
            location=args.location,
            year=args.year,
            month=args.month,
        )
        sys.exit(1 if stats.errors else 0)
