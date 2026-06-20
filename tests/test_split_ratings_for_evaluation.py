import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.split_ratings_for_evaluation import (
    RATINGS_HEADER,
    SplitRatingsError,
    load_normalized_ratings,
    run_split,
    split_leave_one_out,
)


FIXTURE_DIR = Path("tests/fixtures/evaluation")
SPLIT_INPUT = FIXTURE_DIR / "split-input.csv"
EXPECTED_TRAIN = FIXTURE_DIR / "expected-train.csv"
EXPECTED_TEST = FIXTURE_DIR / "expected-test.csv"


class SplitRatingsForEvaluationTests(unittest.TestCase):
    def write_csv(self, root: Path, content: str) -> Path:
        path = root / "ratings.csv"
        path.write_text(content, encoding="utf-8")
        return path

    def run_fixture_split(self, root: Path):
        train = root / "out" / "train.csv"
        test = root / "out" / "test.csv"
        stats = root / "out" / "stats.json"
        run_stats = run_split(SPLIT_INPUT, train, test, stats)
        return train, test, stats, run_stats

    def test_valid_leave_one_out_split(self) -> None:
        result = split_leave_one_out(load_normalized_ratings(SPLIT_INPUT))
        self.assertEqual(len(result.train_records), 5)
        self.assertEqual(len(result.test_records), 3)

    def test_exact_output_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            train, test, _stats, _run_stats = self.run_fixture_split(Path(tmp))
            for path in (train, test):
                with path.open("r", encoding="utf-8", newline="") as input_file:
                    self.assertEqual(next(csv.reader(input_file)), RATINGS_HEADER)

    def test_latest_date_held_out(self) -> None:
        result = split_leave_one_out(load_normalized_ratings(SPLIT_INPUT))
        held_out_by_user = {record.user_id: record.movie_id for record in result.test_records}
        self.assertEqual(held_out_by_user[202], 4)

    def test_movie_id_tie_breaking_for_equal_dates(self) -> None:
        result = split_leave_one_out(load_normalized_ratings(SPLIT_INPUT))
        held_out_by_user = {record.user_id: record.movie_id for record in result.test_records}
        self.assertEqual(held_out_by_user[201], 3)

    def test_user_with_one_rating_remains_train_only(self) -> None:
        result = split_leave_one_out(load_normalized_ratings(SPLIT_INPUT))
        train_user_203 = [record for record in result.train_records if record.user_id == 203]
        test_user_203 = [record for record in result.test_records if record.user_id == 203]
        self.assertEqual(len(train_user_203), 1)
        self.assertEqual(test_user_203, [])

    def test_at_most_one_test_rating_per_user(self) -> None:
        result = split_leave_one_out(load_normalized_ratings(SPLIT_INPUT))
        counts: dict[int, int] = {}
        for record in result.test_records:
            counts[record.user_id] = counts.get(record.user_id, 0) + 1
        self.assertTrue(all(count == 1 for count in counts.values()))

    def test_exact_duplicate_ignored(self) -> None:
        loaded = load_normalized_ratings(SPLIT_INPUT)
        self.assertEqual(loaded.exact_duplicate_rows_ignored, 1)
        self.assertEqual(loaded.accepted_ratings, 8)

    def test_conflicting_duplicate_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(
                Path(tmp),
                "userId,movieId,rating,date\n1,1,5,2005-01-01\n1,1,4,2005-01-01\n",
            )
            with self.assertRaisesRegex(SplitRatingsError, "conflicting duplicate"):
                load_normalized_ratings(path)

    def test_invalid_csv_header_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(Path(tmp), "user,movie,rating,date\n1,1,5,2005-01-01\n")
            with self.assertRaisesRegex(SplitRatingsError, "header"):
                load_normalized_ratings(path)

    def test_invalid_user_id_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(Path(tmp), "userId,movieId,rating,date\n0,1,5,2005-01-01\n")
            with self.assertRaisesRegex(SplitRatingsError, "userId"):
                load_normalized_ratings(path)

    def test_invalid_movie_id_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(Path(tmp), "userId,movieId,rating,date\n1,0,5,2005-01-01\n")
            with self.assertRaisesRegex(SplitRatingsError, "movieId"):
                load_normalized_ratings(path)

    def test_invalid_rating_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(Path(tmp), "userId,movieId,rating,date\n1,1,6,2005-01-01\n")
            with self.assertRaisesRegex(SplitRatingsError, "rating"):
                load_normalized_ratings(path)

    def test_invalid_date_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(Path(tmp), "userId,movieId,rating,date\n1,1,5,2005-02-30\n")
            with self.assertRaisesRegex(SplitRatingsError, "date"):
                load_normalized_ratings(path)

    def test_empty_dataset_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(Path(tmp), "userId,movieId,rating,date\n")
            with self.assertRaisesRegex(SplitRatingsError, "no rating rows"):
                load_normalized_ratings(path)

    def test_deterministic_train_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            train, _test, _stats, _run_stats = self.run_fixture_split(Path(tmp))
            self.assertEqual(train.read_text(encoding="utf-8"), EXPECTED_TRAIN.read_text(encoding="utf-8"))

    def test_deterministic_test_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _train, test, _stats, _run_stats = self.run_fixture_split(Path(tmp))
            self.assertEqual(test.read_text(encoding="utf-8"), EXPECTED_TEST.read_text(encoding="utf-8"))

    def test_internally_consistent_split_statistics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _train, _test, stats_path, run_stats = self.run_fixture_split(Path(tmp))
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
            self.assertEqual(stats, run_stats)
            self.assertEqual(stats["train_rows"] + stats["test_rows"], stats["accepted_ratings"])
            self.assertEqual(stats["split_method"], "leave-one-out-by-time")
            self.assertEqual(stats["holdout_per_user"], 1)

    def test_parent_output_directories_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            train = root / "nested" / "train" / "train.csv"
            test = root / "nested" / "test" / "test.csv"
            stats = root / "nested" / "stats" / "split.json"
            run_split(SPLIT_INPUT, train, test, stats)
            self.assertTrue(train.is_file())
            self.assertTrue(test.is_file())
            self.assertTrue(stats.is_file())


if __name__ == "__main__":
    unittest.main()
