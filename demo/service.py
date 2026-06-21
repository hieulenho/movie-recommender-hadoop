"""Service helpers for the read-only Streamlit demo."""

from __future__ import annotations

import csv
import io
from typing import Mapping, Sequence

from demo.data_loader import fallback_movie_metadata
from demo.models import BenchmarkRun, DemoDataBundle, DemoValidationError, EvaluationMetrics, MovieMetadata, UserProfile


def list_user_ids(bundle: DemoDataBundle) -> list[int]:
    return sorted(bundle.users)


def get_user_profile(bundle: DemoDataBundle, user_id: int) -> UserProfile:
    try:
        return bundle.users[user_id]
    except KeyError as exc:
        raise DemoValidationError(f"Unknown user ID: {user_id}") from exc


def build_history_rows(profile: UserProfile, metadata: Mapping[int, MovieMetadata]) -> list[dict[str, object]]:
    rows = []
    for watched in profile.watched:
        movie = metadata.get(watched.movie_id) or fallback_movie_metadata(watched.movie_id)
        rows.append(
            {
                "Movie ID": watched.movie_id,
                "Title": movie.title,
                "Year": movie.year or "",
                "Genres": movie.genres,
                "Rating": watched.rating,
            }
        )
    return rows


def build_recommendation_rows(profile: UserProfile, metadata: Mapping[int, MovieMetadata]) -> list[dict[str, object]]:
    rows = []
    for rec in profile.recommendations:
        movie = metadata.get(rec.movie_id) or fallback_movie_metadata(rec.movie_id)
        rows.append(
            {
                "Rank": rec.rank,
                "Movie ID": rec.movie_id,
                "Title": movie.title,
                "Year": movie.year or "",
                "Genres": movie.genres,
                "Predicted score": f"{rec.score:.10f}",
            }
        )
    return rows


def build_user_summary(profile: UserProfile) -> dict[str, object]:
    watched_count = len(profile.watched)
    rec_count = len(profile.recommendations)
    rating_avg = None if watched_count == 0 else sum(item.rating for item in profile.watched) / watched_count
    score_avg = None if rec_count == 0 else sum(item.score for item in profile.recommendations) / rec_count
    highest_score = None if rec_count == 0 else max(item.score for item in profile.recommendations)
    return {
        "user_id": profile.user_id,
        "watched_movie_count": watched_count,
        "recommendation_count": rec_count,
        "average_historical_rating": rating_avg,
        "average_recommendation_score": score_avg,
        "highest_recommendation_score": highest_score,
    }


def build_recommendation_csv(profile: UserProfile, metadata: Mapping[int, MovieMetadata]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["rank", "movieId", "title", "year", "genres", "predictedScore"])
    for rec in profile.recommendations:
        movie = metadata.get(rec.movie_id) or fallback_movie_metadata(rec.movie_id)
        writer.writerow([rec.rank, rec.movie_id, movie.title, movie.year or "", movie.genres, rec.score_text])
    return buffer.getvalue()


def summarize_evaluation_metrics(metrics: EvaluationMetrics | None) -> dict[str, object]:
    if metrics is None:
        return {}
    keys = [
        "evaluation_method",
        "k",
        "relevance_threshold",
        "test_rows",
        "prediction_coverage",
        "mae",
        "rmse",
        "precision_at_k",
        "recall_at_k",
        "hit_rate_at_k",
        "ndcg_at_k",
        "mrr_at_k",
        "matched_test_predictions",
        "missing_test_predictions",
        "ranking_eligible_users",
        "ranking_hits",
        "recommendation_user_coverage",
        "train_test_overlap_rows",
        "watched_recommendations_found",
    ]
    return {key: metrics.get(key) for key in keys}


def summarize_benchmark_results(runs: Sequence[BenchmarkRun]) -> dict[str, object]:
    successful = [run for run in runs if run.status == "completed"]
    failed = [run for run in runs if run.status != "completed"]
    ratings = [run.ratings_rows for run in successful if run.ratings_rows is not None]
    return {
        "successful_count": len(successful),
        "failed_count": len(failed),
        "min_ratings_rows": min(ratings) if ratings else None,
        "max_ratings_rows": max(ratings) if ratings else None,
        "successful_runs": successful,
        "failed_runs": failed,
    }


def validate_bundle_integrity(bundle: DemoDataBundle) -> list[str]:
    errors: list[str] = []
    for user_id, profile in bundle.users.items():
        watched_ids = {item.movie_id for item in profile.watched}
        rec_ids: set[int] = set()
        previous_score: float | None = None
        previous_movie_id: int | None = None
        if profile.recommendations == tuple():
            continue
        for rec in profile.recommendations:
            if rec.movie_id in watched_ids:
                errors.append(f"User {user_id} recommendation contains watched movie {rec.movie_id}.")
            if rec.movie_id in rec_ids:
                errors.append(f"User {user_id} recommendation duplicates movie {rec.movie_id}.")
            rec_ids.add(rec.movie_id)
            if previous_score is not None:
                if rec.score > previous_score:
                    errors.append(f"User {user_id} recommendation order is not score-descending.")
                if rec.score == previous_score and previous_movie_id is not None and rec.movie_id < previous_movie_id:
                    errors.append(f"User {user_id} recommendation tie order is not numeric ascending.")
            previous_score = rec.score
            previous_movie_id = rec.movie_id
    recommendation_users = {
        user_id
        for user_id, profile in bundle.users.items()
        if profile.recommendations
    }
    unknown = recommendation_users - set(bundle.users)
    for user_id in sorted(unknown):
        errors.append(f"Recommendations exist for unknown user {user_id}.")
    return errors


def benchmark_table_rows(runs: Sequence[BenchmarkRun]) -> list[dict[str, object]]:
    rows = []
    for run in runs:
        raw = run.raw
        rows.append(
            {
                "experiment": run.experiment_id,
                "method": run.method,
                "ratings": raw.get("ratingsRows", ""),
                "total runtime": raw.get("totalPipelineSeconds", ""),
                "pair rows": raw.get("itemPairRows", ""),
                "similarity rows": raw.get("similarityRows", ""),
                "recommendation users": raw.get("recommendationUsers", ""),
                "prediction coverage": raw.get("predictionCoverage", ""),
                "RMSE": raw.get("rmse", ""),
                "NDCG@K": raw.get("ndcgAtK", ""),
            }
        )
    return rows


def stage_runtime_rows(run: BenchmarkRun) -> list[dict[str, object]]:
    mapping = [
        ("User History", "userHistorySeconds"),
        ("Pair Statistics", "pairStatisticsSeconds"),
        ("Similarity", "similaritySeconds"),
        ("Scoring", "scoringSeconds"),
        ("Top-K", "topKSeconds"),
        ("Evaluation", "evaluationSeconds"),
    ]
    return [{"Stage": label, "Seconds": run.raw.get(column, "")} for label, column in mapping]

