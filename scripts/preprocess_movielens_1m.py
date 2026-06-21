"""Validate and preprocess the official MovieLens 1M dataset."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
import sys
from typing import Iterable, Mapping, Sequence


RATINGS_FILE = "ratings.dat"
MOVIES_FILE = "movies.dat"
USERS_FILE = "users.dat"
README_FILE = "README"
RATINGS_HEADER = ["userId", "movieId", "rating", "timestamp", "dateTimeUtc", "date"]
MOVIE_METADATA_HEADER = ["movieId", "title", "year", "genres"]
EXPECTED_OFFICIAL_RATINGS = 1_000_209
EXPECTED_OFFICIAL_USERS = 6_040
DATASET_NAME = "MovieLens 1M"
DATASET_ROLE = "primary-experimental"
DATASET_TYPE = "real-stable-benchmark"


class MovieLensPreprocessError(Exception):
    """Fatal MovieLens preprocessing error."""


@dataclass(frozen=True, order=True)
class MovieLensRating:
    user_id: int
    movie_id: int
    rating: int
    timestamp: int

    @property
    def datetime_utc(self) -> str:
        return timestamp_to_utc_text(self.timestamp)

    @property
    def date(self) -> str:
        return self.datetime_utc[:10]

    def csv_row(self) -> list[object]:
        return [self.user_id, self.movie_id, self.rating, self.timestamp, self.datetime_utc, self.date]


@dataclass(frozen=True)
class MovieLensMovie:
    movie_id: int
    raw_title: str
    title: str
    year: int | None
    genres: str


@dataclass(frozen=True)
class MovieLensUser:
    user_id: int
    gender: str
    age: int
    occupation: int
    zip_code: str


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def timestamp_to_utc_text(timestamp: int) -> str:
    try:
        parsed = dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise MovieLensPreprocessError(f"timestamp must convert to a valid UTC datetime: {timestamp}") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_positive_int(text: str, field_name: str, context: str) -> int:
    if not text.isdigit():
        raise MovieLensPreprocessError(f"{context}: {field_name} must be a positive integer.")
    value = int(text)
    if value <= 0:
        raise MovieLensPreprocessError(f"{context}: {field_name} must be a positive integer.")
    return value


def parse_non_negative_int(text: str, field_name: str, context: str) -> int:
    """Parse an integer that may be zero (e.g. MovieLens 1M occupation code 0 = other)."""
    stripped = text.strip()
    if not stripped.isdigit():
        raise MovieLensPreprocessError(f"{context}: {field_name} must be a non-negative integer.")
    return int(stripped)


def parse_rating_row(line: str, line_number: int) -> MovieLensRating:
    fields = line.rstrip("\n\r").split("::")
    if len(fields) != 4:
        raise MovieLensPreprocessError(f"ratings.dat:{line_number}: expected UserID::MovieID::Rating::Timestamp.")
    user_id = parse_positive_int(fields[0], "UserID", f"ratings.dat:{line_number}")
    movie_id = parse_positive_int(fields[1], "MovieID", f"ratings.dat:{line_number}")
    rating = parse_positive_int(fields[2], "Rating", f"ratings.dat:{line_number}")
    if rating < 1 or rating > 5:
        raise MovieLensPreprocessError(f"ratings.dat:{line_number}: Rating must be from 1 through 5.")
    timestamp = parse_positive_int(fields[3], "Timestamp", f"ratings.dat:{line_number}")
    timestamp_to_utc_text(timestamp)
    return MovieLensRating(user_id, movie_id, rating, timestamp)


YEAR_SUFFIX = re.compile(r"^(?P<title>.*)\s+\((?P<year>\d{4})\)$")


def parse_movie_row(line: str, line_number: int) -> MovieLensMovie:
    fields = line.rstrip("\n\r").split("::", 2)
    if len(fields) != 3:
        raise MovieLensPreprocessError(f"movies.dat:{line_number}: expected MovieID::Title::Genres.")
    movie_id = parse_positive_int(fields[0], "MovieID", f"movies.dat:{line_number}")
    raw_title = fields[1].strip()
    if not raw_title:
        raise MovieLensPreprocessError(f"movies.dat:{line_number}: Title must not be blank.")
    genres = fields[2].strip()
    match = YEAR_SUFFIX.match(raw_title)
    year = int(match.group("year")) if match else None
    title = match.group("title").strip() if match else raw_title
    if not title:
        raise MovieLensPreprocessError(f"movies.dat:{line_number}: Display title must not be blank.")
    return MovieLensMovie(movie_id, raw_title, title, year, genres)


def parse_user_row(line: str, line_number: int) -> MovieLensUser:
    fields = line.rstrip("\n\r").split("::")
    if len(fields) != 5:
        raise MovieLensPreprocessError(f"users.dat:{line_number}: expected UserID::Gender::Age::Occupation::Zip-code.")
    user_id = parse_positive_int(fields[0], "UserID", f"users.dat:{line_number}")
    gender = fields[1].strip()
    if gender not in {"M", "F"}:
        raise MovieLensPreprocessError(f"users.dat:{line_number}: Gender must be M or F.")
    age = parse_positive_int(fields[2], "Age", f"users.dat:{line_number}")
    # Occupation code 0 = "other or not specified" in MovieLens 1M
    occupation = parse_non_negative_int(fields[3], "Occupation", f"users.dat:{line_number}")
    zip_code = fields[4].strip()
    if not zip_code:
        raise MovieLensPreprocessError(f"users.dat:{line_number}: Zip-code must not be blank.")
    return MovieLensUser(user_id, gender, age, occupation, zip_code)


def require_dataset_files(dataset_dir: Path | str) -> dict[str, Path]:
    root = Path(dataset_dir)
    if not root.exists():
        raise MovieLensPreprocessError(f"Dataset directory does not exist: {root}")
    if not root.is_dir():
        raise MovieLensPreprocessError(f"Dataset path is not a directory: {root}")
    files = {
        "ratings": root / RATINGS_FILE,
        "movies": root / MOVIES_FILE,
        "users": root / USERS_FILE,
        "readme": root / README_FILE,
    }
    for key in ("ratings", "movies", "users"):
        path = files[key]
        if not path.is_file():
            raise MovieLensPreprocessError(f"Missing required MovieLens 1M file: {path.name}")
    return files


def load_ratings(path: Path | str) -> tuple[list[MovieLensRating], dict[str, object]]:
    records: list[MovieLensRating] = []
    seen_by_user_movie: dict[tuple[int, int], MovieLensRating] = {}
    duplicates = 0
    input_lines = 0
    with Path(path).open("r", encoding="latin-1") as input_file:
        for line_number, raw_line in enumerate(input_file, start=1):
            input_lines += 1
            if raw_line.strip() == "":
                raise MovieLensPreprocessError(f"ratings.dat:{line_number}: blank lines are not allowed.")
            record = parse_rating_row(raw_line, line_number)
            key = (record.user_id, record.movie_id)
            previous = seen_by_user_movie.get(key)
            if previous is not None:
                if previous == record:
                    duplicates += 1
                    continue
                raise MovieLensPreprocessError(
                    f"ratings.dat:{line_number}: conflicting duplicate rating for userId={record.user_id}, "
                    f"movieId={record.movie_id}."
                )
            seen_by_user_movie[key] = record
            records.append(record)
    records.sort(key=lambda item: (item.user_id, item.timestamp, item.movie_id))
    return records, {"input_lines": input_lines, "exact_duplicates_ignored": duplicates}


def load_movies(path: Path | str) -> list[MovieLensMovie]:
    rows: dict[int, MovieLensMovie] = {}
    with Path(path).open("r", encoding="latin-1") as input_file:
        for line_number, raw_line in enumerate(input_file, start=1):
            if raw_line.strip() == "":
                raise MovieLensPreprocessError(f"movies.dat:{line_number}: blank lines are not allowed.")
            row = parse_movie_row(raw_line, line_number)
            if row.movie_id in rows:
                raise MovieLensPreprocessError(f"movies.dat:{line_number}: duplicate MovieID {row.movie_id}.")
            rows[row.movie_id] = row
    return [rows[movie_id] for movie_id in sorted(rows)]


def load_users(path: Path | str) -> list[MovieLensUser]:
    rows: dict[int, MovieLensUser] = {}
    with Path(path).open("r", encoding="latin-1") as input_file:
        for line_number, raw_line in enumerate(input_file, start=1):
            if raw_line.strip() == "":
                raise MovieLensPreprocessError(f"users.dat:{line_number}: blank lines are not allowed.")
            row = parse_user_row(raw_line, line_number)
            if row.user_id in rows:
                raise MovieLensPreprocessError(f"users.dat:{line_number}: duplicate UserID {row.user_id}.")
            rows[row.user_id] = row
    return [rows[user_id] for user_id in sorted(rows)]


def write_ratings_csv(records: Iterable[MovieLensRating], output_path: Path | str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file, lineterminator="\n")
        writer.writerow(RATINGS_HEADER)
        for record in records:
            writer.writerow(record.csv_row())


def write_movie_metadata(movies: Sequence[MovieLensMovie], output_path: Path | str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file, lineterminator="\n")
        writer.writerow(MOVIE_METADATA_HEADER)
        for movie in movies:
            writer.writerow([movie.movie_id, movie.title, "" if movie.year is None else movie.year, movie.genres])


def average(values: Sequence[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def distribution(values: Sequence[int]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[str(value)] = result.get(str(value), 0) + 1
    return {key: result[key] for key in sorted(result, key=int)}


def build_stats(
    records: Sequence[MovieLensRating],
    movies: Sequence[MovieLensMovie],
    users: Sequence[MovieLensUser],
    files: Mapping[str, Path],
    normalized_output: Path,
    duplicates: int,
) -> dict[str, object]:
    if not records:
        raise MovieLensPreprocessError("ratings.dat produced no accepted ratings.")
    users_in_ratings: dict[int, int] = {}
    movies_in_ratings: dict[int, int] = {}
    ratings = []
    timestamps = []
    for record in records:
        users_in_ratings[record.user_id] = users_in_ratings.get(record.user_id, 0) + 1
        movies_in_ratings[record.movie_id] = movies_in_ratings.get(record.movie_id, 0) + 1
        ratings.append(record.rating)
        timestamps.append(record.timestamp)
    user_counts = list(users_in_ratings.values())
    movie_counts = list(movies_in_ratings.values())
    metadata_ids = {movie.movie_id for movie in movies}
    rated_ids = set(movies_in_ratings)
    return {
        "dataset_name": DATASET_NAME,
        "dataset_role": DATASET_ROLE,
        "dataset_type": DATASET_TYPE,
        "source_has_timestamps": True,
        "rating_rows": len(records),
        "exact_duplicates_ignored": duplicates,
        "distinct_users": len(users_in_ratings),
        "distinct_rated_movies": len(movies_in_ratings),
        "metadata_movies": len(movies),
        "minimum_user_id": min(users_in_ratings),
        "maximum_user_id": max(users_in_ratings),
        "minimum_movie_id": min(movies_in_ratings),
        "maximum_movie_id": max(movies_in_ratings),
        "minimum_rating": min(ratings),
        "maximum_rating": max(ratings),
        "rating_distribution": distribution(ratings),
        "minimum_timestamp": min(timestamps),
        "maximum_timestamp": max(timestamps),
        "minimum_datetime_utc": timestamp_to_utc_text(min(timestamps)),
        "maximum_datetime_utc": timestamp_to_utc_text(max(timestamps)),
        "ratings_per_user_minimum": min(user_counts),
        "ratings_per_user_maximum": max(user_counts),
        "ratings_per_user_average": average(user_counts),
        "ratings_per_movie_minimum": min(movie_counts),
        "ratings_per_movie_maximum": max(movie_counts),
        "ratings_per_movie_average": average(movie_counts),
        "metadata_coverage": len(rated_ids & metadata_ids) / len(rated_ids) if rated_ids else None,
        "valid_user_rows": len(users),
        "minimum_declared_user_id": min(user.user_id for user in users) if users else None,
        "maximum_declared_user_id": max(user.user_id for user in users) if users else None,
        "ratings_file_sha256": sha256_file(files["ratings"]),
        "movies_file_sha256": sha256_file(files["movies"]),
        "users_file_sha256": sha256_file(files["users"]),
        "readme_sha256": sha256_file(files["readme"]) if files["readme"].is_file() else None,
        "normalized_output_sha256": sha256_file(normalized_output),
    }


def write_json(payload: object, path: Path | str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def validate_strict_official(stats: Mapping[str, object]) -> None:
    if stats.get("rating_rows") != EXPECTED_OFFICIAL_RATINGS:
        raise MovieLensPreprocessError(
            f"Strict official validation expected {EXPECTED_OFFICIAL_RATINGS} accepted ratings, "
            f"found {stats.get('rating_rows')}."
        )
    if stats.get("distinct_users") != EXPECTED_OFFICIAL_USERS:
        raise MovieLensPreprocessError(
            f"Strict official validation expected {EXPECTED_OFFICIAL_USERS} distinct users, "
            f"found {stats.get('distinct_users')}."
        )
    if stats.get("minimum_rating") != 1 or stats.get("maximum_rating") != 5:
        raise MovieLensPreprocessError("Strict official validation expected rating range 1 through 5.")
    if int(stats.get("ratings_per_user_minimum", 0)) < 20:
        raise MovieLensPreprocessError("Strict official validation expected at least 20 ratings per user.")


def preprocess_movielens_1m(
    dataset_dir: Path | str,
    output_dir: Path | str,
    strict_official_counts: bool = False,
    overwrite: bool = False,
    stats_only: bool = False,
) -> dict[str, object]:
    files = require_dataset_files(dataset_dir)
    out_root = Path(output_dir)
    ratings_output = out_root / "ratings_with_timestamp.csv"
    metadata_output = out_root / "movie_metadata.csv"
    stats_output = out_root / "dataset_stats.json"
    manifest_output = out_root / "preprocessing_manifest.json"
    if out_root.exists() and any(out_root.iterdir()) and not overwrite and not stats_only:
        raise MovieLensPreprocessError(f"Output directory already contains files; pass --overwrite to replace: {out_root}")
    out_root.mkdir(parents=True, exist_ok=True)

    records, rating_load_stats = load_ratings(files["ratings"])
    movies = load_movies(files["movies"])
    users = load_users(files["users"])
    if not stats_only:
        write_ratings_csv(records, ratings_output)
        write_movie_metadata(movies, metadata_output)
    else:
        if not ratings_output.exists():
            write_ratings_csv(records, ratings_output)
        if not metadata_output.exists():
            write_movie_metadata(movies, metadata_output)
    stats = build_stats(records, movies, users, files, ratings_output, int(rating_load_stats["exact_duplicates_ignored"]))
    if strict_official_counts:
        validate_strict_official(stats)
    write_json(stats, stats_output)
    source_files = [RATINGS_FILE, MOVIES_FILE, USERS_FILE]
    if files["readme"].is_file():
        source_files.append(README_FILE)
    manifest = {
        "dataset_name": DATASET_NAME,
        "dataset_role": DATASET_ROLE,
        "source_files": sorted(source_files),
        "outputs": {
            "ratings_with_timestamp_csv": "ratings_with_timestamp.csv",
            "movie_metadata_csv": "movie_metadata.csv",
            "dataset_stats_json": "dataset_stats.json",
        },
        "strict_official_counts": strict_official_counts,
        "stats_only": stats_only,
    }
    write_json(manifest, manifest_output)
    return stats


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preprocess the official MovieLens 1M dataset.")
    parser.add_argument("--dataset-dir", required=True, help="Directory containing ratings.dat, movies.dat, and users.dat.")
    parser.add_argument("--output-dir", required=True, help="Directory for normalized outputs.")
    parser.add_argument("--strict-official-counts", action="store_true", help="Require official MovieLens 1M row/user invariants.")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting an existing output directory.")
    parser.add_argument("--stats-only", action="store_true", help="Validate and write statistics without changing existing outputs when present.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        stats = preprocess_movielens_1m(
            args.dataset_dir,
            args.output_dir,
            strict_official_counts=args.strict_official_counts,
            overwrite=args.overwrite,
            stats_only=args.stats_only,
        )
    except (MovieLensPreprocessError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(stats, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
