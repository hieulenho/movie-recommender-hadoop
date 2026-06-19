"""Preprocess Netflix Prize-style rating files into normalized CSV."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import re
import sys
from typing import Iterable, Sequence


CSV_HEADER = ["userId", "movieId", "rating", "date"]
INVALID_REASON_KEYS = [
    "rating_before_movie_header",
    "wrong_field_count",
    "invalid_user_id",
    "invalid_rating",
    "invalid_date",
    "malformed_movie_header",
    "invalid_movie_id",
]
MOVIE_HEADER_RE = re.compile(r"^([1-9]\d*):$")
ZERO_MOVIE_HEADER_RE = re.compile(r"^0+:$")
NEGATIVE_MOVIE_HEADER_RE = re.compile(r"^-\d+:$")
POSITIVE_INTEGER_RE = re.compile(r"^[1-9]\d*$")
RATING_RE = re.compile(r"^[1-5]$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

NormalizedRecord = tuple[int, int, int, str]


class PreprocessError(Exception):
    """Fatal preprocessing error suitable for concise CLI reporting."""


def parse_movie_header(line: str) -> int | None:
    """Return a movie ID for a valid header, or None for a rating-like line.

    Lines ending in a colon are considered header-like. If they are not a
    positive integer followed by a colon, ValueError is raised with a reason
    string used by the statistics collector.
    """

    text = line.strip()
    if not text.endswith(":"):
        return None

    match = MOVIE_HEADER_RE.fullmatch(text)
    if match:
        return int(match.group(1))

    if ZERO_MOVIE_HEADER_RE.fullmatch(text) or NEGATIVE_MOVIE_HEADER_RE.fullmatch(text):
        raise ValueError("invalid_movie_id")

    raise ValueError("malformed_movie_header")


def parse_rating_row(line: str, movie_id: int | None) -> NormalizedRecord:
    """Parse and validate one rating row for the current movie ID."""

    if movie_id is None:
        raise ValueError("rating_before_movie_header")

    fields = [field.strip() for field in line.split(",")]
    if len(fields) != 3:
        raise ValueError("wrong_field_count")

    user_text, rating_text, date_text = fields
    if not POSITIVE_INTEGER_RE.fullmatch(user_text):
        raise ValueError("invalid_user_id")

    if not RATING_RE.fullmatch(rating_text):
        raise ValueError("invalid_rating")

    if not ISO_DATE_RE.fullmatch(date_text):
        raise ValueError("invalid_date")

    try:
        dt.date.fromisoformat(date_text)
    except ValueError as exc:
        raise ValueError("invalid_date") from exc

    return (int(user_text), movie_id, int(rating_text), date_text)


def discover_input_files(input_dir: Path | str) -> list[Path]:
    """Find Netflix raw files matching mv_*.txt recursively in sorted order."""

    root = Path(input_dir)
    if not root.exists():
        raise PreprocessError(f"Input directory does not exist: {root}")
    if not root.is_dir():
        raise PreprocessError(f"Input path is not a directory: {root}")

    files = sorted(
        (path for path in root.rglob("mv_*.txt") if path.is_file()),
        key=lambda path: path.as_posix(),
    )
    if not files:
        raise PreprocessError(f"No mv_*.txt files found in input directory: {root}")
    return files


def create_initial_stats(file_count: int) -> dict[str, object]:
    """Create a deterministic statistics dictionary."""

    return {
        "files_discovered": file_count,
        "files_processed": 0,
        "movie_headers": 0,
        "input_rating_rows": 0,
        "valid_rating_rows": 0,
        "invalid_rating_rows": 0,
        "blank_lines": 0,
        "duplicate_rows_removed": 0,
        "output_rows": 0,
        "invalid_reason_counts": {key: 0 for key in INVALID_REASON_KEYS},
    }


def _increment_invalid(stats: dict[str, object], reason: str) -> None:
    invalid_counts = stats["invalid_reason_counts"]
    if not isinstance(invalid_counts, dict):
        raise TypeError("invalid_reason_counts must be a dictionary")
    if reason not in invalid_counts:
        invalid_counts[reason] = 0
    invalid_counts[reason] += 1
    stats["invalid_rating_rows"] = int(stats["invalid_rating_rows"]) + 1


def preprocess_files(input_files: Sequence[Path]) -> tuple[list[NormalizedRecord], dict[str, object]]:
    """Parse input files, validate rows, and remove exact duplicate records."""

    if not input_files:
        raise PreprocessError("No input files were provided for preprocessing.")

    stats = create_initial_stats(len(input_files))
    records: list[NormalizedRecord] = []
    seen_records: set[NormalizedRecord] = set()

    for path in input_files:
        current_movie_id: int | None = None
        try:
            with path.open("r", encoding="utf-8") as input_file:
                for raw_line in input_file:
                    line = raw_line.strip()
                    if not line:
                        stats["blank_lines"] = int(stats["blank_lines"]) + 1
                        continue

                    try:
                        parsed_movie_id = parse_movie_header(line)
                    except ValueError as exc:
                        stats["input_rating_rows"] = int(stats["input_rating_rows"]) + 1
                        _increment_invalid(stats, str(exc))
                        continue

                    if parsed_movie_id is not None:
                        current_movie_id = parsed_movie_id
                        stats["movie_headers"] = int(stats["movie_headers"]) + 1
                        continue

                    stats["input_rating_rows"] = int(stats["input_rating_rows"]) + 1
                    try:
                        record = parse_rating_row(line, current_movie_id)
                    except ValueError as exc:
                        _increment_invalid(stats, str(exc))
                        continue

                    stats["valid_rating_rows"] = int(stats["valid_rating_rows"]) + 1
                    if record in seen_records:
                        stats["duplicate_rows_removed"] = int(stats["duplicate_rows_removed"]) + 1
                        continue

                    seen_records.add(record)
                    records.append(record)
        except OSError as exc:
            raise OSError(f"Cannot read input file {path}: {exc}") from exc

        stats["files_processed"] = int(stats["files_processed"]) + 1

    stats["output_rows"] = len(records)
    return records, stats


def preprocess_directory(input_dir: Path | str) -> tuple[list[NormalizedRecord], dict[str, object]]:
    """Discover and preprocess all Netflix raw files in an input directory."""

    input_files = discover_input_files(input_dir)
    return preprocess_files(input_files)


def write_normalized_csv(records: Iterable[NormalizedRecord], output_path: Path | str) -> None:
    """Write normalized records to a UTF-8 CSV file with the required header."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.writer(output_file, lineterminator="\n")
            writer.writerow(CSV_HEADER)
            writer.writerows(records)
    except OSError as exc:
        raise OSError(f"Cannot write CSV output {path}: {exc}") from exc


def write_statistics_json(stats: dict[str, object], output_path: Path | str) -> None:
    """Write preprocessing statistics as readable UTF-8 JSON."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(
            json.dumps(stats, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise OSError(f"Cannot write statistics output {path}: {exc}") from exc


def ensure_outputs_do_not_overwrite_inputs(
    input_files: Sequence[Path],
    output_paths: Sequence[Path | str],
) -> None:
    """Fail if an output path resolves to one of the input files."""

    input_file_paths = {path.resolve() for path in input_files}
    for output_path in output_paths:
        resolved_output = Path(output_path).resolve()
        if resolved_output in input_file_paths:
            raise PreprocessError(f"Output path would overwrite an input file: {output_path}")


def run_preprocessing(
    input_dir: Path | str,
    output_path: Path | str,
    stats_output_path: Path | str,
) -> dict[str, object]:
    """Run discovery, preprocessing, CSV writing, and statistics writing."""

    input_files = discover_input_files(input_dir)
    ensure_outputs_do_not_overwrite_inputs(input_files, [output_path, stats_output_path])
    records, stats = preprocess_files(input_files)
    write_normalized_csv(records, output_path)
    write_statistics_json(stats, stats_output_path)
    return stats


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the preprocessor."""

    parser = argparse.ArgumentParser(
        description="Normalize Netflix Prize-style mv_*.txt rating files into CSV.",
    )
    parser.add_argument("--input-dir", required=True, help="Directory containing mv_*.txt files.")
    parser.add_argument("--output", required=True, help="Path to write normalized ratings CSV.")
    parser.add_argument("--stats-output", required=True, help="Path to write statistics JSON.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        stats = run_preprocessing(args.input_dir, args.output, args.stats_output)
    except (PreprocessError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(
        "Preprocessing complete: "
        f"{stats['files_processed']} files processed, "
        f"{stats['output_rows']} output rows, "
        f"{stats['duplicate_rows_removed']} duplicates removed, "
        f"{stats['invalid_rating_rows']} invalid rows."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
