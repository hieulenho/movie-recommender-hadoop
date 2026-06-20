import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_synthetic_ratings import (
    RATINGS_HEADER,
    SyntheticRatingsError,
    generate_records,
    records_to_csv_bytes,
    run_generation,
)


class GenerateSyntheticRatingsTests(unittest.TestCase):
    def test_exact_normalized_csv_header(self) -> None:
        rows = records_to_csv_bytes(generate_records(3, 5, 2, seed=7)).decode("utf-8").splitlines()
        self.assertEqual(rows[0].split(","), RATINGS_HEADER)

    def test_exact_requested_row_count(self) -> None:
        records = generate_records(4, 7, 3, seed=7)
        self.assertEqual(len(records), 12)

    def test_correct_user_count(self) -> None:
        records = generate_records(5, 8, 3, seed=7)
        self.assertEqual(len({row[0] for row in records}), 5)

    def test_ratings_within_one_through_five(self) -> None:
        records = generate_records(5, 8, 3, seed=7)
        self.assertTrue(all(1 <= row[2] <= 5 for row in records))

    def test_positive_user_and_movie_ids(self) -> None:
        records = generate_records(5, 8, 3, seed=7)
        self.assertTrue(all(row[0] > 0 and row[1] > 0 for row in records))

    def test_no_duplicate_user_movie_pair(self) -> None:
        records = generate_records(6, 9, 4, seed=7)
        pairs = {(row[0], row[1]) for row in records}
        self.assertEqual(len(records), len(pairs))

    def test_valid_dates(self) -> None:
        records = generate_records(4, 7, 3, seed=7)
        for _user, _movie, _rating, date_text in records:
            self.assertEqual(dt.date.fromisoformat(date_text).isoformat(), date_text)

    def test_deterministic_output_for_same_seed(self) -> None:
        first = records_to_csv_bytes(generate_records(8, 12, 4, seed=99))
        second = records_to_csv_bytes(generate_records(8, 12, 4, seed=99))
        self.assertEqual(first, second)

    def test_different_output_for_different_seed(self) -> None:
        first = records_to_csv_bytes(generate_records(8, 12, 4, seed=99))
        second = records_to_csv_bytes(generate_records(8, 12, 4, seed=100))
        self.assertNotEqual(first, second)

    def test_identical_sha256_for_equivalent_repeated_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = run_generation(5, 8, 3, root / "a" / "ratings.csv", root / "a" / "stats.json", seed=11)
            second = run_generation(5, 8, 3, root / "b" / "ratings.csv", root / "b" / "stats.json", seed=11)
            self.assertEqual(first["sha256"], second["sha256"])

    def test_reject_users_below_two(self) -> None:
        with self.assertRaisesRegex(SyntheticRatingsError, "users"):
            generate_records(1, 5, 2)

    def test_reject_items_below_three(self) -> None:
        with self.assertRaisesRegex(SyntheticRatingsError, "items"):
            generate_records(2, 2, 2)

    def test_reject_ratings_per_user_below_two(self) -> None:
        with self.assertRaisesRegex(SyntheticRatingsError, "ratings-per-user"):
            generate_records(2, 3, 1)

    def test_reject_ratings_per_user_above_items(self) -> None:
        with self.assertRaisesRegex(SyntheticRatingsError, "ratings-per-user"):
            generate_records(2, 3, 4)

    def test_parent_directories_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "nested" / "data" / "ratings.csv"
            stats = root / "nested" / "stats" / "stats.json"
            run_generation(3, 5, 2, output, stats)
            self.assertTrue(output.is_file())
            self.assertTrue(stats.is_file())

    def test_statistics_internally_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stats_path = root / "stats.json"
            stats = run_generation(6, 9, 4, root / "ratings.csv", stats_path, seed=12)
            loaded = json.loads(stats_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded, stats)
            self.assertEqual(stats["output_rows"], 24)
            self.assertEqual(stats["distinct_users"], 6)
            self.assertEqual(stats["dataset_type"], "synthetic")
            self.assertNotIn("NaN", stats_path.read_text(encoding="utf-8"))

    def test_sufficient_item_overlap_for_small_fixture(self) -> None:
        records = generate_records(6, 8, 4, seed=5)
        users_by_movie: dict[int, set[int]] = {}
        for user_id, movie_id, _rating, _date in records:
            users_by_movie.setdefault(movie_id, set()).add(user_id)
        self.assertGreaterEqual(max(len(users) for users in users_by_movie.values()), 2)
        self.assertEqual(len(users_by_movie), 8)

    def test_output_sorting_is_user_date_movie(self) -> None:
        records = generate_records(5, 7, 3, seed=5)
        self.assertEqual(records, sorted(records, key=lambda row: (row[0], row[3], row[1])))

    def test_csv_can_be_read_by_csv_module(self) -> None:
        rows = records_to_csv_bytes(generate_records(3, 5, 2, seed=7)).decode("utf-8")
        reader = csv.reader(rows.splitlines())
        self.assertEqual(next(reader), RATINGS_HEADER)


if __name__ == "__main__":
    unittest.main()
