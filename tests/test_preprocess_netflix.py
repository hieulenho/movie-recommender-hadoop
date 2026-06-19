import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.preprocess_netflix import (
    CSV_HEADER,
    PreprocessError,
    discover_input_files,
    parse_movie_header,
    parse_rating_row,
    preprocess_directory,
    run_preprocessing,
    write_normalized_csv,
)


class PreprocessNetflixTests(unittest.TestCase):
    def write_file(self, root: Path, relative_path: str, content: str) -> Path:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_parse_valid_movie_header(self) -> None:
        self.assertEqual(parse_movie_header("17:"), 17)

    def test_reject_movie_id_zero_or_negative(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid_movie_id"):
            parse_movie_header("0:")
        with self.assertRaisesRegex(ValueError, "invalid_movie_id"):
            parse_movie_header("-7:")

    def test_detect_malformed_movie_header_syntax(self) -> None:
        with self.assertRaisesRegex(ValueError, "malformed_movie_header"):
            parse_movie_header("abc:")

    def test_parse_valid_rating_row(self) -> None:
        self.assertEqual(
            parse_rating_row("1488844,3,2005-09-06", 1),
            (1488844, 1, 3, "2005-09-06"),
        )

    def test_reject_rating_outside_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid_rating"):
            parse_rating_row("1488844,6,2005-09-06", 1)

    def test_reject_non_integer_rating(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid_rating"):
            parse_rating_row("1488844,five,2005-09-06", 1)

    def test_reject_invalid_user_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid_user_id"):
            parse_rating_row("0,3,2005-09-06", 1)

    def test_reject_invalid_date(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid_date"):
            parse_rating_row("1488844,3,2005-02-30", 1)

    def test_reject_wrong_number_of_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "wrong_field_count"):
            parse_rating_row("1488844,3,2005-09-06,extra", 1)

    def test_reject_rating_before_movie_header(self) -> None:
        with self.assertRaisesRegex(ValueError, "rating_before_movie_header"):
            parse_rating_row("1488844,3,2005-09-06", None)

    def test_skip_blank_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_file(root, "mv_0000001.txt", "1:\n\n1488844,3,2005-09-06\n")
            records, stats = preprocess_directory(root)
            self.assertEqual(records, [(1488844, 1, 3, "2005-09-06")])
            self.assertEqual(stats["blank_lines"], 1)

    def test_process_one_file_with_one_movie_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_file(root, "mv_0000001.txt", "1:\n1488844,3,2005-09-06\n")
            records, stats = preprocess_directory(root)
            self.assertEqual(records, [(1488844, 1, 3, "2005-09-06")])
            self.assertEqual(stats["movie_headers"], 1)

    def test_process_one_file_with_multiple_movie_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_file(
                root,
                "mv_0000001.txt",
                "1:\n1488844,3,2005-09-06\n2:\n822109,5,2005-05-13\n",
            )
            records, stats = preprocess_directory(root)
            self.assertEqual(
                records,
                [(1488844, 1, 3, "2005-09-06"), (822109, 2, 5, "2005-05-13")],
            )
            self.assertEqual(stats["movie_headers"], 2)

    def test_process_multiple_files_in_deterministic_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_file(root, "mv_0000002.txt", "2:\n222,4,2005-01-02\n")
            self.write_file(root, "mv_0000001.txt", "1:\n111,5,2005-01-01\n")
            records, _stats = preprocess_directory(root)
            self.assertEqual(
                records,
                [(111, 1, 5, "2005-01-01"), (222, 2, 4, "2005-01-02")],
            )

    def test_ignore_unrelated_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_file(root, "notes.txt", "this should not be parsed\n")
            self.write_file(root, "mv_0000001.txt", "1:\n1488844,3,2005-09-06\n")
            files = discover_input_files(root)
            self.assertEqual([path.name for path in files], ["mv_0000001.txt"])

    def test_remove_exact_duplicate_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_file(
                root,
                "mv_0000001.txt",
                "1:\n1488844,3,2005-09-06\n1488844,3,2005-09-06\n",
            )
            records, stats = preprocess_directory(root)
            self.assertEqual(records, [(1488844, 1, 3, "2005-09-06")])
            self.assertEqual(stats["duplicate_rows_removed"], 1)

    def test_preserve_non_exact_duplicate_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_file(
                root,
                "mv_0000001.txt",
                "1:\n1488844,3,2005-09-06\n1488844,4,2005-09-06\n1488844,3,2005-09-07\n",
            )
            records, stats = preprocess_directory(root)
            self.assertEqual(len(records), 3)
            self.assertEqual(stats["duplicate_rows_removed"], 0)

    def test_create_exact_csv_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ratings.csv"
            write_normalized_csv([(1488844, 1, 3, "2005-09-06")], output)
            with output.open("r", encoding="utf-8", newline="") as csv_file:
                reader = csv.reader(csv_file)
                self.assertEqual(next(reader), CSV_HEADER)

    def test_produce_internally_consistent_json_statistics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_file(
                root,
                "mv_0000001.txt",
                "1:\n1488844,3,2005-09-06\n1488844,3,2005-09-06\nbad,row\n\n",
            )
            records, stats = preprocess_directory(root)
            self.assertEqual(stats["output_rows"], len(records))
            self.assertEqual(
                stats["output_rows"],
                stats["valid_rating_rows"] - stats["duplicate_rows_removed"],
            )
            self.assertEqual(
                stats["input_rating_rows"],
                stats["valid_rating_rows"] + stats["invalid_rating_rows"],
            )
            self.assertEqual(stats["invalid_reason_counts"]["wrong_field_count"], 1)

    def test_fail_when_input_directory_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"
            with self.assertRaisesRegex(PreprocessError, "does not exist"):
                discover_input_files(missing)

    def test_fail_when_no_matching_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_file(root, "readme.txt", "no data\n")
            with self.assertRaisesRegex(PreprocessError, "No mv_\\*.txt files"):
                discover_input_files(root)

    def test_repeated_runs_produce_equivalent_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            self.write_file(input_dir, "mv_0000001.txt", "1:\n1488844,3,2005-09-06\n")
            output = root / "out" / "ratings.csv"
            stats_output = root / "out" / "stats.json"

            run_preprocessing(input_dir, output, stats_output)
            first_csv = output.read_bytes()
            first_stats = json.loads(stats_output.read_text(encoding="utf-8"))

            run_preprocessing(input_dir, output, stats_output)
            second_csv = output.read_bytes()
            second_stats = json.loads(stats_output.read_text(encoding="utf-8"))

            self.assertEqual(first_csv, second_csv)
            self.assertEqual(first_stats, second_stats)

    def test_malformed_header_like_line_is_counted_and_does_not_set_movie(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_file(
                root,
                "mv_0000001.txt",
                "bad:\n1488844,3,2005-09-06\n1:\n1488844,3,2005-09-06\n",
            )
            records, stats = preprocess_directory(root)
            self.assertEqual(records, [(1488844, 1, 3, "2005-09-06")])
            self.assertEqual(stats["invalid_reason_counts"]["malformed_movie_header"], 1)
            self.assertEqual(stats["invalid_reason_counts"]["rating_before_movie_header"], 1)


if __name__ == "__main__":
    unittest.main()
