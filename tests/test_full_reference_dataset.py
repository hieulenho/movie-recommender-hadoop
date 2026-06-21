from __future__ import annotations

import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import full_reference_dataset as fullrun


FIXTURE_DIR = Path("tests/fixtures/full-reference-dataset")


class FullReferenceDatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.dataset = self.work / "github-reference"
        shutil.copytree(FIXTURE_DIR, self.dataset)
        self.rewrite_dataset_as_github_3col()

    def rewrite_dataset_as_github_3col(self) -> None:
        for movie_id in range(1, 16):
            rows = [
                f"101,{movie_id},{((movie_id + 3) % 5) + 1}",
                f"102,{movie_id},{((movie_id + 1) % 5) + 1}",
            ]
            if movie_id == 1:
                rows.append("101,1,5")
            (self.dataset / f"mv_{movie_id:07d}.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")

    def test_parse_valid_three_column_row(self) -> None:
        record = fullrun.parse_github_3col_rating_row("101,8,5", 8, "mv_0000008.txt", 1)
        self.assertEqual((record.user_id, record.movie_id, record.rating), (101, 8, 5))

    def test_reject_wrong_field_count(self) -> None:
        with self.assertRaisesRegex(fullrun.FullReferenceDatasetError, "expected exactly"):
            fullrun.parse_github_3col_rating_row("101,8,5,2005-01-01", 8, "mv_0000008.txt", 1)

    def test_reject_invalid_user_id(self) -> None:
        with self.assertRaisesRegex(fullrun.FullReferenceDatasetError, "userId"):
            fullrun.parse_github_3col_rating_row("0,8,5", 8, "mv_0000008.txt", 1)

    def test_reject_invalid_movie_id(self) -> None:
        with self.assertRaisesRegex(fullrun.FullReferenceDatasetError, "movieId"):
            fullrun.parse_github_3col_rating_row("101,0,5", 8, "mv_0000008.txt", 1)

    def test_reject_invalid_rating(self) -> None:
        with self.assertRaisesRegex(fullrun.FullReferenceDatasetError, "rating"):
            fullrun.parse_github_3col_rating_row("101,8,6", 8, "mv_0000008.txt", 1)

    def test_reject_row_movie_id_different_from_filename_id(self) -> None:
        with self.assertRaisesRegex(fullrun.FullReferenceDatasetError, "does not match expected"):
            fullrun.parse_github_3col_rating_row("101,7,5", 8, "mv_0000008.txt", 1)

    def test_expected_all_15_names_are_processed_in_numeric_order(self) -> None:
        validation = fullrun.validate_reference_dataset(self.dataset, fullrun.SOURCE_FORMAT_GITHUB_3COL)
        self.assertEqual(validation["source_format"], fullrun.SOURCE_FORMAT_GITHUB_3COL)
        self.assertEqual(validation["discovered_rating_file_count"], 15)
        self.assertEqual([path.name for path in validation["rating_files"]], fullrun.expected_rating_file_names())

    def test_github_format_does_not_expect_movie_id_colon_header(self) -> None:
        validation = fullrun.validate_reference_dataset(self.dataset, fullrun.SOURCE_FORMAT_GITHUB_3COL)
        self.assertEqual(validation["rating_file_stats"]["mv_0000001.txt"]["first_meaningful_line"], "101,1,5")

    def test_reject_missing_rating_file(self) -> None:
        (self.dataset / "mv_0000015.txt").unlink()
        with self.assertRaisesRegex(fullrun.FullReferenceDatasetError, "Missing expected"):
            fullrun.validate_reference_dataset(self.dataset, fullrun.SOURCE_FORMAT_GITHUB_3COL)

    def test_reject_extra_incorrectly_named_rating_file(self) -> None:
        (self.dataset / "mv_0000016.txt").write_text("101,16,5\n", encoding="utf-8")
        with self.assertRaisesRegex(fullrun.FullReferenceDatasetError, "Unexpected rating files"):
            fullrun.validate_reference_dataset(self.dataset, fullrun.SOURCE_FORMAT_GITHUB_3COL)

    def test_reject_empty_rating_file(self) -> None:
        (self.dataset / "mv_0000003.txt").write_text("", encoding="utf-8")
        with self.assertRaisesRegex(fullrun.FullReferenceDatasetError, "empty"):
            fullrun.validate_reference_dataset(self.dataset, fullrun.SOURCE_FORMAT_GITHUB_3COL)

    def test_reject_conflicting_duplicate_rating(self) -> None:
        (self.dataset / "mv_0000005.txt").write_text("101,5,5\n101,5,4\n", encoding="utf-8")
        with self.assertRaisesRegex(fullrun.FullReferenceDatasetError, "conflicting duplicate"):
            fullrun.validate_reference_dataset(self.dataset, fullrun.SOURCE_FORMAT_GITHUB_3COL)

    def test_normalize_records_uses_one_header_and_all_records(self) -> None:
        validation = fullrun.validate_reference_dataset(self.dataset, fullrun.SOURCE_FORMAT_GITHUB_3COL)
        output = self.work / "results" / "normalized" / "ratings.csv"
        stats_path = self.work / "results" / "normalized" / "dataset_stats.json"
        stats = fullrun.normalize_records(validation["rating_files"], output, stats_path, validation)

        lines = output.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "userId,movieId,rating,date")
        self.assertEqual(lines.count("userId,movieId,rating,date"), 1)
        self.assertEqual(len(lines) - 1, 30)
        self.assertEqual(stats["processed_rating_file_count"], 15)
        self.assertEqual(stats["accepted_rating_rows"], 30)
        self.assertEqual(stats["exact_duplicates_ignored"], 1)
        self.assertEqual(stats["distinct_movies"], 15)
        self.assertFalse(stats["source_has_dates"])

    def test_deterministic_non_temporal_split_highest_movie_id_held_out(self) -> None:
        validation = fullrun.validate_reference_dataset(self.dataset, fullrun.SOURCE_FORMAT_GITHUB_3COL)
        load_result = fullrun.load_github_3col_records(validation["rating_files"], fullrun.EXPECTED_MOVIE_IDS)
        split = fullrun.split_undated_leave_one_out_by_item(load_result)
        held_out = {record.user_id: record.movie_id for record in split.test_records}
        self.assertEqual(held_out, {101: 15, 102: 15})
        self.assertEqual(split.stats["split_method"], "deterministic-leave-one-out-by-item")
        self.assertEqual(split.stats["tie_breaking_rule"], "Sort by movieId ascending; hold out the highest movieId.")

    def test_single_rating_users_remain_train_only(self) -> None:
        load_result = fullrun.UndatedLoadResult(
            records=[
                fullrun.UndatedRatingRecord(1, 1, 5),
                fullrun.UndatedRatingRecord(2, 1, 4),
                fullrun.UndatedRatingRecord(2, 2, 3),
            ],
            input_lines=3,
            nonblank_input_lines=3,
            blank_lines=0,
            exact_duplicates_ignored=0,
        )
        split = fullrun.split_undated_leave_one_out_by_item(load_result)
        self.assertIn(fullrun.UndatedRatingRecord(1, 1, 5), split.train_records)
        self.assertNotIn(1, {record.user_id for record in split.test_records})

    def test_placeholder_date_added_only_to_written_schema_after_split(self) -> None:
        output = self.work / "train.csv"
        fullrun.write_undated_records_with_placeholder([fullrun.UndatedRatingRecord(1, 2, 5)], output)
        with output.open("r", encoding="utf-8", newline="") as input_file:
            rows = list(csv.DictReader(input_file))
        self.assertEqual(rows[0]["date"], fullrun.SCHEMA_PLACEHOLDER_DATE)

    def test_manifest_identifies_dataset_as_undated(self) -> None:
        validation = fullrun.validate_reference_dataset(self.dataset, fullrun.SOURCE_FORMAT_GITHUB_3COL)
        output = self.work / "ratings.csv"
        stats_path = self.work / "stats.json"
        stats = fullrun.normalize_records(validation["rating_files"], output, stats_path, validation)
        split_stats = {
            "split_method": fullrun.SPLIT_METHOD_UNDATED,
            "tie_breaking_rule": fullrun.SPLIT_TIE_BREAKING_RULE_UNDATED,
            "schema_placeholder_date": fullrun.SCHEMA_PLACEHOLDER_DATE,
            "warning": fullrun.NO_TEMPORAL_WARNING,
            "train_rows": 28,
            "test_rows": 2,
        }
        manifest = fullrun.build_full_manifest(
            validation,
            stats,
            split_stats,
            [{"method": "cosine", "status": "completed", "metrics": {}, "paths": {}}],
            {"metadata_rows": 15},
            {"top_l": 10, "top_k": 5, "min_common_users": 1},
            Path.cwd(),
        )
        self.assertEqual(manifest["source_format"], fullrun.SOURCE_FORMAT_GITHUB_3COL)
        self.assertFalse(manifest["source_has_dates"])
        self.assertEqual(manifest["split_method"], fullrun.SPLIT_METHOD_UNDATED)

    def test_generated_manifest_paths_contain_no_absolute_host_path(self) -> None:
        validation = fullrun.validate_reference_dataset(self.dataset, fullrun.SOURCE_FORMAT_GITHUB_3COL)
        output = self.work / "ratings.csv"
        stats_path = self.work / "stats.json"
        stats = fullrun.normalize_records(validation["rating_files"], output, stats_path, validation)
        text = json.dumps(stats, sort_keys=True)
        self.assertNotIn(str(self.work), text)

    def test_parse_movie_titles_and_commas(self) -> None:
        metadata = self.work / "movie_metadata.csv"
        result = fullrun.convert_movie_titles(self.dataset / "movie_titles.txt", metadata)
        with metadata.open("r", encoding="utf-8", newline="") as input_file:
            rows = list(csv.DictReader(input_file))
        self.assertEqual(result["metadata_rows"], 15)
        self.assertEqual(rows[0].keys(), {"movieId", "title", "year"})
        self.assertEqual(rows[7]["title"], "Fixture Movie, With Comma")
        self.assertEqual(rows[7]["year"], "")

    def test_reject_duplicate_movie_ids_in_metadata(self) -> None:
        source = self.work / "duplicate_titles.txt"
        source.write_text("1,First\n1,Second\n", encoding="utf-8")
        with self.assertRaisesRegex(fullrun.FullReferenceDatasetError, "duplicate movieId"):
            fullrun.convert_movie_titles(source, self.work / "metadata.csv")

    def test_metadata_header_is_exact(self) -> None:
        metadata = self.work / "movie_metadata.csv"
        fullrun.convert_movie_titles(self.dataset / "movie_titles.txt", metadata)
        self.assertEqual(metadata.read_text(encoding="utf-8").splitlines()[0], "movieId,title,year")

    def test_build_full_run_command_order(self) -> None:
        paths = fullrun.build_paths(self.work / "results")
        specific = fullrun.method_paths(paths["output_dir"], "cosine")
        commands = fullrun.build_stage_commands(
            "cosine",
            "classes:deps",
            paths,
            specific,
            {"reducers": 1, "min_common_users": 1, "top_l": 10, "top_k": 5, "relevance_threshold": 4},
        )
        self.assertEqual([stage for stage, _command in commands], ["user_history", "pair_statistics", "similarity", "scoring", "top_k"])

    def test_model_building_commands_do_not_use_test_input(self) -> None:
        paths = fullrun.build_paths(self.work / "results")
        specific = fullrun.method_paths(paths["output_dir"], "cooccurrence")
        commands = fullrun.build_stage_commands(
            "cooccurrence",
            "classes:deps",
            paths,
            specific,
            {"reducers": 1, "min_common_users": 1, "top_l": 10, "top_k": 5, "relevance_threshold": 4},
        )
        self.assertFalse(any(fullrun.command_uses_test_input(command, paths["test_csv"]) for _stage, command in commands))

    def test_create_method_comparison_output(self) -> None:
        dataset_stats = {"accepted_rating_rows": 30, "distinct_users": 2, "distinct_movies": 15}
        split_stats = {"train_rows": 28, "test_rows": 2}
        rows = fullrun.build_method_comparison_rows(
            [
                {
                    "method": "cosine",
                    "status": "completed",
                    "metrics": {"prediction_coverage": 0.5, "mae": None},
                    "stage_seconds": {"user_history": 1.0, "evaluation": 0.25},
                    "total_pipeline_seconds": 4.5,
                }
            ],
            dataset_stats,
            split_stats,
            {"top_l": 10, "top_k": 5, "min_common_users": 1},
        )
        output = self.work / "method_comparison.csv"
        fullrun.write_method_comparison(rows, output)
        text = output.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(",".join(fullrun.METHOD_COMPARISON_HEADER)))
        self.assertIn("cosine,30,2,15,28,2,10,5,1,0.5000000000,", text)


if __name__ == "__main__":
    unittest.main()
