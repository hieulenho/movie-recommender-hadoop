"""Create deterministic time-aware train/test splits for offline evaluation."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable, Mapping, Sequence


RATINGS_HEADER = ["userId", "movieId", "rating", "date"]
SPLIT_METHOD = "leave-one-out-by-time"
TIE_BREAKING_RULE = "Sort by date ascending, then movieId ascending; hold out the final row."


class SplitRatingsError(Exception):
    """Fatal split error suitable for concise CLI reporting."""


@dataclass(frozen=True, order=True)
class RatingRecord:
    """One validated normalized rating row."""

    user_id: int
    movie_id: int
    rating: int
    date: str

    def csv_row(self) -> list[object]:
        return [self.user_id, self.movie_id, self.rating, self.date]


@dataclass(frozen=True)
class RatingLoadResult:
    """Loaded unique ratings and duplicate/input counts."""

    records: list[RatingRecord]
    input_rows: int
    exact_duplicate_rows_ignored: int

    @property
    def accepted_ratings(self) -> int:
        return len(self.records)


@dataclass(frozen=True)
class SplitResult:
    """Train/test records plus machine-readable split statistics."""

    train_records: list[RatingRecord]
    test_records: list[RatingRecord]
    stats: dict[str, object]


def _parse_positive_id(value: str, field_name: str, line_number: int) -> int:
    text = value.strip()
    if not text.isdigit() or int(text) <= 0:
        raise SplitRatingsError(f"Line {line_number}: {field_name} must be a positive integer.")
    return int(text)


def _parse_rating(value: str, line_number: int) -> int:
    text = value.strip()
    if not text.isdigit():
        raise SplitRatingsError(f"Line {line_number}: rating must be an integer from 1 through 5.")
    rating = int(text)
    if rating < 1 or rating > 5:
        raise SplitRatingsError(f"Line {line_number}: rating must be an integer from 1 through 5.")
    return rating


def _parse_iso_date(value: str, line_number: int) -> str:
    text = value.strip()
    try:
        parsed = dt.date.fromisoformat(text)
    except ValueError as exc:
        raise SplitRatingsError(f"Line {line_number}: date must be a valid YYYY-MM-DD date.") from exc
    if parsed.isoformat() != text:
        raise SplitRatingsError(f"Line {line_number}: date must be in YYYY-MM-DD format.")
    return text


def _require_input_file(path: Path) -> None:
    if not path.exists():
        raise SplitRatingsError(f"Input file does not exist: {path}")
    if not path.is_file():
        raise SplitRatingsError(f"Input path is not a file: {path}")


def _ensure_outputs_do_not_overwrite_input(input_path: Path, output_paths: Sequence[Path]) -> None:
    resolved_input = input_path.resolve()
    for output_path in output_paths:
        if output_path.resolve() == resolved_input:
            raise SplitRatingsError(f"Output path would overwrite the input file: {output_path}")


def load_normalized_ratings(input_path: Path | str) -> RatingLoadResult:
    """Load normalized ratings with strict validation and duplicate detection."""

    path = Path(input_path)
    _require_input_file(path)

    records: list[RatingRecord] = []
    by_user_movie: dict[tuple[int, int], RatingRecord] = {}
    input_rows = 0
    exact_duplicates = 0

    try:
        with path.open("r", encoding="utf-8", newline="") as input_file:
            reader = csv.reader(input_file)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise SplitRatingsError("Input CSV is empty; expected header userId,movieId,rating,date.") from exc

            if header != RATINGS_HEADER:
                raise SplitRatingsError("Input CSV header must be exactly: userId,movieId,rating,date")

            for line_number, row in enumerate(reader, start=2):
                input_rows += 1
                if len(row) != 4:
                    raise SplitRatingsError(f"Line {line_number}: expected exactly 4 CSV fields.")

                user_id = _parse_positive_id(row[0], "userId", line_number)
                movie_id = _parse_positive_id(row[1], "movieId", line_number)
                rating = _parse_rating(row[2], line_number)
                date = _parse_iso_date(row[3], line_number)
                record = RatingRecord(user_id, movie_id, rating, date)
                key = (user_id, movie_id)

                previous = by_user_movie.get(key)
                if previous is not None:
                    if previous == record:
                        exact_duplicates += 1
                        continue
                    raise SplitRatingsError(
                        "Line "
                        f"{line_number}: conflicting duplicate rating for userId={user_id}, "
                        f"movieId={movie_id}."
                    )

                by_user_movie[key] = record
                records.append(record)
    except OSError as exc:
        raise OSError(f"Cannot read input file {path}: {exc}") from exc

    if not records:
        raise SplitRatingsError("Input CSV contains no rating rows after the header.")

    return RatingLoadResult(records=records, input_rows=input_rows, exact_duplicate_rows_ignored=exact_duplicates)


def split_leave_one_out(load_result: RatingLoadResult) -> SplitResult:
    """Split records by user using the deterministic leave-one-out-by-time rule."""

    by_user: dict[int, list[RatingRecord]] = {}
    for record in load_result.records:
        by_user.setdefault(record.user_id, []).append(record)

    train_records: list[RatingRecord] = []
    test_records: list[RatingRecord] = []
    for user_id in sorted(by_user):
        sorted_ratings = sorted(by_user[user_id], key=lambda item: (item.date, item.movie_id))
        if len(sorted_ratings) >= 2:
            train_records.extend(sorted_ratings[:-1])
            test_records.append(sorted_ratings[-1])
        else:
            train_records.extend(sorted_ratings)

    output_key = lambda item: (item.user_id, item.date, item.movie_id)
    train_records = sorted(train_records, key=output_key)
    test_records = sorted(test_records, key=output_key)
    item_ids = {record.movie_id for record in load_result.records}
    stats = {
        "input_rows": load_result.input_rows,
        "accepted_ratings": load_result.accepted_ratings,
        "exact_duplicate_rows_ignored": load_result.exact_duplicate_rows_ignored,
        "users": len(by_user),
        "items": len(item_ids),
        "users_with_test_rating": len(test_records),
        "users_without_test_rating": len(by_user) - len(test_records),
        "train_rows": len(train_records),
        "test_rows": len(test_records),
        "split_method": SPLIT_METHOD,
        "holdout_per_user": 1,
        "tie_breaking_rule": TIE_BREAKING_RULE,
    }
    if stats["train_rows"] + stats["test_rows"] != stats["accepted_ratings"]:
        raise SplitRatingsError("Internal split error: train_rows + test_rows != accepted_ratings.")

    return SplitResult(train_records=train_records, test_records=test_records, stats=stats)


def write_ratings_csv(records: Iterable[RatingRecord], output_path: Path | str) -> None:
    """Write normalized rating rows with the exact expected header."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.writer(output_file, lineterminator="\n")
            writer.writerow(RATINGS_HEADER)
            for record in records:
                writer.writerow(record.csv_row())
    except OSError as exc:
        raise OSError(f"Cannot write ratings CSV {path}: {exc}") from exc


def write_stats_json(stats: Mapping[str, object], output_path: Path | str) -> None:
    """Write readable UTF-8 split statistics JSON."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(
            json.dumps(dict(stats), indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise OSError(f"Cannot write split statistics {path}: {exc}") from exc


def run_split(
    input_path: Path | str,
    train_output: Path | str,
    test_output: Path | str,
    stats_output: Path | str,
) -> dict[str, object]:
    """Run the full split workflow and write all requested artifacts."""

    input_file = Path(input_path)
    train_path = Path(train_output)
    test_path = Path(test_output)
    stats_path = Path(stats_output)
    _ensure_outputs_do_not_overwrite_input(input_file, [train_path, test_path, stats_path])

    load_result = load_normalized_ratings(input_file)
    split_result = split_leave_one_out(load_result)
    write_ratings_csv(split_result.train_records, train_path)
    write_ratings_csv(split_result.test_records, test_path)
    write_stats_json(split_result.stats, stats_path)
    return split_result.stats


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split normalized ratings into deterministic train/test CSV files for evaluation.",
    )
    parser.add_argument("--input", required=True, help="Normalized ratings CSV input.")
    parser.add_argument("--train-output", required=True, help="Path to write train ratings CSV.")
    parser.add_argument("--test-output", required=True, help="Path to write test ratings CSV.")
    parser.add_argument("--stats-output", required=True, help="Path to write split statistics JSON.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        stats = run_split(args.input, args.train_output, args.test_output, args.stats_output)
    except (SplitRatingsError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(
        "Split complete: "
        f"{stats['train_rows']} train rows, "
        f"{stats['test_rows']} test rows, "
        f"{stats['users_with_test_rating']} users with held-out ratings."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
