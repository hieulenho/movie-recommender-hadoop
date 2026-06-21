"""Run the full GitHub reference dataset workflow for Milestone 12."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Iterable, Mapping, Sequence


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import evaluate_recommendations
from scripts import preprocess_netflix
from scripts import split_ratings_for_evaluation


DATASET_TYPE = "github-reference-complete"
SOURCE_REPOSITORY = "thviet79/Bigdata_Project_Recommender_System"
SOURCE_SUBSET_DESCRIPTION = "all 15 mv_*.txt files committed in Movie_DataSet"
SOURCE_FORMAT_GITHUB_3COL = "github-reference-3col"
SOURCE_FORMAT_NETFLIX_RAW = "netflix-raw"
SOURCE_FORMAT_AUTO = "auto"
SPLIT_METHOD_UNDATED = "deterministic-leave-one-out-by-item"
SPLIT_TIE_BREAKING_RULE_UNDATED = "Sort by movieId ascending; hold out the highest movieId."
SCHEMA_PLACEHOLDER_DATE = "1970-01-01"
NO_TEMPORAL_WARNING = (
    "Source files contain userId,movieId,rating only; no temporal evaluation is possible. "
    "The placeholder date is used only after deterministic non-temporal splitting for schema compatibility."
)
EXPECTED_MOVIE_IDS = tuple(range(1, 16))
EXPECTED_RATING_FILES = tuple(f"mv_{movie_id:07d}.txt" for movie_id in EXPECTED_MOVIE_IDS)
MOVIE_TITLES_FILE = "movie_titles.txt"
METHODS = ("cosine", "cooccurrence")
METHOD_COMPARISON_HEADER = [
    "method",
    "ratingsRows",
    "users",
    "movies",
    "trainRows",
    "testRows",
    "topL",
    "topK",
    "minCommonUsers",
    "predictionCoverage",
    "mae",
    "rmse",
    "precisionAtK",
    "recallAtK",
    "hitRateAtK",
    "ndcgAtK",
    "mrrAtK",
    "userHistorySeconds",
    "pairStatisticsSeconds",
    "similaritySeconds",
    "scoringSeconds",
    "topKSeconds",
    "evaluationSeconds",
    "totalPipelineSeconds",
    "status",
]


class FullReferenceDatasetError(Exception):
    """Fatal workflow error with a concise user-facing message."""


@dataclass(frozen=True, order=True)
class UndatedRatingRecord:
    user_id: int
    movie_id: int
    rating: int

    def csv_row_with_placeholder_date(self) -> list[object]:
        return [self.user_id, self.movie_id, self.rating, SCHEMA_PLACEHOLDER_DATE]


@dataclass(frozen=True)
class UndatedLoadResult:
    records: list[UndatedRatingRecord]
    input_lines: int
    nonblank_input_lines: int
    blank_lines: int
    exact_duplicates_ignored: int

    @property
    def accepted_ratings(self) -> int:
        return len(self.records)


@dataclass(frozen=True)
class UndatedSplitResult:
    train_records: list[UndatedRatingRecord]
    test_records: list[UndatedRatingRecord]
    stats: dict[str, object]


def expected_rating_file_names() -> list[str]:
    return list(EXPECTED_RATING_FILES)


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_source_format(dataset_dir: Path | str, requested_format: str = SOURCE_FORMAT_AUTO) -> str:
    if requested_format not in {SOURCE_FORMAT_AUTO, SOURCE_FORMAT_GITHUB_3COL, SOURCE_FORMAT_NETFLIX_RAW}:
        raise FullReferenceDatasetError(f"Unsupported source format: {requested_format}")
    if requested_format != SOURCE_FORMAT_AUTO:
        return requested_format

    first_file = Path(dataset_dir) / EXPECTED_RATING_FILES[0]
    first_line = ""
    try:
        with first_file.open("r", encoding="utf-8") as input_file:
            for raw_line in input_file:
                first_line = raw_line.strip()
                if first_line:
                    break
    except OSError as exc:
        raise FullReferenceDatasetError(f"Cannot inspect source format from {first_file}: {exc}") from exc
    if not first_line:
        raise FullReferenceDatasetError(f"Cannot inspect source format from empty file: {first_file.name}")
    if first_line.endswith(":"):
        return SOURCE_FORMAT_NETFLIX_RAW
    fields = [field.strip() for field in first_line.split(",")]
    if len(fields) == 3 and all(fields):
        return SOURCE_FORMAT_GITHUB_3COL
    raise FullReferenceDatasetError(f"Cannot safely detect source format from first line: {first_line}")


def validate_reference_dataset(dataset_dir: Path | str, source_format: str = SOURCE_FORMAT_AUTO) -> dict[str, object]:
    root = Path(dataset_dir)
    if not root.exists():
        raise FullReferenceDatasetError(f"Dataset directory does not exist: {root}")
    if not root.is_dir():
        raise FullReferenceDatasetError(f"Dataset path is not a directory: {root}")

    resolved_format = resolve_source_format(root, source_format)
    movie_titles = root / MOVIE_TITLES_FILE
    if not movie_titles.exists():
        raise FullReferenceDatasetError(f"Missing required metadata file: {MOVIE_TITLES_FILE}")
    if not movie_titles.is_file():
        raise FullReferenceDatasetError(f"Metadata path is not a regular file: {MOVIE_TITLES_FILE}")

    children = list(root.iterdir())
    rating_candidates = [path for path in children if path.name.startswith("mv_") and path.suffix == ".txt"]
    candidate_names = [path.name for path in rating_candidates]
    duplicates = sorted(name for name in set(candidate_names) if candidate_names.count(name) > 1)
    if duplicates:
        raise FullReferenceDatasetError(f"Duplicate rating file names found: {', '.join(duplicates)}")

    expected = set(EXPECTED_RATING_FILES)
    discovered = set(candidate_names)
    missing = sorted(expected - discovered)
    extra = sorted(discovered - expected)
    if missing:
        raise FullReferenceDatasetError(f"Missing expected rating files: {', '.join(missing)}")
    if extra:
        raise FullReferenceDatasetError(f"Unexpected rating files found: {', '.join(extra)}")

    source_hashes: dict[str, str] = {MOVIE_TITLES_FILE: sha256_file(movie_titles)}
    file_stats: dict[str, dict[str, object]] = {}
    total_input_lines = 0
    ordered_paths: list[Path] = []
    for movie_id, file_name in zip(EXPECTED_MOVIE_IDS, EXPECTED_RATING_FILES):
        path = root / file_name
        if not path.is_file():
            raise FullReferenceDatasetError(f"Rating path is not a regular file: {file_name}")
        if path.stat().st_size == 0:
            raise FullReferenceDatasetError(f"Rating file is empty: {file_name}")
        if resolved_format == SOURCE_FORMAT_GITHUB_3COL:
            stats = validate_github_3col_rating_file(path, movie_id)
        else:
            stats = validate_netflix_raw_rating_file(path, movie_id)
        total_input_lines += int(stats["input_lines"])
        file_stats[file_name] = stats
        source_hashes[file_name] = sha256_file(path)
        ordered_paths.append(path)

    return {
        "dataset_dir": root,
        "movie_titles_path": movie_titles,
        "rating_files": ordered_paths,
        "source_format": resolved_format,
        "source_has_dates": resolved_format == SOURCE_FORMAT_NETFLIX_RAW,
        "expected_rating_file_count": len(EXPECTED_RATING_FILES),
        "discovered_rating_file_count": len(rating_candidates),
        "input_lines": total_input_lines,
        "source_file_sha256": source_hashes,
        "rating_file_stats": file_stats,
    }


def parse_github_3col_rating_row(raw_line: str, expected_movie_id: int, path_name: str, line_number: int) -> UndatedRatingRecord:
    line = raw_line.strip()
    fields = [field.strip() for field in line.split(",")]
    if len(fields) != 3:
        raise FullReferenceDatasetError(f"{path_name}:{line_number}: expected exactly userId,movieId,rating.")
    user_text, movie_text, rating_text = fields
    if not user_text.isdigit() or int(user_text) <= 0:
        raise FullReferenceDatasetError(f"{path_name}:{line_number}: userId must be a positive integer.")
    if not movie_text.isdigit() or int(movie_text) <= 0:
        raise FullReferenceDatasetError(f"{path_name}:{line_number}: movieId must be a positive integer.")
    movie_id = int(movie_text)
    if movie_id != expected_movie_id:
        raise FullReferenceDatasetError(
            f"{path_name}:{line_number}: movie ID {movie_id} does not match expected {expected_movie_id}."
        )
    if not rating_text.isdigit() or int(rating_text) < 1 or int(rating_text) > 5:
        raise FullReferenceDatasetError(f"{path_name}:{line_number}: rating must be an integer from 1 through 5.")
    return UndatedRatingRecord(int(user_text), movie_id, int(rating_text))


def validate_github_3col_rating_file(path: Path, expected_movie_id: int) -> dict[str, object]:
    load_result = load_github_3col_records([path], [expected_movie_id])
    if load_result.nonblank_input_lines == 0:
        raise FullReferenceDatasetError(f"Rating file has no meaningful lines: {path.name}")
    return {
        "input_lines": load_result.input_lines,
        "rating_rows": load_result.nonblank_input_lines,
        "blank_lines": load_result.blank_lines,
        "exact_duplicates_ignored": load_result.exact_duplicates_ignored,
        "first_meaningful_line": first_meaningful_line(path),
    }


def validate_netflix_raw_rating_file(path: Path, expected_movie_id: int) -> dict[str, object]:
    first_line = ""
    rating_rows = 0
    input_lines = 0
    current_movie_id: int | None = None
    try:
        with path.open("r", encoding="utf-8") as input_file:
            for line_number, raw_line in enumerate(input_file, start=1):
                input_lines += 1
                line = raw_line.strip()
                if not line:
                    continue
                if not first_line:
                    first_line = line
                    try:
                        current_movie_id = preprocess_netflix.parse_movie_header(line)
                    except ValueError as exc:
                        raise FullReferenceDatasetError(
                            f"{path.name}:{line_number}: first meaningful line must be a positive movie ID header."
                        ) from exc
                    if current_movie_id != expected_movie_id:
                        raise FullReferenceDatasetError(
                            f"{path.name}:{line_number}: movie ID {current_movie_id} does not match expected {expected_movie_id}."
                        )
                    continue

                parsed_header = preprocess_netflix.parse_movie_header(line)
                if parsed_header is not None:
                    if parsed_header != expected_movie_id:
                        raise FullReferenceDatasetError(
                            f"{path.name}:{line_number}: movie ID {parsed_header} does not match expected {expected_movie_id}."
                        )
                    current_movie_id = parsed_header
                    continue
                try:
                    preprocess_netflix.parse_rating_row(line, current_movie_id)
                except ValueError as exc:
                    raise FullReferenceDatasetError(f"{path.name}:{line_number}: malformed rating row ({exc}).") from exc
                rating_rows += 1
    except OSError as exc:
        raise FullReferenceDatasetError(f"Cannot read rating file {path.name}: {exc}") from exc

    if not first_line:
        raise FullReferenceDatasetError(f"Rating file has no meaningful lines: {path.name}")
    if rating_rows == 0:
        raise FullReferenceDatasetError(f"Rating file has no rating rows: {path.name}")
    return {
        "input_lines": input_lines,
        "rating_rows": rating_rows,
        "first_meaningful_line": first_line,
    }


def first_meaningful_line(path: Path) -> str:
    with path.open("r", encoding="utf-8") as input_file:
        for raw_line in input_file:
            line = raw_line.strip()
            if line:
                return line
    return ""


def load_github_3col_records(rating_files: Sequence[Path], expected_movie_ids: Sequence[int] | None = None) -> UndatedLoadResult:
    if expected_movie_ids is None:
        expected_movie_ids = tuple(int(path.stem.removeprefix("mv_")) for path in rating_files)
    records: list[UndatedRatingRecord] = []
    seen: dict[tuple[int, int], int] = {}
    input_lines = 0
    nonblank = 0
    blank = 0
    duplicates = 0
    for path, expected_movie_id in zip(rating_files, expected_movie_ids):
        with path.open("r", encoding="utf-8") as input_file:
            for line_number, raw_line in enumerate(input_file, start=1):
                input_lines += 1
                if not raw_line.strip():
                    blank += 1
                    continue
                nonblank += 1
                record = parse_github_3col_rating_row(raw_line, expected_movie_id, path.name, line_number)
                key = (record.user_id, record.movie_id)
                previous_rating = seen.get(key)
                if previous_rating is not None:
                    if previous_rating == record.rating:
                        duplicates += 1
                        continue
                    raise FullReferenceDatasetError(
                        f"{path.name}:{line_number}: conflicting duplicate rating for userId={record.user_id}, "
                        f"movieId={record.movie_id}."
                    )
                seen[key] = record.rating
                records.append(record)
    if not records:
        raise FullReferenceDatasetError("No github-reference-3col rating rows were loaded.")
    return UndatedLoadResult(
        records=records,
        input_lines=input_lines,
        nonblank_input_lines=nonblank,
        blank_lines=blank,
        exact_duplicates_ignored=duplicates,
    )


def split_undated_leave_one_out_by_item(load_result: UndatedLoadResult) -> UndatedSplitResult:
    by_user: dict[int, list[UndatedRatingRecord]] = {}
    for record in load_result.records:
        by_user.setdefault(record.user_id, []).append(record)

    train: list[UndatedRatingRecord] = []
    test: list[UndatedRatingRecord] = []
    for user_id in sorted(by_user):
        ratings = sorted(by_user[user_id], key=lambda item: item.movie_id)
        if len(ratings) >= 2:
            train.extend(ratings[:-1])
            test.append(ratings[-1])
        else:
            train.extend(ratings)

    train = sorted(train, key=lambda item: (item.user_id, item.movie_id))
    test = sorted(test, key=lambda item: (item.user_id, item.movie_id))
    item_ids = {record.movie_id for record in load_result.records}
    stats = {
        "input_rows": load_result.input_lines,
        "accepted_ratings": load_result.accepted_ratings,
        "exact_duplicate_rows_ignored": load_result.exact_duplicates_ignored,
        "users": len(by_user),
        "items": len(item_ids),
        "users_with_test_rating": len(test),
        "users_without_test_rating": len(by_user) - len(test),
        "train_rows": len(train),
        "test_rows": len(test),
        "split_method": SPLIT_METHOD_UNDATED,
        "holdout_per_user": 1,
        "tie_breaking_rule": SPLIT_TIE_BREAKING_RULE_UNDATED,
        "source_has_dates": False,
        "schema_placeholder_date": SCHEMA_PLACEHOLDER_DATE,
        "date_policy": "Placeholder date added after non-temporal split for Hadoop schema compatibility.",
        "warning": NO_TEMPORAL_WARNING,
    }
    if stats["train_rows"] + stats["test_rows"] != stats["accepted_ratings"]:
        raise FullReferenceDatasetError("Internal split error: train_rows + test_rows != accepted_ratings.")
    return UndatedSplitResult(train_records=train, test_records=test, stats=stats)


def write_undated_records_with_placeholder(records: Iterable[UndatedRatingRecord], output_path: Path | str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file, lineterminator="\n")
        writer.writerow(preprocess_netflix.CSV_HEADER)
        for record in records:
            writer.writerow(record.csv_row_with_placeholder_date())


def normalize_records(
    rating_files: Sequence[Path],
    output_path: Path,
    stats_output_path: Path,
    validation: Mapping[str, object],
) -> dict[str, object]:
    if validation.get("source_format") == SOURCE_FORMAT_GITHUB_3COL:
        load_result = load_github_3col_records(rating_files, EXPECTED_MOVIE_IDS)
        records = sorted(load_result.records, key=lambda item: (item.user_id, item.movie_id))
        write_undated_records_with_placeholder(records, output_path)
        stats = build_undated_dataset_stats(records, load_result, validation, output_path)
    else:
        records, base_stats = preprocess_netflix.preprocess_files(rating_files)
        if int(base_stats.get("invalid_rating_rows", 0)) != 0:
            raise FullReferenceDatasetError("Reference dataset validation found malformed rows during preprocessing.")
        records = sorted(records, key=lambda item: (item[0], item[3], item[1]))
        preprocess_netflix.write_normalized_csv(records, output_path)
        stats = build_dated_dataset_stats(records, base_stats, validation, output_path)
    write_json(stats, stats_output_path)
    return stats


def build_undated_dataset_stats(
    records: Sequence[UndatedRatingRecord],
    load_result: UndatedLoadResult,
    validation: Mapping[str, object],
    normalized_csv: Path,
) -> dict[str, object]:
    users: dict[int, int] = {}
    movies: dict[int, int] = {}
    ratings: list[int] = []
    for record in records:
        users[record.user_id] = users.get(record.user_id, 0) + 1
        movies[record.movie_id] = movies.get(record.movie_id, 0) + 1
        ratings.append(record.rating)
    user_counts = list(users.values())
    return {
        "dataset_type": DATASET_TYPE,
        "source_format": SOURCE_FORMAT_GITHUB_3COL,
        "source_has_dates": False,
        "schema_placeholder_date": SCHEMA_PLACEHOLDER_DATE,
        "warning": NO_TEMPORAL_WARNING,
        "source_repository": SOURCE_REPOSITORY,
        "source_subset_description": SOURCE_SUBSET_DESCRIPTION,
        "expected_rating_file_count": validation["expected_rating_file_count"],
        "discovered_rating_file_count": validation["discovered_rating_file_count"],
        "processed_rating_file_count": len(EXPECTED_RATING_FILES),
        "input_lines": load_result.input_lines,
        "accepted_rating_rows": len(records),
        "exact_duplicates_ignored": load_result.exact_duplicates_ignored,
        "blank_lines_ignored": load_result.blank_lines,
        "distinct_users": len(users),
        "distinct_movies": len(movies),
        "movie_ids": sorted(movies),
        "minimum_date": None,
        "maximum_date": None,
        "source_date_status": "unavailable",
        "minimum_rating": min(ratings),
        "maximum_rating": max(ratings),
        "ratings_per_movie": {str(movie_id): movies[movie_id] for movie_id in sorted(movies)},
        "ratings_per_user_minimum": min(user_counts),
        "ratings_per_user_maximum": max(user_counts),
        "ratings_per_user_average": sum(user_counts) / len(user_counts),
        "normalized_csv_sha256": sha256_file(normalized_csv),
        "source_file_sha256": validation["source_file_sha256"],
    }


def build_dated_dataset_stats(
    records: Sequence[preprocess_netflix.NormalizedRecord],
    base_stats: Mapping[str, object],
    validation: Mapping[str, object],
    normalized_csv: Path,
) -> dict[str, object]:
    users: dict[int, int] = {}
    movies: dict[int, int] = {}
    dates: list[str] = []
    ratings: list[int] = []
    for user_id, movie_id, rating, date in records:
        users[user_id] = users.get(user_id, 0) + 1
        movies[movie_id] = movies.get(movie_id, 0) + 1
        dates.append(date)
        ratings.append(rating)
    user_counts = list(users.values())
    return {
        "dataset_type": DATASET_TYPE,
        "source_format": SOURCE_FORMAT_NETFLIX_RAW,
        "source_has_dates": True,
        "source_repository": SOURCE_REPOSITORY,
        "source_subset_description": SOURCE_SUBSET_DESCRIPTION,
        "expected_rating_file_count": validation["expected_rating_file_count"],
        "discovered_rating_file_count": validation["discovered_rating_file_count"],
        "processed_rating_file_count": base_stats["files_processed"],
        "input_lines": validation["input_lines"],
        "accepted_rating_rows": len(records),
        "exact_duplicates_ignored": base_stats["duplicate_rows_removed"],
        "distinct_users": len(users),
        "distinct_movies": len(movies),
        "movie_ids": sorted(movies),
        "minimum_date": min(dates),
        "maximum_date": max(dates),
        "minimum_rating": min(ratings),
        "maximum_rating": max(ratings),
        "ratings_per_movie": {str(movie_id): movies[movie_id] for movie_id in sorted(movies)},
        "ratings_per_user_minimum": min(user_counts),
        "ratings_per_user_maximum": max(user_counts),
        "ratings_per_user_average": sum(user_counts) / len(user_counts),
        "normalized_csv_sha256": sha256_file(normalized_csv),
        "source_file_sha256": validation["source_file_sha256"],
    }


def parse_movie_title_line(raw_line: str, line_number: int) -> tuple[int, str, str]:
    line = raw_line.rstrip("\n")
    if line.endswith("\r"):
        line = line[:-1]
    if not line.strip():
        raise FullReferenceDatasetError(f"Line {line_number}: movie title row must not be blank.")
    try:
        row = next(csv.reader([line]))
    except csv.Error as exc:
        raise FullReferenceDatasetError(f"Line {line_number}: invalid CSV metadata row.") from exc
    if len(row) == 2:
        movie_id_text, title = row
        year = ""
    elif len(row) >= 3:
        movie_id_text = row[0]
        year = row[1].strip()
        title = ",".join(row[2:]).strip()
    else:
        raise FullReferenceDatasetError(f"Line {line_number}: expected movieId,title or movieId,year,title.")

    movie_id_text = movie_id_text.strip()
    if not movie_id_text.isdigit() or int(movie_id_text) <= 0:
        raise FullReferenceDatasetError(f"Line {line_number}: movieId must be a positive integer.")
    if year and (not year.isdigit() or len(year) != 4):
        raise FullReferenceDatasetError(f"Line {line_number}: year must be blank or a four-digit year.")
    if not title:
        raise FullReferenceDatasetError(f"Line {line_number}: title must not be empty.")
    return int(movie_id_text), title, year


def convert_movie_titles(input_path: Path | str, output_path: Path | str) -> dict[str, object]:
    source = Path(input_path)
    if not source.exists():
        raise FullReferenceDatasetError(f"Movie titles file does not exist: {source}")
    if not source.is_file():
        raise FullReferenceDatasetError(f"Movie titles path is not a file: {source}")

    rows: dict[int, tuple[str, str]] = {}
    with source.open("r", encoding="utf-8") as input_file:
        for line_number, raw_line in enumerate(input_file, start=1):
            movie_id, title, year = parse_movie_title_line(raw_line, line_number)
            if movie_id in rows:
                raise FullReferenceDatasetError(f"Line {line_number}: duplicate movieId in metadata: {movie_id}")
            rows[movie_id] = (title, year)

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file, lineterminator="\n")
        writer.writerow(["movieId", "title", "year"])
        for movie_id in sorted(rows):
            title, year = rows[movie_id]
            writer.writerow([movie_id, title, year])
    return {"metadata_rows": len(rows), "metadata_sha256": sha256_file(destination)}


def build_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "output_dir": output_dir,
        "marker": output_dir / ".full-reference-dataset-owned",
        "normalized_dir": output_dir / "normalized",
        "normalized_csv": output_dir / "normalized" / "ratings.csv",
        "dataset_stats": output_dir / "normalized" / "dataset_stats.json",
        "metadata_dir": output_dir / "metadata",
        "metadata_csv": output_dir / "metadata" / "movie_metadata.csv",
        "split_dir": output_dir / "split",
        "train_csv": output_dir / "split" / "train_ratings.csv",
        "test_csv": output_dir / "split" / "test_ratings.csv",
        "split_stats": output_dir / "split" / "split_stats.json",
        "logs_dir": output_dir / "logs",
        "report_artifacts_dir": output_dir / "report-artifacts",
        "method_comparison": output_dir / "method_comparison.csv",
        "manifest": output_dir / "full_dataset_manifest.json",
    }


def method_paths(output_dir: Path, method: str) -> dict[str, Path]:
    root = output_dir / method
    return {
        "method_dir": root,
        "user_history_dir": root / "user-history",
        "pair_statistics_dir": root / "pair-statistics",
        "similarity_dir": root / "similarity",
        "raw_predictions_dir": root / "raw-predictions",
        "recommendations_dir": root / "recommendations",
        "raw_predictions_file": root / "raw_predictions.txt",
        "recommendations_file": root / "recommendations.txt",
        "metrics_json": root / "metrics.json",
        "metrics_csv": root / "metrics.csv",
        "per_user_metrics": root / "per_user_metrics.csv",
    }


def prepare_output_dir(output_dir: Path, repo_root: Path) -> dict[str, Path]:
    resolved = output_dir.resolve()
    repo = repo_root.resolve()
    try:
        resolved.relative_to((repo / "results").resolve())
    except ValueError as exc:
        raise FullReferenceDatasetError("Output directory must be under results/.") from exc
    if resolved == (repo / "results").resolve():
        raise FullReferenceDatasetError("Output directory must be a results/ subdirectory.")
    paths = build_paths(resolved)
    if resolved.exists():
        if not resolved.is_dir():
            raise FullReferenceDatasetError(f"Output path exists and is not a directory: {output_dir}")
        if any(resolved.iterdir()) and not paths["marker"].exists():
            raise FullReferenceDatasetError(f"Refusing to overwrite unowned output directory: {output_dir}")
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)
    paths["marker"].write_text("owned by scripts/full_reference_dataset.py\n", encoding="utf-8")
    return paths


def build_stage_commands(
    method: str,
    java_classpath: str,
    paths: Mapping[str, Path],
    method_specific: Mapping[str, Path],
    parameters: Mapping[str, int],
) -> list[tuple[str, list[str]]]:
    reducers = str(parameters["reducers"])
    return [
        (
            "user_history",
            ["java", "-cp", java_classpath, "com.movierecommender.history.UserHistoryJob", "--local", "--reducers", reducers, str(paths["train_csv"]), str(method_specific["user_history_dir"])],
        ),
        (
            "pair_statistics",
            ["java", "-cp", java_classpath, "com.movierecommender.pairs.ItemPairStatisticsJob", "--local", "--reducers", reducers, str(method_specific["user_history_dir"]), str(method_specific["pair_statistics_dir"])],
        ),
        (
            "similarity",
            ["java", "-cp", java_classpath, "com.movierecommender.similarity.ItemSimilarityPipeline", "--local", "--method", method, "--min-common-users", str(parameters["min_common_users"]), "--top-l", str(parameters["top_l"]), "--reducers", reducers, str(method_specific["pair_statistics_dir"]), str(method_specific["similarity_dir"])],
        ),
        (
            "scoring",
            ["java", "-cp", java_classpath, "com.movierecommender.scoring.RecommendationScoringPipeline", "--local", "--reducers", reducers, str(method_specific["user_history_dir"]), str(method_specific["similarity_dir"]), str(method_specific["raw_predictions_dir"])],
        ),
        (
            "top_k",
            ["java", "-cp", java_classpath, "com.movierecommender.recommendation.TopKRecommendationJob", "--local", "--reducers", reducers, "--top-k", str(parameters["top_k"]), str(method_specific["user_history_dir"]), str(method_specific["raw_predictions_dir"]), str(method_specific["recommendations_dir"])],
        ),
    ]


def command_uses_test_input(command: Sequence[str], test_path: Path | str) -> bool:
    return any(argument == str(test_path) for argument in command)


def run_command(stage: str, command: Sequence[str], logs_dir: Path, repo_root: Path) -> float:
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / f"{stage}.stdout.log"
    stderr_path = logs_dir / f"{stage}.stderr.log"
    start = time.perf_counter()
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        result = subprocess.run(command, cwd=repo_root, stdout=stdout, stderr=stderr, text=True, check=False)
    elapsed = time.perf_counter() - start
    if result.returncode != 0:
        raise FullReferenceDatasetError(
            f"Stage {stage} failed with exit code {result.returncode}. See {stdout_path.as_posix()} and {stderr_path.as_posix()}."
        )
    return elapsed


def iter_part_files(path: Path | str) -> list[Path]:
    root = Path(path)
    if not root.exists():
        return []
    return sorted(
        [
            child
            for child in root.iterdir()
            if child.is_file()
            and child.name.startswith("part-")
            and child.name != "_SUCCESS"
            and not child.name.startswith(".")
            and not child.name.endswith(".crc")
        ],
        key=lambda item: item.name,
    )


def combine_part_files(source_dir: Path | str, destination: Path | str) -> None:
    parts = iter_part_files(source_dir)
    if not parts:
        raise FullReferenceDatasetError(f"No Hadoop part files found under {source_dir}")
    output_path = Path(destination)
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        for part_file in parts:
            with part_file.open("r", encoding="utf-8", errors="replace") as input_file:
                shutil.copyfileobj(input_file, output_file)


def build_java_classpath(repo_root: Path, output_dir: Path) -> str:
    run_command("maven_package", ["mvn", "-q", "-DskipTests", "package"], output_dir / "logs", repo_root)
    classpath_file = output_dir / "logs" / "runtime-classpath.txt"
    run_command(
        "maven_classpath",
        ["mvn", "-q", "dependency:build-classpath", "-Dmdep.includeScope=runtime", f"-Dmdep.outputFile={classpath_file}"],
        output_dir / "logs",
        repo_root,
    )
    runtime_classpath = classpath_file.read_text(encoding="utf-8").strip()
    return f"{repo_root / 'target' / 'classes'}:{runtime_classpath}"


def run_method(
    method: str,
    java_classpath: str,
    paths: Mapping[str, Path],
    parameters: Mapping[str, int],
    repo_root: Path,
) -> dict[str, object]:
    specific = method_paths(paths["output_dir"], method)
    specific["method_dir"].mkdir(parents=True, exist_ok=True)
    stage_seconds: dict[str, float] = {}
    started = time.perf_counter()
    for stage, command in build_stage_commands(method, java_classpath, paths, specific, parameters):
        if command_uses_test_input(command, paths["test_csv"]):
            raise FullReferenceDatasetError(f"Internal error: {stage} command uses held-out test data.")
        stage_seconds[stage] = run_command(f"{method}_{stage}", command, paths["logs_dir"], repo_root)

    combine_part_files(specific["raw_predictions_dir"], specific["raw_predictions_file"])
    combine_part_files(specific["recommendations_dir"], specific["recommendations_file"])
    eval_start = time.perf_counter()
    evaluate_recommendations.run_evaluation(
        paths["train_csv"],
        paths["test_csv"],
        specific["raw_predictions_file"],
        specific["recommendations_file"],
        specific["metrics_json"],
        specific["metrics_csv"],
        specific["per_user_metrics"],
        parameters["top_k"],
        parameters["relevance_threshold"],
    )
    stage_seconds["evaluation"] = time.perf_counter() - eval_start
    metrics = read_json(specific["metrics_json"])
    return {
        "method": method,
        "status": "completed",
        "stage_seconds": stage_seconds,
        "total_pipeline_seconds": time.perf_counter() - started,
        "metrics": metrics,
        "paths": specific,
    }


def build_method_comparison_rows(
    method_results: Sequence[Mapping[str, object]],
    dataset_stats: Mapping[str, object],
    split_stats: Mapping[str, object],
    parameters: Mapping[str, int],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for result in method_results:
        metrics = result.get("metrics", {})
        if not isinstance(metrics, dict):
            metrics = {}
        stage_seconds = result.get("stage_seconds", {})
        if not isinstance(stage_seconds, dict):
            stage_seconds = {}
        row = {
            "method": result.get("method", ""),
            "ratingsRows": dataset_stats.get("accepted_rating_rows", ""),
            "users": dataset_stats.get("distinct_users", ""),
            "movies": dataset_stats.get("distinct_movies", ""),
            "trainRows": split_stats.get("train_rows", ""),
            "testRows": split_stats.get("test_rows", ""),
            "topL": parameters["top_l"],
            "topK": parameters["top_k"],
            "minCommonUsers": parameters["min_common_users"],
            "predictionCoverage": format_metric(metrics.get("prediction_coverage")),
            "mae": format_metric(metrics.get("mae")),
            "rmse": format_metric(metrics.get("rmse")),
            "precisionAtK": format_metric(metrics.get("precision_at_k")),
            "recallAtK": format_metric(metrics.get("recall_at_k")),
            "hitRateAtK": format_metric(metrics.get("hit_rate_at_k")),
            "ndcgAtK": format_metric(metrics.get("ndcg_at_k")),
            "mrrAtK": format_metric(metrics.get("mrr_at_k")),
            "userHistorySeconds": format_seconds(stage_seconds.get("user_history")),
            "pairStatisticsSeconds": format_seconds(stage_seconds.get("pair_statistics")),
            "similaritySeconds": format_seconds(stage_seconds.get("similarity")),
            "scoringSeconds": format_seconds(stage_seconds.get("scoring")),
            "topKSeconds": format_seconds(stage_seconds.get("top_k")),
            "evaluationSeconds": format_seconds(stage_seconds.get("evaluation")),
            "totalPipelineSeconds": format_seconds(result.get("total_pipeline_seconds")),
            "status": result.get("status", ""),
        }
        rows.append(row)
    return rows


def write_method_comparison(rows: Sequence[Mapping[str, object]], output_path: Path | str) -> None:
    with Path(output_path).open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=METHOD_COMPARISON_HEADER, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in METHOD_COMPARISON_HEADER})


def format_metric(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            return ""
        return f"{float(value):.10f}"
    return str(value)


def format_seconds(value: object) -> str:
    if value is None:
        return ""
    return f"{float(value):.6f}"


def build_full_manifest(
    validation: Mapping[str, object],
    dataset_stats: Mapping[str, object],
    split_stats: Mapping[str, object],
    method_results: Sequence[Mapping[str, object]],
    metadata_result: Mapping[str, object],
    parameters: Mapping[str, int],
    repo_root: Path,
) -> dict[str, object]:
    method_map = {str(result["method"]): result for result in method_results}
    return {
        "dataset_label": "GitHub reference repository 15-movie subset",
        "dataset_type": DATASET_TYPE,
        "source_format": validation["source_format"],
        "source_has_dates": validation["source_has_dates"],
        "split_method": split_stats["split_method"],
        "split_tie_breaking_rule": split_stats["tie_breaking_rule"],
        "schema_placeholder_date": split_stats.get("schema_placeholder_date"),
        "warning": split_stats.get("warning"),
        "source_repository": SOURCE_REPOSITORY,
        "source_subset_description": SOURCE_SUBSET_DESCRIPTION,
        "input_file_names": list(EXPECTED_RATING_FILES),
        "source_hashes": validation["source_file_sha256"],
        "normalized_hash": dataset_stats["normalized_csv_sha256"],
        "total_ratings": dataset_stats["accepted_rating_rows"],
        "distinct_users": dataset_stats["distinct_users"],
        "distinct_movies": dataset_stats["distinct_movies"],
        "movie_ids": dataset_stats.get("movie_ids", []),
        "train_rows": split_stats["train_rows"],
        "test_rows": split_stats["test_rows"],
        "cosine_status": method_map.get("cosine", {}).get("status", "not_run"),
        "cooccurrence_status": method_map.get("cooccurrence", {}).get("status", "not_run"),
        "cosine_artifact_locations": artifact_locations(method_map.get("cosine", {}).get("paths", {}), repo_root),
        "cooccurrence_artifact_locations": artifact_locations(method_map.get("cooccurrence", {}).get("paths", {}), repo_root),
        "metadata": metadata_result,
        "parameters": dict(parameters),
        "train_test_overlap_count": max(int(result.get("metrics", {}).get("train_test_overlap_rows", 0)) for result in method_results),
        "watched_recommendation_violations": max(int(result.get("metrics", {}).get("watched_recommendations_found", 0)) for result in method_results),
        "completion_status": "completed" if all(result.get("status") == "completed" for result in method_results) else "failed",
    }


def artifact_locations(paths: object, repo_root: Path) -> dict[str, str]:
    if not isinstance(paths, Mapping):
        return {}
    keys = [
        "user_history_dir",
        "pair_statistics_dir",
        "similarity_dir",
        "raw_predictions_dir",
        "recommendations_dir",
        "metrics_json",
        "metrics_csv",
        "per_user_metrics",
    ]
    return {key: relative_to_repo(value, repo_root) for key in keys if isinstance((value := paths.get(key)), Path)}


def relative_to_repo(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def write_json(data: object, path: Path | str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def read_json(path: Path | str) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_workflow(args: argparse.Namespace) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    dataset_dir = Path(args.dataset_dir)
    if not dataset_dir.is_absolute():
        dataset_dir = repo_root / dataset_dir
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    parameters = {
        "top_l": args.top_l,
        "top_k": args.top_k,
        "min_common_users": args.min_common_users,
        "relevance_threshold": args.relevance_threshold,
        "reducers": args.reducers,
    }

    validation = validate_reference_dataset(dataset_dir, args.source_format)
    paths = prepare_output_dir(output_dir, repo_root)
    for directory_key in ("normalized_dir", "metadata_dir", "split_dir", "logs_dir", "report_artifacts_dir"):
        paths[directory_key].mkdir(parents=True, exist_ok=True)

    dataset_stats = normalize_records(validation["rating_files"], paths["normalized_csv"], paths["dataset_stats"], validation)
    metadata_result = convert_movie_titles(validation["movie_titles_path"], paths["metadata_csv"])
    if validation["source_format"] == SOURCE_FORMAT_GITHUB_3COL:
        load_result = load_github_3col_records(validation["rating_files"], EXPECTED_MOVIE_IDS)
        split_result = split_undated_leave_one_out_by_item(load_result)
        write_undated_records_with_placeholder(split_result.train_records, paths["train_csv"])
        write_undated_records_with_placeholder(split_result.test_records, paths["test_csv"])
        write_json(split_result.stats, paths["split_stats"])
        split_stats = split_result.stats
    else:
        split_stats = split_ratings_for_evaluation.run_split(paths["normalized_csv"], paths["train_csv"], paths["test_csv"], paths["split_stats"])

    java_classpath = build_java_classpath(repo_root, paths["output_dir"])
    method_results = [run_method(method, java_classpath, paths, parameters, repo_root) for method in METHODS]
    comparison_rows = build_method_comparison_rows(method_results, dataset_stats, split_stats, parameters)
    write_method_comparison(comparison_rows, paths["method_comparison"])

    from scripts import export_report_artifacts

    export_report_artifacts.export_report_artifacts(paths["output_dir"], paths["report_artifacts_dir"])
    manifest = build_full_manifest(validation, dataset_stats, split_stats, method_results, metadata_result, parameters, repo_root)
    write_json(manifest, paths["manifest"])
    print(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False))
    return 0 if manifest["completion_status"] == "completed" else 1


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the 15-movie GitHub reference dataset workflow.")
    parser.add_argument("--dataset-dir", default="data/raw/github-reference")
    parser.add_argument("--output-dir", default="results/full-reference-dataset")
    parser.add_argument("--source-format", choices=[SOURCE_FORMAT_AUTO, SOURCE_FORMAT_GITHUB_3COL, SOURCE_FORMAT_NETFLIX_RAW], default=SOURCE_FORMAT_AUTO)
    parser.add_argument("--top-l", type=int, default=10)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-common-users", type=int, default=1)
    parser.add_argument("--relevance-threshold", type=int, default=4)
    parser.add_argument("--reducers", type=int, default=1)
    return parser


def validate_args(args: argparse.Namespace) -> None:
    for name in ("top_l", "top_k", "min_common_users", "reducers"):
        if getattr(args, name) < 1:
            raise FullReferenceDatasetError(f"{name.replace('_', '-')} must be at least 1.")
    if args.relevance_threshold < 1 or args.relevance_threshold > 5:
        raise FullReferenceDatasetError("relevance-threshold must be from 1 through 5.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        validate_args(args)
        return run_workflow(args)
    except (
        FullReferenceDatasetError,
        preprocess_netflix.PreprocessError,
        split_ratings_for_evaluation.SplitRatingsError,
        evaluate_recommendations.EvaluationError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
