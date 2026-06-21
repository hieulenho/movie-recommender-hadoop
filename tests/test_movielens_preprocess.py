import csv
import tempfile
import unittest
from pathlib import Path

from scripts import preprocess_movielens_1m as prep


class MovieLensPreprocessTests(unittest.TestCase):
    def write_dataset(self, root: Path, ratings: str | None = None, movies: str | None = None, users: str | None = None) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        (root / "ratings.dat").write_text(
            ratings
            if ratings is not None
            else "1::1193::5::978300760\n1::661::3::978302109\n2::1193::4::978300001\n",
            encoding="latin-1",
        )
        (root / "movies.dat").write_text(
            movies
            if movies is not None
            else "1193::One Flew Over the Cuckoo's Nest (1975)::Drama\n661::James and the Giant Peach (1996)::Animation|Children's|Musical\n",
            encoding="latin-1",
        )
        (root / "users.dat").write_text(users if users is not None else "1::F::1::10::48067\n2::M::56::16::70072\n", encoding="latin-1")
        (root / "README").write_text("MovieLens 1M fixture\n", encoding="latin-1")
        return root

    def test_parse_valid_ratings_row(self) -> None:
        row = prep.parse_rating_row("1::1193::5::978300760", 1)
        self.assertEqual((row.user_id, row.movie_id, row.rating, row.timestamp), (1, 1193, 5, 978300760))

    def test_reject_wrong_field_count(self) -> None:
        with self.assertRaisesRegex(prep.MovieLensPreprocessError, "expected"):
            prep.parse_rating_row("1::1193::5", 1)

    def test_reject_invalid_user_id(self) -> None:
        with self.assertRaisesRegex(prep.MovieLensPreprocessError, "UserID"):
            prep.parse_rating_row("0::1193::5::978300760", 1)

    def test_reject_invalid_movie_id(self) -> None:
        with self.assertRaisesRegex(prep.MovieLensPreprocessError, "MovieID"):
            prep.parse_rating_row("1::0::5::978300760", 1)

    def test_reject_rating_below_one(self) -> None:
        with self.assertRaisesRegex(prep.MovieLensPreprocessError, "Rating"):
            prep.parse_rating_row("1::1193::0::978300760", 1)

    def test_reject_rating_above_five(self) -> None:
        with self.assertRaisesRegex(prep.MovieLensPreprocessError, "Rating"):
            prep.parse_rating_row("1::1193::6::978300760", 1)

    def test_reject_non_integer_rating(self) -> None:
        with self.assertRaisesRegex(prep.MovieLensPreprocessError, "Rating"):
            prep.parse_rating_row("1::1193::4.5::978300760", 1)

    def test_reject_invalid_timestamp(self) -> None:
        with self.assertRaisesRegex(prep.MovieLensPreprocessError, "Timestamp"):
            prep.parse_rating_row("1::1193::5::abc", 1)

    def test_timestamp_conversion_uses_utc(self) -> None:
        self.assertEqual(prep.timestamp_to_utc_text(978300760), "2000-12-31T22:12:40Z")

    def test_exact_duplicate_handling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ratings.dat"
            path.write_text("1::1::5::978300760\n1::1::5::978300760\n", encoding="latin-1")
            records, stats = prep.load_ratings(path)
            self.assertEqual(len(records), 1)
            self.assertEqual(stats["exact_duplicates_ignored"], 1)

    def test_conflicting_duplicate_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ratings.dat"
            path.write_text("1::1::5::978300760\n1::1::4::978300760\n", encoding="latin-1")
            with self.assertRaisesRegex(prep.MovieLensPreprocessError, "conflicting duplicate"):
                prep.load_ratings(path)

    def test_deterministic_normalized_ordering_and_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = self.write_dataset(
                root / "ml-1m",
                ratings="1::2::4::978300800\n1::1::5::978300760\n2::1::3::978300700\n",
                movies="1::Movie A (2000)::Drama\n2::Movie B (2001)::Comedy\n",
            )
            out = root / "out"
            prep.preprocess_movielens_1m(dataset, out)
            lines = (out / "ratings_with_timestamp.csv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "userId,movieId,rating,timestamp,dateTimeUtc,date")
            self.assertTrue(lines[1].startswith("1,1,5,978300760"))
            self.assertEqual((out / "movie_metadata.csv").read_text(encoding="utf-8").splitlines()[0], "movieId,title,year,genres")

    def test_validating_users_dat(self) -> None:
        user = prep.parse_user_row("1::F::1::10::48067", 1)
        self.assertEqual((user.user_id, user.gender, user.age, user.occupation, user.zip_code), (1, "F", 1, 10, "48067"))
        with self.assertRaisesRegex(prep.MovieLensPreprocessError, "Gender"):
            prep.parse_user_row("1::X::1::10::48067", 1)
        # occupation code 0 = "other or not specified" -- must be accepted
        user0 = prep.parse_user_row("2::M::25::0::10001", 2)
        self.assertEqual(user0.occupation, 0)

    def test_parsing_movies_title_colons_year_and_genres(self) -> None:
        movie = prep.parse_movie_row("1::Star Wars: Episode IV - A New Hope (1977)::Action|Adventure|Sci-Fi", 1)
        self.assertEqual(movie.title, "Star Wars: Episode IV - A New Hope")
        self.assertEqual(movie.year, 1977)
        self.assertEqual(movie.genres, "Action|Adventure|Sci-Fi")

    def test_reject_duplicate_metadata_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "movies.dat"
            path.write_text("1::A (2000)::Drama\n1::B (2001)::Comedy\n", encoding="latin-1")
            with self.assertRaisesRegex(prep.MovieLensPreprocessError, "duplicate"):
                prep.load_movies(path)

    def test_dataset_statistics_consistency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = self.write_dataset(root / "ml-1m")
            out = root / "out"
            stats = prep.preprocess_movielens_1m(dataset, out)
            self.assertEqual(stats["dataset_name"], "MovieLens 1M")
            self.assertEqual(stats["dataset_role"], "primary-experimental")
            self.assertEqual(stats["rating_rows"], 3)
            self.assertEqual(stats["distinct_users"], 2)
            self.assertEqual(stats["metadata_coverage"], 1.0)
            with (out / "movie_metadata.csv").open("r", encoding="utf-8", newline="") as input_file:
                rows = list(csv.DictReader(input_file))
            by_movie = {row["movieId"]: row for row in rows}
            self.assertEqual(by_movie["1193"]["genres"], "Drama")


if __name__ == "__main__":
    unittest.main()
