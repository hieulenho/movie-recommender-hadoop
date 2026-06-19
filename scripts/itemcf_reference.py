"""Deterministic Item-CF reference implementation for local validation."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from dataclasses import dataclass
import datetime as dt
import json
import math
from pathlib import Path
import sys
from typing import Iterable, Mapping, Sequence


RATINGS_HEADER = ["userId", "movieId", "rating", "date"]
NEIGHBORS_HEADER = ["sourceMovieId", "neighborMovieId", "similarity", "commonUsers"]
RECOMMENDATIONS_HEADER = ["userId", "rank", "movieId", "score"]
VALID_METHODS = {"cooccurrence", "cosine"}

RatingRecord = tuple[int, int, int, str]
UserRatings = dict[int, dict[int, int]]


class ItemCFError(Exception):
    """Fatal Item-CF reference error suitable for CLI reporting."""


@dataclass(frozen=True)
class RatingLoadResult:
    """Normalized ratings and load-time counts."""

    records: list[RatingRecord]
    input_rows: int
    exact_duplicate_rows_ignored: int

    @property
    def accepted_ratings(self) -> int:
        """Return the number of unique accepted rating records."""

        return len(self.records)


@dataclass
class PairStats:
    """Aggregated co-rating statistics for one unordered item pair."""

    common_users: int = 0
    sum_xy: float = 0.0
    sum_x2: float = 0.0
    sum_y2: float = 0.0

    def add(self, x_rating: int, y_rating: int) -> None:
        """Add one user's ratings for the pair."""

        self.common_users += 1
        self.sum_xy += x_rating * y_rating
        self.sum_x2 += x_rating * x_rating
        self.sum_y2 += y_rating * y_rating


@dataclass(frozen=True)
class SimilarityEntry:
    """Directed item-neighbor similarity entry."""

    source_movie_id: int
    neighbor_movie_id: int
    similarity: float
    common_users: int


@dataclass(frozen=True)
class Recommendation:
    """Ranked recommendation for one user."""

    user_id: int
    rank: int
    movie_id: int
    score: float


def parse_positive_int(value: str) -> int:
    """Parse a CLI integer argument that must be at least 1."""

    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer greater than or equal to 1") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be an integer greater than or equal to 1")
    return parsed


def validate_positive_parameters(min_common_users: int, top_l: int, top_k: int) -> None:
    """Validate positive Item-CF numeric options."""

    if min_common_users < 1:
        raise ItemCFError("min-common-users must be greater than or equal to 1.")
    if top_l < 1:
        raise ItemCFError("top-l must be a positive integer.")
    if top_k < 1:
        raise ItemCFError("top-k must be a positive integer.")


def _parse_positive_id(value: str, field_name: str, line_number: int) -> int:
    text = value.strip()
    if not text.isdigit() or int(text) <= 0:
        raise ItemCFError(f"Line {line_number}: {field_name} must be a positive integer.")
    return int(text)


def _parse_rating(value: str, line_number: int) -> int:
    text = value.strip()
    if not text.isdigit():
        raise ItemCFError(f"Line {line_number}: rating must be an integer from 1 through 5.")
    rating = int(text)
    if rating < 1 or rating > 5:
        raise ItemCFError(f"Line {line_number}: rating must be an integer from 1 through 5.")
    return rating


def _parse_iso_date(value: str, line_number: int) -> str:
    text = value.strip()
    try:
        parsed = dt.date.fromisoformat(text)
    except ValueError as exc:
        raise ItemCFError(f"Line {line_number}: date must be a valid YYYY-MM-DD date.") from exc
    if parsed.isoformat() != text:
        raise ItemCFError(f"Line {line_number}: date must be in YYYY-MM-DD format.")
    return text


def load_normalized_ratings(input_path: Path | str) -> RatingLoadResult:
    """Load and validate Milestone 1 normalized rating CSV data."""

    path = Path(input_path)
    if not path.exists():
        raise ItemCFError(f"Input file does not exist: {path}")
    if not path.is_file():
        raise ItemCFError(f"Input path is not a file: {path}")

    records: list[RatingRecord] = []
    seen_records: set[RatingRecord] = set()
    by_user_movie: dict[tuple[int, int], RatingRecord] = {}
    input_rows = 0
    exact_duplicates = 0

    try:
        with path.open("r", encoding="utf-8", newline="") as input_file:
            reader = csv.reader(input_file)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise ItemCFError("Input CSV is empty; expected header userId,movieId,rating,date.") from exc

            if header != RATINGS_HEADER:
                raise ItemCFError("Input CSV header must be exactly: userId,movieId,rating,date")

            for line_number, row in enumerate(reader, start=2):
                input_rows += 1
                if len(row) != 4:
                    raise ItemCFError(f"Line {line_number}: expected exactly 4 CSV fields.")

                user_id = _parse_positive_id(row[0], "userId", line_number)
                movie_id = _parse_positive_id(row[1], "movieId", line_number)
                rating = _parse_rating(row[2], line_number)
                date = _parse_iso_date(row[3], line_number)
                record = (user_id, movie_id, rating, date)
                user_movie_key = (user_id, movie_id)

                previous = by_user_movie.get(user_movie_key)
                if previous is not None:
                    if previous == record:
                        exact_duplicates += 1
                        continue
                    raise ItemCFError(
                        "Line "
                        f"{line_number}: conflicting duplicate rating for userId={user_id}, "
                        f"movieId={movie_id}."
                    )

                by_user_movie[user_movie_key] = record
                if record not in seen_records:
                    seen_records.add(record)
                    records.append(record)
    except OSError as exc:
        raise OSError(f"Cannot read input file {path}: {exc}") from exc

    if not records:
        raise ItemCFError("Input CSV contains no rating rows after the header.")

    return RatingLoadResult(
        records=records,
        input_rows=input_rows,
        exact_duplicate_rows_ignored=exact_duplicates,
    )


def build_user_histories(records: Iterable[RatingRecord]) -> UserRatings:
    """Build user_ratings[user_id][movie_id] = rating."""

    user_ratings: UserRatings = {}
    for user_id, movie_id, rating, _date in records:
        user_ratings.setdefault(user_id, {})[movie_id] = rating
    return user_ratings


def compute_pair_statistics(user_ratings: Mapping[int, Mapping[int, int]]) -> dict[tuple[int, int], PairStats]:
    """Compute unordered item-pair co-rating statistics from user histories."""

    pair_stats: dict[tuple[int, int], PairStats] = {}
    for user_id in sorted(user_ratings):
        ratings = user_ratings[user_id]
        movie_ids = sorted(ratings)
        for left_index, left_movie_id in enumerate(movie_ids):
            for right_movie_id in movie_ids[left_index + 1 :]:
                pair = (left_movie_id, right_movie_id)
                stats = pair_stats.setdefault(pair, PairStats())
                stats.add(ratings[left_movie_id], ratings[right_movie_id])
    return pair_stats


def _append_similarity(
    similarities: dict[int, list[SimilarityEntry]],
    source_movie_id: int,
    neighbor_movie_id: int,
    similarity: float,
    common_users: int,
) -> None:
    similarities[source_movie_id].append(
        SimilarityEntry(
            source_movie_id=source_movie_id,
            neighbor_movie_id=neighbor_movie_id,
            similarity=similarity,
            common_users=common_users,
        )
    )


def compute_directed_similarities(
    pair_stats: Mapping[tuple[int, int], PairStats],
    method: str,
    min_common_users: int = 1,
) -> tuple[dict[int, list[SimilarityEntry]], int]:
    """Compute directed item similarities and eligible unordered pair count."""

    if method not in VALID_METHODS:
        raise ItemCFError(f"Unsupported similarity method: {method}")
    if min_common_users < 1:
        raise ItemCFError("min-common-users must be greater than or equal to 1.")

    eligible_pairs = {
        pair: stats
        for pair, stats in pair_stats.items()
        if stats.common_users >= min_common_users
    }
    similarities: dict[int, list[SimilarityEntry]] = defaultdict(list)

    if method == "cooccurrence":
        denominators: dict[int, int] = defaultdict(int)
        for (left_movie_id, right_movie_id), stats in eligible_pairs.items():
            denominators[left_movie_id] += stats.common_users
            denominators[right_movie_id] += stats.common_users

        for (left_movie_id, right_movie_id), stats in sorted(eligible_pairs.items()):
            left_similarity = stats.common_users / denominators[left_movie_id]
            right_similarity = stats.common_users / denominators[right_movie_id]
            _append_similarity(
                similarities,
                left_movie_id,
                right_movie_id,
                left_similarity,
                stats.common_users,
            )
            _append_similarity(
                similarities,
                right_movie_id,
                left_movie_id,
                right_similarity,
                stats.common_users,
            )
    else:
        for (left_movie_id, right_movie_id), stats in sorted(eligible_pairs.items()):
            denominator = math.sqrt(stats.sum_x2 * stats.sum_y2)
            if denominator == 0:
                continue
            similarity = stats.sum_xy / denominator
            _append_similarity(
                similarities,
                left_movie_id,
                right_movie_id,
                similarity,
                stats.common_users,
            )
            _append_similarity(
                similarities,
                right_movie_id,
                left_movie_id,
                similarity,
                stats.common_users,
            )

    return dict(similarities), len(eligible_pairs)


def retain_top_l_neighbors(
    directed_similarities: Mapping[int, Sequence[SimilarityEntry]],
    top_l: int,
) -> dict[int, list[SimilarityEntry]]:
    """Keep at most Top-L neighbors for each source movie."""

    if top_l < 1:
        raise ItemCFError("top-l must be a positive integer.")

    retained: dict[int, list[SimilarityEntry]] = {}
    for source_movie_id in sorted(directed_similarities):
        sorted_entries = sorted(
            directed_similarities[source_movie_id],
            key=lambda entry: (-entry.similarity, entry.neighbor_movie_id),
        )
        retained[source_movie_id] = sorted_entries[:top_l]
    return retained


def score_unseen_candidates(
    rated_items: Mapping[int, int],
    top_l_neighbors: Mapping[int, Sequence[SimilarityEntry]],
) -> dict[int, float]:
    """Score unseen candidate movies for one user from retained directed neighbors."""

    numerators: dict[int, float] = defaultdict(float)
    denominators: dict[int, float] = defaultdict(float)
    seen_movie_ids = set(rated_items)

    for rated_movie_id in sorted(rated_items):
        rating = rated_items[rated_movie_id]
        for entry in top_l_neighbors.get(rated_movie_id, []):
            candidate_movie_id = entry.neighbor_movie_id
            if candidate_movie_id in seen_movie_ids:
                continue
            numerators[candidate_movie_id] += entry.similarity * rating
            denominators[candidate_movie_id] += abs(entry.similarity)

    return {
        movie_id: numerators[movie_id] / denominator
        for movie_id, denominator in denominators.items()
        if denominator != 0
    }


def generate_top_k_recommendations(
    user_ratings: Mapping[int, Mapping[int, int]],
    top_l_neighbors: Mapping[int, Sequence[SimilarityEntry]],
    top_k: int,
) -> list[Recommendation]:
    """Generate deterministic ranked Top-K recommendations for all users."""

    if top_k < 1:
        raise ItemCFError("top-k must be a positive integer.")

    recommendations: list[Recommendation] = []
    for user_id in sorted(user_ratings):
        candidate_scores = score_unseen_candidates(user_ratings[user_id], top_l_neighbors)
        sorted_candidates = sorted(
            candidate_scores.items(),
            key=lambda item: (-item[1], item[0]),
        )[:top_k]
        for rank, (movie_id, score) in enumerate(sorted_candidates, start=1):
            recommendations.append(
                Recommendation(user_id=user_id, rank=rank, movie_id=movie_id, score=score)
            )
    return recommendations


def format_float(value: float) -> str:
    """Format floating-point output with stable 12-decimal precision."""

    return f"{value:.12f}"


def iter_neighbor_entries(
    top_l_neighbors: Mapping[int, Sequence[SimilarityEntry]],
) -> Iterable[SimilarityEntry]:
    """Yield neighbor entries in required output order."""

    for source_movie_id in sorted(top_l_neighbors):
        for entry in sorted(
            top_l_neighbors[source_movie_id],
            key=lambda item: (-item.similarity, item.neighbor_movie_id),
        ):
            yield entry


def write_neighbor_csv(
    top_l_neighbors: Mapping[int, Sequence[SimilarityEntry]],
    output_path: Path | str,
) -> None:
    """Write directed neighbor entries to CSV."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.writer(output_file, lineterminator="\n")
            writer.writerow(NEIGHBORS_HEADER)
            for entry in iter_neighbor_entries(top_l_neighbors):
                writer.writerow(
                    [
                        entry.source_movie_id,
                        entry.neighbor_movie_id,
                        format_float(entry.similarity),
                        entry.common_users,
                    ]
                )
    except OSError as exc:
        raise OSError(f"Cannot write neighbor output {path}: {exc}") from exc


def write_recommendation_csv(
    recommendations: Sequence[Recommendation],
    output_path: Path | str,
) -> None:
    """Write ranked recommendations to CSV."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.writer(output_file, lineterminator="\n")
            writer.writerow(RECOMMENDATIONS_HEADER)
            for recommendation in sorted(recommendations, key=lambda item: (item.user_id, item.rank)):
                writer.writerow(
                    [
                        recommendation.user_id,
                        recommendation.rank,
                        recommendation.movie_id,
                        format_float(recommendation.score),
                    ]
                )
    except OSError as exc:
        raise OSError(f"Cannot write recommendation output {path}: {exc}") from exc


def write_statistics_json(stats: Mapping[str, object], output_path: Path | str) -> None:
    """Write reference-model statistics as readable UTF-8 JSON."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(
            json.dumps(dict(stats), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise OSError(f"Cannot write statistics output {path}: {exc}") from exc


def ensure_outputs_do_not_overwrite_input(
    input_path: Path | str,
    output_paths: Sequence[Path | str],
) -> None:
    """Fail if any output path resolves to the input path."""

    resolved_input = Path(input_path).resolve()
    for output_path in output_paths:
        if Path(output_path).resolve() == resolved_input:
            raise ItemCFError(f"Output path would overwrite the input file: {output_path}")


def build_statistics(
    method: str,
    input_file: Path | str,
    load_result: RatingLoadResult,
    user_ratings: Mapping[int, Mapping[int, int]],
    pair_stats: Mapping[tuple[int, int], PairStats],
    eligible_unordered_pairs: int,
    directed_before_top_l: Mapping[int, Sequence[SimilarityEntry]],
    top_l_neighbors: Mapping[int, Sequence[SimilarityEntry]],
    recommendations: Sequence[Recommendation],
    min_common_users: int,
    top_l: int,
    top_k: int,
) -> dict[str, object]:
    """Build deterministic run statistics."""

    item_ids = {movie_id for ratings in user_ratings.values() for movie_id in ratings}
    users_with_recommendations = {recommendation.user_id for recommendation in recommendations}
    return {
        "method": method,
        "input_file": str(input_file),
        "users": len(user_ratings),
        "items": len(item_ids),
        "input_rows": load_result.input_rows,
        "accepted_ratings": load_result.accepted_ratings,
        "exact_duplicate_rows_ignored": load_result.exact_duplicate_rows_ignored,
        "unordered_item_pairs": len(pair_stats),
        "eligible_unordered_item_pairs": eligible_unordered_pairs,
        "directed_similarity_entries_before_top_l": sum(
            len(entries) for entries in directed_before_top_l.values()
        ),
        "directed_similarity_entries_after_top_l": sum(
            len(entries) for entries in top_l_neighbors.values()
        ),
        "users_with_recommendations": len(users_with_recommendations),
        "recommendation_rows": len(recommendations),
        "min_common_users": min_common_users,
        "top_l": top_l,
        "top_k": top_k,
    }


def run_reference_pipeline(
    input_path: Path | str,
    method: str,
    neighbors_output: Path | str,
    recommendations_output: Path | str,
    stats_output: Path | str,
    min_common_users: int = 1,
    top_l: int = 50,
    top_k: int = 10,
) -> dict[str, object]:
    """Run the complete local Item-CF reference pipeline."""

    if method not in VALID_METHODS:
        raise ItemCFError(f"Unsupported similarity method: {method}")
    validate_positive_parameters(min_common_users, top_l, top_k)
    ensure_outputs_do_not_overwrite_input(
        input_path,
        [neighbors_output, recommendations_output, stats_output],
    )

    load_result = load_normalized_ratings(input_path)
    user_ratings = build_user_histories(load_result.records)
    pair_stats = compute_pair_statistics(user_ratings)
    directed_similarities, eligible_unordered_pairs = compute_directed_similarities(
        pair_stats,
        method,
        min_common_users,
    )
    top_l_neighbors = retain_top_l_neighbors(directed_similarities, top_l)
    recommendations = generate_top_k_recommendations(user_ratings, top_l_neighbors, top_k)
    stats = build_statistics(
        method=method,
        input_file=input_path,
        load_result=load_result,
        user_ratings=user_ratings,
        pair_stats=pair_stats,
        eligible_unordered_pairs=eligible_unordered_pairs,
        directed_before_top_l=directed_similarities,
        top_l_neighbors=top_l_neighbors,
        recommendations=recommendations,
        min_common_users=min_common_users,
        top_l=top_l,
        top_k=top_k,
    )

    write_neighbor_csv(top_l_neighbors, neighbors_output)
    write_recommendation_csv(recommendations, recommendations_output)
    write_statistics_json(stats, stats_output)
    return stats


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the Item-CF reference CLI parser."""

    parser = argparse.ArgumentParser(
        description="Run a deterministic local Item-CF reference implementation.",
    )
    parser.add_argument("--input", required=True, help="Normalized rating CSV input file.")
    parser.add_argument(
        "--method",
        required=True,
        choices=sorted(VALID_METHODS),
        help="Similarity method to use.",
    )
    parser.add_argument(
        "--min-common-users",
        type=parse_positive_int,
        default=1,
        help="Minimum number of common users required for an item pair.",
    )
    parser.add_argument(
        "--top-l",
        type=parse_positive_int,
        default=50,
        help="Maximum neighbors to retain for each source movie.",
    )
    parser.add_argument(
        "--top-k",
        type=parse_positive_int,
        default=10,
        help="Maximum recommendations to retain for each user.",
    )
    parser.add_argument("--neighbors-output", required=True, help="Path to write neighbor CSV.")
    parser.add_argument(
        "--recommendations-output",
        required=True,
        help="Path to write recommendation CSV.",
    )
    parser.add_argument("--stats-output", required=True, help="Path to write statistics JSON.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        stats = run_reference_pipeline(
            input_path=args.input,
            method=args.method,
            min_common_users=args.min_common_users,
            top_l=args.top_l,
            top_k=args.top_k,
            neighbors_output=args.neighbors_output,
            recommendations_output=args.recommendations_output,
            stats_output=args.stats_output,
        )
    except (ItemCFError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(
        "Item-CF reference complete: "
        f"method={stats['method']}, "
        f"{stats['directed_similarity_entries_after_top_l']} neighbor rows, "
        f"{stats['recommendation_rows']} recommendation rows."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
