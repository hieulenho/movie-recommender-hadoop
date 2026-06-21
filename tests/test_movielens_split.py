import csv
import tempfile
import unittest
from pathlib import Path

from scripts import split_movielens_1m as split


class MovieLensSplitTests(unittest.TestCase):
    def write_input(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(
                [
                    "userId,movieId,rating,timestamp,dateTimeUtc,date",
                    "1,10,5,978300760,2000-12-31T22:12:40Z,2000-12-31",
                    "1,20,4,978300800,2000-12-31T22:13:20Z,2000-12-31",
                    "1,30,3,978300800,2000-12-31T22:13:20Z,2000-12-31",
                    "2,10,4,978300700,2000-12-31T22:11:40Z,2000-12-31",
                    "2,40,5,978300900,2000-12-31T22:15:00Z,2000-12-31",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def test_latest_timestamp_is_held_out(self) -> None:
        records = split.load_timestamped_ratings(self.write_input(Path(tempfile.mkdtemp()) / "ratings.csv"))
        train, test, stats = split.split_leave_one_out_by_timestamp(records)
        held_out = {(row.user_id, row.movie_id) for row in test}
        self.assertEqual(held_out, {(1, 30), (2, 40)})
        self.assertEqual(stats["split_method"], "leave-one-out-by-exact-timestamp")

    def test_movie_id_is_used_only_for_timestamp_ties(self) -> None:
        records = [
            split.TimestampedRating(1, 99, 5, 100, "1970-01-01T00:01:40Z", "1970-01-01"),
            split.TimestampedRating(1, 1, 5, 200, "1970-01-01T00:03:20Z", "1970-01-01"),
            split.TimestampedRating(1, 2, 5, 200, "1970-01-01T00:03:20Z", "1970-01-01"),
        ]
        _train, test, _stats = split.split_leave_one_out_by_timestamp(records)
        self.assertEqual(test[0].movie_id, 2)

    def test_exactly_one_test_row_per_eligible_user_and_no_overlap(self) -> None:
        records = split.load_timestamped_ratings(self.write_input(Path(tempfile.mkdtemp()) / "ratings.csv"))
        train, test, stats = split.split_leave_one_out_by_timestamp(records)
        self.assertEqual(len(test), 2)
        self.assertEqual(stats["users_with_test_rating"], 2)
        self.assertEqual(stats["train_test_overlap_rows"], 0)
        self.assertFalse({(row.user_id, row.movie_id) for row in train} & {(row.user_id, row.movie_id) for row in test})

    def test_output_schemas_and_audit_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = self.write_input(root / "ratings.csv")
            stats = split.split_movielens_1m(input_path, root / "split")
            self.assertEqual(stats["input_ratings"], 5)
            self.assertEqual((root / "split" / "train_ratings.csv").read_text(encoding="utf-8").splitlines()[0], "userId,movieId,rating,date")
            self.assertEqual((root / "split" / "test_ratings_with_timestamp.csv").read_text(encoding="utf-8").splitlines()[0], "userId,movieId,rating,timestamp,dateTimeUtc,date")
            with (root / "split" / "test_ratings.csv").open("r", encoding="utf-8", newline="") as input_file:
                rows = list(csv.DictReader(input_file))
            self.assertEqual(rows[0].keys(), {"userId", "movieId", "rating", "date"})

    def test_reject_non_utc_timestamp_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ratings.csv"
            path.write_text(
                "userId,movieId,rating,timestamp,dateTimeUtc,date\n"
                "1,10,5,978300760,2000-12-31T00:00:00Z,2000-12-31\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(split.MovieLensSplitError, "dateTimeUtc"):
                split.load_timestamped_ratings(path)

    def test_deterministic_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = self.write_input(root / "ratings.csv")
            split.split_movielens_1m(input_path, root / "a")
            split.split_movielens_1m(input_path, root / "b")
            self.assertEqual((root / "a" / "test_ratings.csv").read_text(), (root / "b" / "test_ratings.csv").read_text())


if __name__ == "__main__":
    unittest.main()
