"""Generate deterministic normalized rating datasets for scalability tests."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import random
import sys
from typing import Mapping, Sequence


RATINGS_HEADER = ["userId", "movieId", "rating", "date"]
DATASET_TYPE = "synthetic"
DEFAULT_SEED = 42
DEFAULT_START_DATE = "2005-01-01"


class SyntheticRatingsError(Exception):
    """Fatal generator error suitable for concise CLI reporting."""


def parse_start_date(value: str) -> dt.date:
    """Parse an ISO start date and reject non-canonical date text."""

    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError as exc:
        raise SyntheticRatingsError("start-date must be a valid ISO date in YYYY-MM-DD format.") from exc
    if parsed.isoformat() != value:
        raise SyntheticRatingsError("start-date must be a valid ISO date in YYYY-MM-DD format.")
    return parsed


def validate_generation_request(users: int, items: int, ratings_per_user: int, seed: int, start_date: str) -> None:
    """Validate generator dimensions without silently correcting values."""

    if not isinstance(seed, int):
        raise SyntheticRatingsError("seed must be an integer.")
    if users < 2:
        raise SyntheticRatingsError("users must be at least 2.")
    if items < 3:
        raise SyntheticRatingsError("items must be at least 3.")
    if ratings_per_user < 2:
        raise SyntheticRatingsError("ratings-per-user must be at least 2.")
    if ratings_per_user > items:
        raise SyntheticRatingsError("ratings-per-user must not exceed items.")
    parse_start_date(start_date)


def _choose_item_sets(users: int, items: int, ratings_per_user: int, rng: random.Random) -> list[set[int]]:
    """Choose user item sets with deterministic overlap and broad item coverage."""

    popular_count = max(1, min(ratings_per_user // 3, items))
    if ratings_per_user >= 4:
        popular_count = max(2, popular_count)
    popular_count = min(popular_count, ratings_per_user)
    popular_items = list(range(1, popular_count + 1))

    item_sets: list[set[int]] = []
    coverage_cursor = popular_count + 1
    for user_index in range(users):
        selected = set(popular_items)

        # A shifted window keeps adjacent users sharing many items.
        shift = (user_index * max(1, ratings_per_user - popular_count)) % items
        for offset in range(items):
            if len(selected) >= ratings_per_user:
                break
            movie_id = ((shift + offset) % items) + 1
            selected.add(movie_id)

        # A global coverage cursor helps later users cover less popular items.
        attempts = 0
        while len(selected) < ratings_per_user and attempts < items * 2:
            movie_id = ((coverage_cursor - 1) % items) + 1
            coverage_cursor += 1
            attempts += 1
            selected.add(movie_id)

        if len(selected) != ratings_per_user:
            raise SyntheticRatingsError("internal generator error: could not create unique user item set.")
        item_sets.append(selected)

    _repair_item_coverage(item_sets, items, ratings_per_user)
    _add_seeded_variation(item_sets, items, ratings_per_user, rng)
    _repair_item_coverage(item_sets, items, ratings_per_user)
    return item_sets


def _item_counts(item_sets: Sequence[set[int]]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for selected in item_sets:
        for movie_id in selected:
            counts[movie_id] = counts.get(movie_id, 0) + 1
    return counts


def _repair_item_coverage(item_sets: list[set[int]], items: int, ratings_per_user: int) -> None:
    """Replace overrepresented items so every item appears when capacity allows."""

    if len(item_sets) * ratings_per_user < items:
        return

    counts = _item_counts(item_sets)
    missing_items = [movie_id for movie_id in range(1, items + 1) if counts.get(movie_id, 0) == 0]
    for missing_movie_id in missing_items:
        counts = _item_counts(item_sets)
        replacement: tuple[int, int] | None = None
        for user_index, selected in enumerate(item_sets):
            if missing_movie_id in selected:
                continue
            replaceable = sorted(
                (movie_id for movie_id in selected if counts.get(movie_id, 0) > 1),
                key=lambda movie_id: (-counts[movie_id], movie_id),
            )
            if replaceable:
                replacement = (user_index, replaceable[0])
                break
        if replacement is None:
            return

        user_index, old_movie_id = replacement
        item_sets[user_index].remove(old_movie_id)
        item_sets[user_index].add(missing_movie_id)


def _add_seeded_variation(
    item_sets: list[set[int]],
    items: int,
    ratings_per_user: int,
    rng: random.Random,
) -> None:
    """Make item selections seed-sensitive while preserving overlap and uniqueness."""

    if ratings_per_user >= items:
        return

    swap_attempts = max(1, len(item_sets) // 2)
    for _ in range(swap_attempts):
        user_index = rng.randrange(len(item_sets))
        selected = item_sets[user_index]
        if len(selected) != ratings_per_user:
            continue

        counts = _item_counts(item_sets)
        replaceable = [movie_id for movie_id in selected if counts.get(movie_id, 0) > 1]
        missing_for_user = [movie_id for movie_id in range(1, items + 1) if movie_id not in selected]
        if not replaceable or not missing_for_user:
            continue

        old_movie_id = rng.choice(sorted(replaceable))
        new_movie_id = rng.choice(sorted(missing_for_user))
        selected.remove(old_movie_id)
        selected.add(new_movie_id)


def generate_records(
    users: int,
    items: int,
    ratings_per_user: int,
    seed: int = DEFAULT_SEED,
    start_date: str = DEFAULT_START_DATE,
) -> list[tuple[int, int, int, str]]:
    """Generate deterministic normalized rating rows."""

    validate_generation_request(users, items, ratings_per_user, seed, start_date)
    start = parse_start_date(start_date)
    rng = random.Random(seed)
    item_sets = _choose_item_sets(users, items, ratings_per_user, rng)

    records: list[tuple[int, int, int, str]] = []
    for user_index, selected in enumerate(item_sets):
        user_id = user_index + 1
        ordered_items = sorted(selected)
        rng.shuffle(ordered_items)
        for rank, movie_id in enumerate(ordered_items):
            rating_rng = random.Random((seed + 1) * 1_000_003 + user_id * 9_176 + movie_id * 131)
            rating = rating_rng.randint(1, 5)
            date = start + dt.timedelta(days=user_index * ratings_per_user + rank)
            records.append((user_id, movie_id, rating, date.isoformat()))

    records.sort(key=lambda row: (row[0], row[3], row[1]))
    return records


def records_to_csv_bytes(records: Sequence[tuple[int, int, int, str]]) -> bytes:
    """Serialize records to normalized CSV bytes with stable newlines."""

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(RATINGS_HEADER)
    writer.writerows(records)
    return buffer.getvalue().encode("utf-8")


def build_statistics(
    records: Sequence[tuple[int, int, int, str]],
    users: int,
    items: int,
    ratings_per_user: int,
    seed: int,
    csv_bytes: bytes,
) -> dict[str, object]:
    """Build machine-readable statistics for the generated dataset."""

    ratings_by_user: dict[int, int] = {}
    users_by_item: dict[int, set[int]] = {}
    dates: list[str] = []
    for user_id, movie_id, _rating, date in records:
        ratings_by_user[user_id] = ratings_by_user.get(user_id, 0) + 1
        users_by_item.setdefault(movie_id, set()).add(user_id)
        dates.append(date)

    user_counts = list(ratings_by_user.values())
    item_counts = [len(user_ids) for user_ids in users_by_item.values()]
    return {
        "dataset_type": DATASET_TYPE,
        "seed": seed,
        "users_requested": users,
        "items_requested": items,
        "ratings_per_user": ratings_per_user,
        "output_rows": len(records),
        "distinct_users": len(ratings_by_user),
        "distinct_items": len(users_by_item),
        "minimum_ratings_per_user": min(user_counts),
        "maximum_ratings_per_user": max(user_counts),
        "average_ratings_per_user": sum(user_counts) / len(user_counts),
        "minimum_users_per_item": min(item_counts),
        "maximum_users_per_item": max(item_counts),
        "average_users_per_item": sum(item_counts) / len(item_counts),
        "start_date": min(dates),
        "end_date": max(dates),
        "sha256": hashlib.sha256(csv_bytes).hexdigest(),
    }


def write_outputs(csv_bytes: bytes, stats: Mapping[str, object], output_path: Path, stats_output_path: Path) -> None:
    """Write generated CSV and statistics JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    stats_output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(csv_bytes)
    stats_output_path.write_text(
        json.dumps(dict(stats), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def run_generation(
    users: int,
    items: int,
    ratings_per_user: int,
    output_path: Path | str,
    stats_output_path: Path | str,
    seed: int = DEFAULT_SEED,
    start_date: str = DEFAULT_START_DATE,
) -> dict[str, object]:
    """Run the full generation workflow and return statistics."""

    records = generate_records(users, items, ratings_per_user, seed, start_date)
    csv_bytes = records_to_csv_bytes(records)
    stats = build_statistics(records, users, items, ratings_per_user, seed, csv_bytes)
    write_outputs(csv_bytes, stats, Path(output_path), Path(stats_output_path))
    return stats


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate deterministic synthetic normalized ratings for scalability experiments.",
    )
    parser.add_argument("--users", type=_positive_int, required=True)
    parser.add_argument("--items", type=_positive_int, required=True)
    parser.add_argument("--ratings-per-user", type=_positive_int, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stats-output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        stats = run_generation(
            users=args.users,
            items=args.items,
            ratings_per_user=args.ratings_per_user,
            seed=args.seed,
            start_date=args.start_date,
            output_path=args.output,
            stats_output_path=args.stats_output,
        )
    except (SyntheticRatingsError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(
        "Synthetic ratings generated: "
        f"{stats['output_rows']} rows, "
        f"{stats['distinct_users']} users, "
        f"{stats['distinct_items']} items, "
        f"sha256={stats['sha256']}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
