"""Create a true timestamp-aware MovieLens 1M leave-one-out split."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Mapping, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.preprocess_movielens_1m import RATINGS_HEADER, timestamp_to_utc_text


TRAIN_TEST_HEADER = ["userId", "movieId", "rating", "date"]
AUDIT_HEADER = RATINGS_HEADER
SPLIT_METHOD = "leave-one-out-by-exact-timestamp"


class MovieLensSplitError(Exception):
    """Fatal MovieLens split error."""


@dataclass(frozen=True)
class TimestampedRating:
    user_id: int
    movie_id: int
    rating: int
    timestamp: int
    datetime_utc: str
    date: str

    def train_test_row(self) -> list[object]:
        return [self.user_id, self.movie_id, self.rating, self.date]

    def audit_row(self) -> list[object]:
        return [self.user_id, self.movie_id, self.rating, self.timestamp, self.datetime_utc, self.date]


def parse_positive_int(text: str, field_name: str, line_number: int) -> int:
    if not text.strip().isdigit():
        raise MovieLensSplitError(f"Line {line_number}: {field_name} must be a positive integer.")
    value = int(text)
    if value <= 0:
        raise MovieLensSplitError(f"Line {line_number}: {field_name} must be a positive integer.")
    return value


def load_timestamped_ratings(path: Path | str) -> list[TimestampedRating]:
    source = Path(path)
    if not source.is_file():
        raise MovieLensSplitError(f"Input ratings_with_timestamp.csv does not exist: {source}")
    records: list[TimestampedRating] = []
    seen: set[tuple[int, int]] = set()
    with source.open("r", encoding="utf-8", newline="") as input_file:
        reader = csv.reader(input_file)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise MovieLensSplitError("Input ratings_with_timestamp.csv is empty.") from exc
        if header != RATINGS_HEADER:
            raise MovieLensSplitError("Input header must be exactly: " + ",".join(RATINGS_HEADER))
        for line_number, row in enumerate(reader, start=2):
            if len(row) != 6:
                raise MovieLensSplitError(f"Line {line_number}: expected exactly 6 CSV fields.")
            user_id = parse_positive_int(row[0], "userId", line_number)
            movie_id = parse_positive_int(row[1], "movieId", line_number)
            rating = parse_positive_int(row[2], "rating", line_number)
            if rating < 1 or rating > 5:
                raise MovieLensSplitError(f"Line {line_number}: rating must be from 1 through 5.")
            timestamp = parse_positive_int(row[3], "timestamp", line_number)
            expected_datetime = timestamp_to_utc_text(timestamp)
            if row[4] != expected_datetime:
                raise MovieLensSplitError(f"Line {line_number}: dateTimeUtc does not match timestamp UTC conversion.")
            if row[5] != expected_datetime[:10]:
                raise MovieLensSplitError(f"Line {line_number}: date does not match timestamp UTC conversion.")
            key = (user_id, movie_id)
            if key in seen:
                raise MovieLensSplitError(f"Line {line_number}: duplicate userId/movieId row.")
            seen.add(key)
            records.append(TimestampedRating(user_id, movie_id, rating, timestamp, row[4], row[5]))
    return sorted(records, key=lambda item: (item.user_id, item.timestamp, item.movie_id))


def split_leave_one_out_by_timestamp(records: Sequence[TimestampedRating]) -> tuple[list[TimestampedRating], list[TimestampedRating], dict[str, object]]:
    by_user: dict[int, list[TimestampedRating]] = {}
    for record in records:
        by_user.setdefault(record.user_id, []).append(record)

    train: list[TimestampedRating] = []
    test: list[TimestampedRating] = []
    users_without_test = 0
    for user_id in sorted(by_user):
        ratings = sorted(by_user[user_id], key=lambda item: (item.timestamp, item.movie_id))
        if len(ratings) >= 2:
            train.extend(ratings[:-1])
            test.append(ratings[-1])
        else:
            train.extend(ratings)
            users_without_test += 1

    train.sort(key=lambda item: (item.user_id, item.timestamp, item.movie_id))
    test.sort(key=lambda item: (item.user_id, item.timestamp, item.movie_id))
    overlap = {(row.user_id, row.movie_id) for row in train} & {(row.user_id, row.movie_id) for row in test}
    if overlap:
        raise MovieLensSplitError("Train/test overlap detected.")
    train_by_user: dict[int, list[TimestampedRating]] = {}
    for row in train:
        train_by_user.setdefault(row.user_id, []).append(row)
    for row in test:
        for train_row in train_by_user.get(row.user_id, []):
            if row.timestamp < train_row.timestamp:
                raise MovieLensSplitError(f"Test timestamp is earlier than train timestamp for user {row.user_id}.")
    train_item_ids = {row.movie_id for row in train}
    test_item_ids = {row.movie_id for row in test}
    train_counts = [len(rows) for rows in train_by_user.values()]
    total = len(records)
    stats = {
        "split_method": SPLIT_METHOD,
        "source_has_timestamps": True,
        "timezone": "UTC",
        "tie_breaking_rule": "highest movieId for equal timestamps",
        "input_ratings": total,
        "train_rows": len(train),
        "test_rows": len(test),
        "train_percentage": len(train) / total if total else 0.0,
        "test_percentage": len(test) / total if total else 0.0,
        "users": len(by_user),
        "users_with_test_rating": len(test),
        "users_without_test_rating": users_without_test,
        "train_test_overlap_rows": len(overlap),
        "cold_start_test_items": len(test_item_ids - train_item_ids),
        "test_items_absent_from_train": sorted(test_item_ids - train_item_ids),
        "minimum_train_ratings_per_user": min(train_counts) if train_counts else 0,
        "maximum_train_ratings_per_user": max(train_counts) if train_counts else 0,
        "average_train_ratings_per_user": sum(train_counts) / len(train_counts) if train_counts else 0.0,
    }
    if stats["train_rows"] + stats["test_rows"] != total:
        raise MovieLensSplitError("Internal split error: train_rows + test_rows != input_ratings.")
    return train, test, stats


def write_train_test_csv(records: Sequence[TimestampedRating], path: Path | str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file, lineterminator="\n")
        writer.writerow(TRAIN_TEST_HEADER)
        for record in records:
            writer.writerow(record.train_test_row())


def write_audit_csv(records: Sequence[TimestampedRating], path: Path | str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file, lineterminator="\n")
        writer.writerow(AUDIT_HEADER)
        for record in records:
            writer.writerow(record.audit_row())


def write_json(payload: Mapping[str, object], path: Path | str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def split_movielens_1m(input_path: Path | str, output_dir: Path | str) -> dict[str, object]:
    records = load_timestamped_ratings(input_path)
    train, test, stats = split_leave_one_out_by_timestamp(records)
    out_root = Path(output_dir)
    write_train_test_csv(train, out_root / "train_ratings.csv")
    write_train_test_csv(test, out_root / "test_ratings.csv")
    write_audit_csv(test, out_root / "test_ratings_with_timestamp.csv")
    write_json(stats, out_root / "split_stats.json")
    return stats


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Split MovieLens 1M using exact timestamps.")
    parser.add_argument("--input", required=True, help="ratings_with_timestamp.csv path.")
    parser.add_argument("--output-dir", required=True, help="Output split directory.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        stats = split_movielens_1m(args.input, args.output_dir)
    except (MovieLensSplitError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(stats, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
