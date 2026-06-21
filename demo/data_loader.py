"""Pure artifact parsing for the Streamlit offline recommendation demo."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from demo.models import (
    BenchmarkRun,
    DemoDataBundle,
    DemoValidationError,
    EvaluationMetrics,
    MovieMetadata,
    Recommendation,
    UserProfile,
    WatchedMovie,
)


DEMO_ROOT = Path(__file__).resolve().parent
SAMPLE_DIR = DEMO_ROOT / "sample"
REQUIRED_BENCHMARK_COLUMNS = {
    "experimentId",
    "profile",
    "datasetType",
    "method",
    "ratingsRows",
    "trainRows",
    "testRows",
    "topL",
    "topK",
    "totalPipelineSeconds",
    "userHistorySeconds",
    "pairStatisticsSeconds",
    "similaritySeconds",
    "scoringSeconds",
    "topKSeconds",
    "evaluationSeconds",
    "itemPairRows",
    "similarityRows",
    "rawPredictionRows",
    "recommendationUsers",
    "recommendationItems",
    "predictionCoverage",
    "mae",
    "rmse",
    "precisionAtK",
    "recallAtK",
    "ndcgAtK",
    "mrrAtK",
    "status",
}
COUNT_METRIC_FIELDS = {
    "k",
    "relevance_threshold",
    "test_rows",
    "matched_test_predictions",
    "missing_test_predictions",
    "ranking_eligible_users",
    "ranking_hits",
    "users_with_recommendations",
    "watched_recommendations_found",
    "train_test_overlap_rows",
}
RANGE_METRIC_FIELDS = {
    "prediction_coverage",
    "recommendation_user_coverage",
    "precision_at_k",
    "recall_at_k",
    "hit_rate_at_k",
    "ndcg_at_k",
    "mrr_at_k",
}


def discover_part_files(path: Path | str) -> list[Path]:
    """Return a single text file or sorted Hadoop part-* files."""

    candidate = Path(path)
    if candidate.is_file():
        return [candidate]
    if not candidate.exists():
        raise DemoValidationError(f"Artifact path does not exist: {candidate}")
    if not candidate.is_dir():
        raise DemoValidationError(f"Artifact path is neither file nor directory: {candidate}")
    parts = sorted(
        child
        for child in candidate.iterdir()
        if child.is_file() and _is_readable_part_file(child)
    )
    if not parts:
        raise DemoValidationError(f"No readable part-* files found under: {candidate}")
    return parts


def _is_readable_part_file(path: Path) -> bool:
    name = path.name
    if name == "_SUCCESS" or name.startswith(".") or name.endswith(".crc") or name.endswith(".log"):
        return False
    return name.startswith("part-")


def path_signature(path: Path | str | None) -> tuple[tuple[str, int, float], ...]:
    """Build a cache signature from resolved path, size, and mtime."""

    if path is None or str(path).strip() == "":
        return (("<missing>", 0, 0.0),)
    candidate = Path(path)
    try:
        files = discover_part_files(candidate)
    except DemoValidationError:
        if not candidate.exists():
            return ((str(candidate), -1, -1.0),)
        raise
    signature = []
    for file_path in files:
        stat = file_path.stat()
        signature.append((str(file_path.resolve()), stat.st_size, stat.st_mtime))
    return tuple(signature)


def load_user_histories(path: Path | str) -> dict[int, tuple[WatchedMovie, ...]]:
    rows: dict[int, tuple[WatchedMovie, ...]] = {}
    for line_number, line in _iter_artifact_lines(path):
        user_id, value = _split_tab(line, line_number, "history")
        if value == "":
            raise DemoValidationError(f"Line {line_number}: history must not be empty.")
        watched = []
        movie_ids: set[int] = set()
        for entry in value.split(","):
            movie_text, rating_text = _split_entry(entry, line_number, "history")
            movie_id = _parse_positive_int(movie_text, f"Line {line_number}: movie ID")
            rating = _parse_positive_int(rating_text, f"Line {line_number}: rating")
            if rating > 5:
                raise DemoValidationError(f"Line {line_number}: rating must be from 1 through 5.")
            if movie_id in movie_ids:
                raise DemoValidationError(f"Line {line_number}: duplicate movie ID {movie_id}.")
            movie_ids.add(movie_id)
            watched.append(WatchedMovie(movie_id, rating))
        watched_tuple = tuple(sorted(watched, key=lambda item: item.movie_id))
        _store_duplicate_checked(rows, user_id, watched_tuple, "history")
    return rows


def load_recommendations(path: Path | str) -> dict[int, tuple[Recommendation, ...]]:
    rows: dict[int, tuple[Recommendation, ...]] = {}
    for line_number, line in _iter_artifact_lines(path):
        user_id, value = _split_tab(line, line_number, "recommendation")
        if value == "":
            raise DemoValidationError(f"Line {line_number}: recommendation list must not be empty.")
        recommendations = []
        movie_ids: set[int] = set()
        previous: Recommendation | None = None
        for rank, entry in enumerate(value.split(","), start=1):
            movie_text, score_text = _split_entry(entry, line_number, "recommendation")
            movie_id = _parse_positive_int(movie_text, f"Line {line_number}: movie ID")
            score = _parse_float(score_text, f"Line {line_number}: score")
            if score < 1.0 or score > 5.0:
                raise DemoValidationError(f"Line {line_number}: score must be from 1 through 5.")
            if movie_id in movie_ids:
                raise DemoValidationError(f"Line {line_number}: duplicate recommended movie ID {movie_id}.")
            movie_ids.add(movie_id)
            recommendation = Recommendation(rank, movie_id, score, score_text)
            if previous is not None:
                if recommendation.score > previous.score:
                    raise DemoValidationError(f"Line {line_number}: recommendations must be sorted by score descending.")
                if recommendation.score == previous.score and recommendation.movie_id < previous.movie_id:
                    raise DemoValidationError(f"Line {line_number}: tied recommendations must sort by movie ID ascending.")
            recommendations.append(recommendation)
            previous = recommendation
        _store_duplicate_checked(rows, user_id, tuple(recommendations), "recommendation")
    return rows


def load_movie_metadata(path: Path | str) -> dict[int, MovieMetadata]:
    metadata_path = Path(path)
    if not metadata_path.exists():
        raise DemoValidationError(f"Metadata path does not exist: {metadata_path}")
    with metadata_path.open("r", encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames != ["movieId", "title", "year"]:
            raise DemoValidationError("Movie metadata header must be: movieId,title,year")
        rows: dict[int, MovieMetadata] = {}
        for line_number, row in enumerate(reader, start=2):
            movie_id = _parse_positive_int(row.get("movieId", ""), f"Line {line_number}: movieId")
            if movie_id in rows:
                raise DemoValidationError(f"Line {line_number}: duplicate metadata movie ID {movie_id}.")
            title = (row.get("title") or "").strip()
            if not title:
                raise DemoValidationError(f"Line {line_number}: title must not be blank.")
            year_text = (row.get("year") or "").strip()
            year = None
            if year_text:
                if not year_text.isdigit() or len(year_text) != 4:
                    raise DemoValidationError(f"Line {line_number}: year must be a four-digit integer.")
                year = int(year_text)
            rows[movie_id] = MovieMetadata(movie_id, title, year, title.startswith("Demo Movie"))
        return rows


def fallback_movie_metadata(movie_id: int) -> MovieMetadata:
    return MovieMetadata(movie_id=movie_id, title=f"Movie {movie_id}", year=None)


def load_evaluation_metrics(path: Path | str) -> EvaluationMetrics:
    metrics_path = Path(path)
    try:
        data = json.loads(
            metrics_path.read_text(encoding="utf-8"),
            parse_constant=lambda value: (_raise_json_constant(value)),
        )
    except json.JSONDecodeError as exc:
        raise DemoValidationError(f"Evaluation metrics JSON is invalid: {exc}") from exc
    if not isinstance(data, dict):
        raise DemoValidationError("Evaluation metrics JSON root must be an object.")
    _reject_non_finite(data)
    for key in COUNT_METRIC_FIELDS:
        if key in data and data[key] is not None:
            value = data[key]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise DemoValidationError(f"{key} must be a non-negative integer.")
    for key in RANGE_METRIC_FIELDS:
        if key in data and data[key] is not None:
            value = data[key]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= float(value) <= 1.0:
                raise DemoValidationError(f"{key} must be between 0 and 1.")
    for key in ("mae", "rmse"):
        if key in data and data[key] is not None:
            value = data[key]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or float(value) < 0:
                raise DemoValidationError(f"{key} must be non-negative or null.")
    for required in ("watched_recommendations_found", "train_test_overlap_rows"):
        if required not in data:
            raise DemoValidationError(f"{required} must be present in evaluation metrics.")
    return EvaluationMetrics(data)


def load_benchmark_results(path: Path | str) -> tuple[BenchmarkRun, ...]:
    benchmark_path = Path(path)
    with benchmark_path.open("r", encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        fieldnames = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_BENCHMARK_COLUMNS - fieldnames)
        if missing:
            raise DemoValidationError(f"Benchmark CSV is missing columns: {', '.join(missing)}")
        runs = []
        for line_number, row in enumerate(reader, start=2):
            clean = {key: value or "" for key, value in row.items()}
            _validate_benchmark_numeric_fields(clean, line_number)
            ratings_rows = _parse_optional_int(clean.get("ratingsRows", ""), f"Line {line_number}: ratingsRows")
            runs.append(
                BenchmarkRun(
                    experiment_id=clean["experimentId"],
                    profile=clean["profile"],
                    dataset_type=clean["datasetType"],
                    method=clean["method"],
                    ratings_rows=ratings_rows,
                    status=clean["status"],
                    raw=clean,
                )
            )
    return tuple(sorted(runs, key=lambda item: (item.ratings_rows if item.ratings_rows is not None else -1, item.method, item.experiment_id)))


def build_demo_bundle(
    user_history_path: Path | str,
    recommendations_path: Path | str,
    evaluation_metrics_path: Path | str | None = None,
    benchmark_results_path: Path | str | None = None,
    movie_metadata_path: Path | str | None = None,
    manifest_path: Path | str | None = None,
    dataset_type: str = "local-artifacts",
) -> DemoDataBundle:
    histories = load_user_histories(user_history_path)
    recommendations = load_recommendations(recommendations_path)
    unknown_recommendation_users = sorted(set(recommendations) - set(histories))
    if unknown_recommendation_users:
        first = unknown_recommendation_users[0]
        raise DemoValidationError(f"Recommendations exist for unknown user {first}.")
    users = {
        user_id: UserProfile(user_id, watched, recommendations.get(user_id, tuple()))
        for user_id, watched in sorted(histories.items())
    }
    metadata: dict[int, MovieMetadata] = {}
    warnings: list[str] = []
    if movie_metadata_path and Path(movie_metadata_path).is_file():
        metadata = load_movie_metadata(movie_metadata_path)
    elif movie_metadata_path and Path(movie_metadata_path).exists():
        warnings.append(f"Optional movie metadata is not a regular CSV file: {movie_metadata_path}")
    elif movie_metadata_path:
        warnings.append(f"Optional movie metadata not found: {movie_metadata_path}")

    evaluation = None
    if evaluation_metrics_path and Path(evaluation_metrics_path).is_file():
        evaluation = load_evaluation_metrics(evaluation_metrics_path)
    elif evaluation_metrics_path and Path(evaluation_metrics_path).exists():
        warnings.append(f"Optional evaluation metrics is not a regular JSON file: {evaluation_metrics_path}")
    elif evaluation_metrics_path:
        warnings.append(f"Optional evaluation metrics not found: {evaluation_metrics_path}")

    benchmark_runs: tuple[BenchmarkRun, ...] = ()
    if benchmark_results_path and Path(benchmark_results_path).is_file():
        benchmark_runs = load_benchmark_results(benchmark_results_path)
    elif benchmark_results_path and Path(benchmark_results_path).exists():
        warnings.append(f"Optional benchmark results is not a regular CSV file: {benchmark_results_path}")
    elif benchmark_results_path:
        warnings.append(f"Optional benchmark results not found: {benchmark_results_path}")

    manifest: Mapping[str, object] | None = None
    if manifest_path and Path(manifest_path).exists():
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))

    bundle = DemoDataBundle(users, metadata, evaluation, benchmark_runs, manifest, dataset_type, tuple(warnings))
    return bundle


def build_sample_bundle(include_benchmark: bool = False) -> DemoDataBundle:
    benchmark_path = SAMPLE_DIR / "benchmark_results.csv" if include_benchmark else None
    return build_demo_bundle(
        SAMPLE_DIR / "user_history.txt",
        SAMPLE_DIR / "recommendations.txt",
        SAMPLE_DIR / "evaluation_metrics.json",
        benchmark_path,
        SAMPLE_DIR / "movie_metadata.csv",
        SAMPLE_DIR / "demo_manifest.json",
        dataset_type="demo-fixture",
    )


def _iter_artifact_lines(path: Path | str) -> Iterable[tuple[int, str]]:
    line_number = 0
    for file_path in discover_part_files(path):
        with file_path.open("r", encoding="utf-8", errors="replace") as input_file:
            for raw_line in input_file:
                line_number += 1
                line = raw_line.rstrip("\n\r")
                if line == "":
                    raise DemoValidationError(f"Line {line_number}: blank lines are not allowed.")
                yield line_number, line


def _split_tab(line: str, line_number: int, label: str) -> tuple[int, str]:
    fields = line.split("\t")
    if len(fields) != 2:
        raise DemoValidationError(f"Line {line_number}: {label} row must contain exactly one tab.")
    user_id = _parse_positive_int(fields[0], f"Line {line_number}: user ID")
    return user_id, fields[1]


def _split_entry(entry: str, line_number: int, label: str) -> tuple[str, str]:
    fields = entry.split(":")
    if len(fields) != 2 or not fields[0] or not fields[1]:
        raise DemoValidationError(f"Line {line_number}: malformed {label} entry.")
    return fields[0], fields[1]


def _parse_positive_int(text: object, label: str) -> int:
    try:
        value = int(str(text))
    except (TypeError, ValueError) as exc:
        raise DemoValidationError(f"{label} must be a positive integer.") from exc
    if value < 1:
        raise DemoValidationError(f"{label} must be a positive integer.")
    return value


def _parse_optional_int(text: object, label: str) -> int | None:
    if text is None or str(text).strip() == "":
        return None
    return _parse_positive_int(text, label)


def _parse_float(text: object, label: str) -> float:
    try:
        value = float(str(text))
    except (TypeError, ValueError) as exc:
        raise DemoValidationError(f"{label} must be numeric.") from exc
    if not math.isfinite(value):
        raise DemoValidationError(f"{label} must be finite.")
    return value


def _store_duplicate_checked(target: dict[int, object], user_id: int, value: object, label: str) -> None:
    if user_id in target:
        if target[user_id] == value:
            return
        raise DemoValidationError(f"Conflicting duplicate {label} row for user {user_id}.")
    target[user_id] = value


def _raise_json_constant(value: str) -> None:
    raise DemoValidationError(f"JSON contains invalid floating-point value: {value}")


def _reject_non_finite(value: object) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise DemoValidationError("JSON contains NaN or Infinity.")
    if isinstance(value, dict):
        for child in value.values():
            _reject_non_finite(child)
    if isinstance(value, list):
        for child in value:
            _reject_non_finite(child)


def _validate_benchmark_numeric_fields(row: Mapping[str, str], line_number: int) -> None:
    numeric_fields = [
        "ratingsRows",
        "trainRows",
        "testRows",
        "topL",
        "topK",
        "totalPipelineSeconds",
        "userHistorySeconds",
        "pairStatisticsSeconds",
        "similaritySeconds",
        "scoringSeconds",
        "topKSeconds",
        "evaluationSeconds",
        "itemPairRows",
        "similarityRows",
        "rawPredictionRows",
        "recommendationUsers",
        "recommendationItems",
        "predictionCoverage",
        "mae",
        "rmse",
        "precisionAtK",
        "recallAtK",
        "ndcgAtK",
        "mrrAtK",
    ]
    for field in numeric_fields:
        text = (row.get(field) or "").strip()
        if text == "":
            continue
        value = _parse_float(text, f"Line {line_number}: {field}")
        if value < 0:
            raise DemoValidationError(f"Line {line_number}: {field} must be non-negative.")
