import csv
import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.run_scalability_experiments import (
    BENCHMARK_RESULTS_HEADER,
    BenchmarkError,
    build_stage_command,
    collect_environment_metadata,
    collect_runs_with_failure_policy,
    command_uses_test_data,
    count_recommendation_items,
    count_text_part_rows,
    create_user_preserving_subset,
    deterministic_experiment_id,
    is_completed_manifest,
    validate_external_normalized_input,
    validate_safe_output_dir,
    write_benchmark_json,
    write_json,
    write_results_csv,
    stage_order,
)


class RunScalabilityExperimentsTests(unittest.TestCase):
    def sample_experiment(self) -> dict[str, object]:
        return {
            "users": 10,
            "items": 12,
            "ratings_per_user": 3,
            "method": "cosine",
            "min_common_users": 1,
            "top_l": 10,
            "top_k": 5,
            "relevance_threshold": 4,
            "reducers": 1,
            "repetitions": 1,
        }

    def sample_paths(self, root: Path) -> dict[str, Path]:
        return {
            "train_csv": root / "split" / "train.csv",
            "test_csv": root / "split" / "test.csv",
            "user_history_dir": root / "stages" / "user-history",
            "pair_stats_dir": root / "stages" / "pair-statistics",
            "similarity_dir": root / "stages" / "similarity",
            "raw_predictions_dir": root / "stages" / "raw-predictions",
            "top_k_dir": root / "stages" / "top-k",
        }

    def test_deterministic_experiment_id(self) -> None:
        experiment = self.sample_experiment()
        self.assertEqual(
            deterministic_experiment_id(experiment, "profile"),
            "profile-cosine-30-ratings-mcu1-tl10-tk5",
        )
        experiment["id"] = "custom-id"
        self.assertEqual(deterministic_experiment_id(experiment, "profile"), "custom-id")

    def test_correct_stage_order(self) -> None:
        self.assertEqual(
            stage_order(),
            [
                "dataset_generation",
                "split",
                "user_history",
                "pair_statistics",
                "similarity",
                "scoring",
                "top_k",
                "evaluation",
            ],
        )

    def test_test_data_is_not_supplied_to_model_building_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.sample_paths(root)
            experiment = self.sample_experiment()
            for stage in ["user_history", "pair_statistics", "similarity", "scoring", "top_k"]:
                command = build_stage_command(stage, "classes:deps", experiment, paths)
                self.assertFalse(command_uses_test_data(command, paths["test_csv"]))

    def test_safe_output_directory_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            output = repo / "target" / "scalability-benchmark"
            repo.mkdir()
            self.assertEqual(validate_safe_output_dir(output, repo), output.resolve())

    def test_reject_unsafe_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "src").mkdir(parents=True)
            with self.assertRaisesRegex(BenchmarkError, "repository root"):
                validate_safe_output_dir(repo, repo)
            with self.assertRaisesRegex(BenchmarkError, "protected"):
                validate_safe_output_dir(repo / "src" / "out", repo)

    def test_resume_only_completed_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "run_manifest.json"
            write_json({"status": "completed"}, manifest)
            self.assertTrue(is_completed_manifest(manifest))

    def test_incomplete_run_is_not_treated_as_completed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "run_manifest.json"
            write_json({"status": "running"}, manifest)
            self.assertFalse(is_completed_manifest(manifest))

    def test_continue_after_failure_when_fail_fast_disabled(self) -> None:
        experiments = [
            {"id": "a", "repetitions": 1},
            {"id": "b", "repetitions": 1},
        ]

        def run_one(experiment: dict[str, object], repetition: int) -> dict[str, object]:
            return {"experimentId": experiment["id"], "repetition": repetition, "status": "failed"}

        records = collect_runs_with_failure_policy(experiments, run_one, fail_fast=False)
        self.assertEqual([record["experimentId"] for record in records], ["a", "b"])

    def test_stop_after_failure_when_fail_fast_enabled(self) -> None:
        experiments = [
            {"id": "a", "repetitions": 1},
            {"id": "b", "repetitions": 1},
        ]

        def run_one(experiment: dict[str, object], repetition: int) -> dict[str, object]:
            return {"experimentId": experiment["id"], "repetition": repetition, "status": "failed"}

        records = collect_runs_with_failure_policy(experiments, run_one, fail_fast=True)
        self.assertEqual([record["experimentId"] for record in records], ["a"])

    def test_correct_csv_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "benchmark_results.csv"
            write_results_csv([], path)
            with path.open("r", encoding="utf-8", newline="") as input_file:
                self.assertEqual(next(csv.reader(input_file)), BENCHMARK_RESULTS_HEADER)

    def test_json_contains_no_nan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = {column: "" for column in BENCHMARK_RESULTS_HEADER}
            record["status"] = "completed"
            write_benchmark_json([record], {"name": "smoke"}, {"python_version": "3"}, root)
            text = (root / "benchmark_results.json").read_text(encoding="utf-8")
            self.assertNotIn("NaN", text)
            self.assertNotIn("Infinity", text)
            self.assertEqual(json.loads(text)["successful_run_count"], 1)

    def test_count_rows_across_multiple_part_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "part-r-00000").write_text("a\nb\n", encoding="utf-8")
            (root / "part-r-00001").write_text("c\n", encoding="utf-8")
            self.assertEqual(count_text_part_rows(root), 3)

    def test_ignore_success_and_hidden_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "part-r-00000").write_text("a\n", encoding="utf-8")
            (root / "_SUCCESS").write_text("", encoding="utf-8")
            (root / ".part-r-00001.crc").write_text("ignored\n", encoding="utf-8")
            self.assertEqual(count_text_part_rows(root), 1)

    def test_count_recommendation_items_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "part-r-00000").write_text(
                "101\t1:4.0,2:3.0\n102\t3:5.0\n",
                encoding="utf-8",
            )
            self.assertEqual(count_recommendation_items(root), 3)

    def test_external_normalized_input_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ratings.csv"
            path.write_text(
                "userId,movieId,rating,date\n1,1,5,2005-01-01\n1,2,4,2005-01-02\n",
                encoding="utf-8",
            )
            stats = validate_external_normalized_input(path)
            self.assertEqual(stats["dataset_type"], "external-normalized")
            self.assertEqual(stats["output_rows"], 2)

    def test_user_preserving_subset_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "ratings.csv"
            source.write_text(
                "userId,movieId,rating,date\n"
                "1,1,5,2005-01-01\n"
                "1,2,4,2005-01-02\n"
                "2,1,3,2005-01-01\n"
                "2,3,5,2005-01-02\n",
                encoding="utf-8",
            )
            output = root / "subset.csv"
            stats = create_user_preserving_subset(source, output, target_rows=3)
            rows = output.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 5)
            self.assertEqual(stats["output_rows"], 4)

    def test_environment_metadata_excludes_secrets_and_home_paths(self) -> None:
        os.environ["VERY_SECRET_TOKEN"] = "do-not-record"
        metadata = collect_environment_metadata(Path("."))
        text = json.dumps(metadata, sort_keys=True)
        self.assertNotIn("VERY_SECRET_TOKEN", text)
        self.assertNotIn("do-not-record", text)


if __name__ == "__main__":
    unittest.main()
