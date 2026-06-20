"""Evaluate raw predictions and Top-K recommendations against held-out ratings."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import datetime as dt
import json
import math
from pathlib import Path
import sys
from typing import Mapping, Sequence


RATINGS_HEADER = ["userId", "movieId", "rating", "date"]
PER_USER_HEADER = [
    "userId",
    "testMovieId",
    "actualRating",
    "predictedScore",
    "absoluteError",
    "squaredError",
    "isRelevant",
    "recommendationRank",
    "hit",
    "ndcg",
    "mrr",
    "recommendationCount",
]
METRICS_CSV_HEADER = [
    "method",
    "k",
    "relevanceThreshold",
    "testRows",
    "matchedPredictions",
    "predictionCoverage",
    "mae",
    "rmse",
    "rankingEligibleUsers",
    "hits",
    "precisionAtK",
    "recallAtK",
    "hitRateAtK",
    "ndcgAtK",
    "mrrAtK",
]
EVALUATION_METHOD = "leave-one-out-by-time"


class EvaluationError(Exception):
    """Fatal evaluation error suitable for concise CLI reporting."""


@dataclass(frozen=True)
class RatingRecord:
    user_id: int
    movie_id: int
    rating: int
    date: str


@dataclass(frozen=True)
class RecommendationEntry:
    movie_id: int
    score: float


@dataclass(frozen=True)
class UserDiagnostics:
    user_id: int
    test_movie_id: int
    actual_rating: int
    predicted_score: float | None
    absolute_error: float | None
    squared_error: float | None
    is_relevant: bool
    recommendation_rank: int | None
    hit: int
    ndcg: float
    mrr: float
    recommendation_count: int


def _require_file(path: Path, name: str) -> None:
    if not path.exists():
        raise EvaluationError(f"{name} file does not exist: {path}")
    if not path.is_file():
        raise EvaluationError(f"{name} path is not a file: {path}")


def _parse_positive_id(value: str, field_name: str, line_number: int) -> int:
    text = value.strip()
    if not text.isdigit() or int(text) <= 0:
        raise EvaluationError(f"Line {line_number}: {field_name} must be a positive integer.")
    return int(text)


def _parse_rating(value: str, line_number: int) -> int:
    text = value.strip()
    if not text.isdigit():
        raise EvaluationError(f"Line {line_number}: rating must be an integer from 1 through 5.")
    rating = int(text)
    if rating < 1 or rating > 5:
        raise EvaluationError(f"Line {line_number}: rating must be an integer from 1 through 5.")
    return rating


def _parse_iso_date(value: str, line_number: int) -> str:
    text = value.strip()
    try:
        parsed = dt.date.fromisoformat(text)
    except ValueError as exc:
        raise EvaluationError(f"Line {line_number}: date must be a valid YYYY-MM-DD date.") from exc
    if parsed.isoformat() != text:
        raise EvaluationError(f"Line {line_number}: date must be in YYYY-MM-DD format.")
    return text


def _parse_score(value: str, line_number: int, require_rating_range: bool) -> float:
    text = value.strip()
    try:
        score = float(text)
    except ValueError as exc:
        raise EvaluationError(f"Line {line_number}: score must be a finite number.") from exc
    if not math.isfinite(score):
        raise EvaluationError(f"Line {line_number}: score must be a finite number.")
    if require_rating_range and (score < 1.0 or score > 5.0):
        raise EvaluationError(f"Line {line_number}: recommendation score must be from 1.0 through 5.0.")
    return score


def _format_decimal(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.10f}"


def _safe_average(total: float, count: int) -> float:
    if count == 0:
        return 0.0
    return total / count


def _load_ratings_csv(path: Path | str, name: str) -> list[RatingRecord]:
    file_path = Path(path)
    _require_file(file_path, name)
    records: list[RatingRecord] = []
    by_user_movie: dict[tuple[int, int], RatingRecord] = {}

    try:
        with file_path.open("r", encoding="utf-8", newline="") as input_file:
            reader = csv.reader(input_file)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise EvaluationError(f"{name} CSV is empty; expected header userId,movieId,rating,date.") from exc
            if header != RATINGS_HEADER:
                raise EvaluationError(f"{name} CSV header must be exactly: userId,movieId,rating,date")

            for line_number, row in enumerate(reader, start=2):
                if len(row) != 4:
                    raise EvaluationError(f"Line {line_number}: expected exactly 4 CSV fields in {name}.")
                user_id = _parse_positive_id(row[0], "userId", line_number)
                movie_id = _parse_positive_id(row[1], "movieId", line_number)
                rating = _parse_rating(row[2], line_number)
                date = _parse_iso_date(row[3], line_number)
                record = RatingRecord(user_id, movie_id, rating, date)
                key = (user_id, movie_id)
                previous = by_user_movie.get(key)
                if previous is not None:
                    if previous == record:
                        continue
                    raise EvaluationError(
                        f"Line {line_number}: conflicting duplicate rating for userId={user_id}, "
                        f"movieId={movie_id} in {name}."
                    )
                by_user_movie[key] = record
                records.append(record)
    except OSError as exc:
        raise OSError(f"Cannot read {name} CSV {file_path}: {exc}") from exc

    return sorted(records, key=lambda item: (item.user_id, item.date, item.movie_id))


def load_raw_predictions(path: Path | str) -> dict[tuple[int, int], float]:
    """Load raw prediction rows keyed by (userId, movieId)."""

    file_path = Path(path)
    _require_file(file_path, "Raw predictions")
    predictions: dict[tuple[int, int], float] = {}

    try:
        with file_path.open("r", encoding="utf-8", newline="") as input_file:
            for line_number, raw_line in enumerate(input_file, start=1):
                line = raw_line.rstrip("\n")
                if line.endswith("\r"):
                    line = line[:-1]
                if not line:
                    raise EvaluationError(f"Line {line_number}: raw prediction row must not be empty.")
                sections = line.split("\t")
                if len(sections) != 2:
                    raise EvaluationError(
                        f"Line {line_number}: expected userId,movieId<TAB>score raw prediction row."
                    )
                key_fields = sections[0].split(",")
                if len(key_fields) != 2:
                    raise EvaluationError(f"Line {line_number}: raw prediction key must contain userId,movieId.")
                user_id = _parse_positive_id(key_fields[0], "userId", line_number)
                movie_id = _parse_positive_id(key_fields[1], "movieId", line_number)
                score = _parse_score(sections[1], line_number, require_rating_range=False)
                key = (user_id, movie_id)
                previous = predictions.get(key)
                if previous is not None:
                    if previous == score:
                        continue
                    raise EvaluationError(
                        f"Line {line_number}: conflicting duplicate prediction for userId={user_id}, "
                        f"movieId={movie_id}."
                    )
                predictions[key] = score
    except OSError as exc:
        raise OSError(f"Cannot read raw predictions {file_path}: {exc}") from exc

    return predictions


def load_recommendations(path: Path | str, k: int) -> dict[int, list[RecommendationEntry]]:
    """Load final Top-K recommendation rows keyed by user ID."""

    if k < 1:
        raise EvaluationError("k must be at least 1.")

    file_path = Path(path)
    _require_file(file_path, "Recommendations")
    recommendations: dict[int, list[RecommendationEntry]] = {}

    try:
        with file_path.open("r", encoding="utf-8", newline="") as input_file:
            for line_number, raw_line in enumerate(input_file, start=1):
                line = raw_line.rstrip("\n")
                if line.endswith("\r"):
                    line = line[:-1]
                if not line:
                    raise EvaluationError(f"Line {line_number}: recommendation row must not be empty.")
                sections = line.split("\t")
                if len(sections) != 2:
                    raise EvaluationError(
                        f"Line {line_number}: expected userId<TAB>movieId:score,... recommendation row."
                    )
                user_id = _parse_positive_id(sections[0], "userId", line_number)
                if user_id in recommendations:
                    raise EvaluationError(f"Line {line_number}: duplicate recommendation row for userId={user_id}.")
                entries = _parse_recommendation_entries(sections[1], line_number, k)
                recommendations[user_id] = entries
    except OSError as exc:
        raise OSError(f"Cannot read recommendations {file_path}: {exc}") from exc

    return recommendations


def _parse_recommendation_entries(value: str, line_number: int, k: int) -> list[RecommendationEntry]:
    text = value.strip()
    if not text:
        raise EvaluationError(f"Line {line_number}: recommendation list must not be empty.")

    entries: list[RecommendationEntry] = []
    seen_movie_ids: set[int] = set()
    for raw_entry in text.split(","):
        entry = raw_entry.strip()
        fields = entry.split(":")
        if len(fields) != 2:
            raise EvaluationError(f"Line {line_number}: recommendation entry must be movieId:score.")
        movie_id = _parse_positive_id(fields[0], "movieId", line_number)
        if movie_id in seen_movie_ids:
            raise EvaluationError(f"Line {line_number}: duplicate recommendation movieId={movie_id}.")
        seen_movie_ids.add(movie_id)
        score = _parse_score(fields[1], line_number, require_rating_range=True)
        entries.append(RecommendationEntry(movie_id=movie_id, score=score))

    if len(entries) > k:
        raise EvaluationError(f"Line {line_number}: recommendation row contains more than K={k} entries.")

    for previous, current in zip(entries, entries[1:]):
        if previous.score < current.score or (
            previous.score == current.score and previous.movie_id > current.movie_id
        ):
            raise EvaluationError(
                f"Line {line_number}: recommendations must be ordered by score descending, movieId ascending."
            )

    return entries


def validate_evaluation_inputs(
    train_records: Sequence[RatingRecord],
    test_records: Sequence[RatingRecord],
    recommendations: Mapping[int, Sequence[RecommendationEntry]],
) -> tuple[int, int]:
    """Return overlap and watched-recommendation counts, raising on either."""

    train_pairs = {(record.user_id, record.movie_id) for record in train_records}
    test_pairs = {(record.user_id, record.movie_id) for record in test_records}
    overlap = len(train_pairs & test_pairs)
    if overlap:
        raise EvaluationError(f"Train/test overlap detected for {overlap} user-movie pair(s).")

    watched_by_user: dict[int, set[int]] = {}
    for record in train_records:
        watched_by_user.setdefault(record.user_id, set()).add(record.movie_id)

    watched_recommendations = 0
    for user_id, entries in recommendations.items():
        watched = watched_by_user.get(user_id, set())
        watched_recommendations += sum(1 for entry in entries if entry.movie_id in watched)
    if watched_recommendations:
        raise EvaluationError(f"Watched recommendations detected: {watched_recommendations}.")

    return overlap, watched_recommendations


def compute_metrics(
    train_records: Sequence[RatingRecord],
    test_records: Sequence[RatingRecord],
    raw_predictions: Mapping[tuple[int, int], float],
    recommendations: Mapping[int, Sequence[RecommendationEntry]],
    k: int,
    relevance_threshold: int,
) -> tuple[dict[str, object], list[UserDiagnostics]]:
    """Compute aggregate and deterministic per-user evaluation metrics."""

    if k < 1:
        raise EvaluationError("k must be at least 1.")
    if relevance_threshold < 1 or relevance_threshold > 5:
        raise EvaluationError("relevance threshold must be an integer from 1 through 5.")

    overlap, watched = validate_evaluation_inputs(train_records, test_records, recommendations)

    diagnostics: list[UserDiagnostics] = []
    matched_predictions = 0
    missing_predictions = 0
    absolute_error_sum = 0.0
    squared_error_sum = 0.0
    ranking_eligible_users = 0
    ranking_hits = 0
    precision_sum = 0.0
    recall_sum = 0.0
    hit_rate_sum = 0.0
    ndcg_sum = 0.0
    mrr_sum = 0.0

    for record in sorted(test_records, key=lambda item: item.user_id):
        prediction = raw_predictions.get((record.user_id, record.movie_id))
        if prediction is None:
            missing_predictions += 1
            absolute_error = None
            squared_error = None
        else:
            matched_predictions += 1
            absolute_error = abs(record.rating - prediction)
            squared_error = (record.rating - prediction) ** 2
            absolute_error_sum += absolute_error
            squared_error_sum += squared_error

        entries = list(recommendations.get(record.user_id, []))[:k]
        rank = next(
            (index for index, entry in enumerate(entries, start=1) if entry.movie_id == record.movie_id),
            None,
        )
        is_relevant = record.rating >= relevance_threshold
        hit = 1 if is_relevant and rank is not None else 0
        ndcg = 1.0 / math.log2(rank + 1) if hit and rank is not None else 0.0
        mrr = 1.0 / rank if hit and rank is not None else 0.0

        if is_relevant:
            ranking_eligible_users += 1
            ranking_hits += hit
            precision_sum += hit / k
            recall_sum += hit
            hit_rate_sum += hit
            ndcg_sum += ndcg
            mrr_sum += mrr

        diagnostics.append(
            UserDiagnostics(
                user_id=record.user_id,
                test_movie_id=record.movie_id,
                actual_rating=record.rating,
                predicted_score=prediction,
                absolute_error=absolute_error,
                squared_error=squared_error,
                is_relevant=is_relevant,
                recommendation_rank=rank,
                hit=hit,
                ndcg=ndcg,
                mrr=mrr,
                recommendation_count=len(entries),
            )
        )

    test_rows = len(test_records)
    mae = None if matched_predictions == 0 else absolute_error_sum / matched_predictions
    rmse = None if matched_predictions == 0 else math.sqrt(squared_error_sum / matched_predictions)
    users_with_recommendations = sum(1 for record in test_records if recommendations.get(record.user_id))
    metrics = {
        "evaluation_method": EVALUATION_METHOD,
        "k": k,
        "relevance_threshold": relevance_threshold,
        "test_rows": test_rows,
        "matched_test_predictions": matched_predictions,
        "missing_test_predictions": missing_predictions,
        "prediction_coverage": 0.0 if test_rows == 0 else matched_predictions / test_rows,
        "mae": mae,
        "rmse": rmse,
        "ranking_eligible_users": ranking_eligible_users,
        "ranking_hits": ranking_hits,
        "users_with_recommendations": users_with_recommendations,
        "recommendation_user_coverage": 0.0 if test_rows == 0 else users_with_recommendations / test_rows,
        "precision_at_k": _safe_average(precision_sum, ranking_eligible_users),
        "recall_at_k": _safe_average(recall_sum, ranking_eligible_users),
        "hit_rate_at_k": _safe_average(hit_rate_sum, ranking_eligible_users),
        "ndcg_at_k": _safe_average(ndcg_sum, ranking_eligible_users),
        "mrr_at_k": _safe_average(mrr_sum, ranking_eligible_users),
        "watched_recommendations_found": watched,
        "train_test_overlap_rows": overlap,
    }
    return metrics, diagnostics


def write_metrics_json(metrics: Mapping[str, object], output_path: Path | str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(
            json.dumps(dict(metrics), indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise OSError(f"Cannot write metrics JSON {path}: {exc}") from exc


def write_metrics_csv(metrics: Mapping[str, object], output_path: Path | str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = [
        metrics["evaluation_method"],
        metrics["k"],
        metrics["relevance_threshold"],
        metrics["test_rows"],
        metrics["matched_test_predictions"],
        _format_decimal(metrics["prediction_coverage"]),  # type: ignore[arg-type]
        _format_decimal(metrics["mae"]),  # type: ignore[arg-type]
        _format_decimal(metrics["rmse"]),  # type: ignore[arg-type]
        metrics["ranking_eligible_users"],
        metrics["ranking_hits"],
        _format_decimal(metrics["precision_at_k"]),  # type: ignore[arg-type]
        _format_decimal(metrics["recall_at_k"]),  # type: ignore[arg-type]
        _format_decimal(metrics["hit_rate_at_k"]),  # type: ignore[arg-type]
        _format_decimal(metrics["ndcg_at_k"]),  # type: ignore[arg-type]
        _format_decimal(metrics["mrr_at_k"]),  # type: ignore[arg-type]
    ]
    try:
        with path.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.writer(output_file, lineterminator="\n")
            writer.writerow(METRICS_CSV_HEADER)
            writer.writerow(row)
    except OSError as exc:
        raise OSError(f"Cannot write metrics CSV {path}: {exc}") from exc


def write_per_user_csv(diagnostics: Sequence[UserDiagnostics], output_path: Path | str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.writer(output_file, lineterminator="\n")
            writer.writerow(PER_USER_HEADER)
            for item in sorted(diagnostics, key=lambda row: row.user_id):
                writer.writerow(
                    [
                        item.user_id,
                        item.test_movie_id,
                        item.actual_rating,
                        _format_decimal(item.predicted_score),
                        _format_decimal(item.absolute_error),
                        _format_decimal(item.squared_error),
                        1 if item.is_relevant else 0,
                        "" if item.recommendation_rank is None else item.recommendation_rank,
                        item.hit,
                        _format_decimal(item.ndcg),
                        _format_decimal(item.mrr),
                        item.recommendation_count,
                    ]
                )
    except OSError as exc:
        raise OSError(f"Cannot write per-user metrics CSV {path}: {exc}") from exc


def run_evaluation(
    train_path: Path | str,
    test_path: Path | str,
    raw_predictions_path: Path | str,
    recommendations_path: Path | str,
    metrics_json_path: Path | str,
    metrics_csv_path: Path | str,
    per_user_output_path: Path | str,
    k: int = 10,
    relevance_threshold: int = 4,
) -> dict[str, object]:
    """Run full evaluation and write aggregate plus per-user artifacts."""

    if k < 1:
        raise EvaluationError("k must be at least 1.")
    if relevance_threshold < 1 or relevance_threshold > 5:
        raise EvaluationError("relevance threshold must be an integer from 1 through 5.")

    train_records = _load_ratings_csv(train_path, "Train ratings")
    test_records = _load_ratings_csv(test_path, "Test ratings")
    raw_predictions = load_raw_predictions(raw_predictions_path)
    recommendations = load_recommendations(recommendations_path, k)
    metrics, diagnostics = compute_metrics(
        train_records,
        test_records,
        raw_predictions,
        recommendations,
        k,
        relevance_threshold,
    )
    write_metrics_json(metrics, metrics_json_path)
    write_metrics_csv(metrics, metrics_csv_path)
    write_per_user_csv(diagnostics, per_user_output_path)
    return metrics


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer greater than or equal to 1") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be an integer greater than or equal to 1")
    return parsed


def _relevance_threshold(value: str) -> int:
    parsed = _positive_int(value)
    if parsed > 5:
        raise argparse.ArgumentTypeError("must be an integer from 1 through 5")
    return parsed


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate held-out ratings against raw predictions and final Top-K recommendations.",
    )
    parser.add_argument("--train", required=True, help="Train ratings CSV.")
    parser.add_argument("--test", required=True, help="Test ratings CSV.")
    parser.add_argument("--raw-predictions", required=True, help="Raw prediction text file.")
    parser.add_argument("--recommendations", required=True, help="Final Top-K recommendation text file.")
    parser.add_argument("--k", type=_positive_int, default=10, help="Top-K cutoff.")
    parser.add_argument(
        "--relevance-threshold",
        type=_relevance_threshold,
        default=4,
        help="Integer relevance threshold from 1 through 5.",
    )
    parser.add_argument("--metrics-json", required=True, help="Path to write metrics JSON.")
    parser.add_argument("--metrics-csv", required=True, help="Path to write one-row metrics CSV.")
    parser.add_argument("--per-user-output", required=True, help="Path to write per-user diagnostics CSV.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        metrics = run_evaluation(
            train_path=args.train,
            test_path=args.test,
            raw_predictions_path=args.raw_predictions,
            recommendations_path=args.recommendations,
            k=args.k,
            relevance_threshold=args.relevance_threshold,
            metrics_json_path=args.metrics_json,
            metrics_csv_path=args.metrics_csv,
            per_user_output_path=args.per_user_output,
        )
    except (EvaluationError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(
        "Evaluation complete: "
        f"coverage={_format_decimal(metrics['prediction_coverage'])}, "
        f"mae={_format_decimal(metrics['mae']) or 'null'}, "
        f"rmse={_format_decimal(metrics['rmse']) or 'null'}, "
        f"hit_rate_at_k={_format_decimal(metrics['hit_rate_at_k'])}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
