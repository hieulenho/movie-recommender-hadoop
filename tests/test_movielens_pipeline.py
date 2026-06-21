import json
import math
import tempfile
import unittest
from pathlib import Path

from scripts import movielens_1m_pipeline as pipe


class MovieLensPipelineTests(unittest.TestCase):
    def write(self, path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_correct_stage_order(self) -> None:
        self.assertEqual(pipe.STAGE_ORDER[0:4], ("preprocess", "split", "user_history", "pair_statistics"))
        self.assertLess(pipe.STAGE_ORDER.index("cosine_evaluation"), pipe.STAGE_ORDER.index("cooccurrence_similarity"))

    def test_model_commands_do_not_use_test_input_and_pair_statistics_shared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = pipe.build_paths(root / "results" / "movielens-1m")
            params = {"reducers": 4, "min_common_users": 5, "top_l": 50, "top_k": 10, "relevance_threshold": 4}
            common = pipe.common_stage_commands("classes:deps", paths, params)
            self.assertEqual([stage for stage, *_rest in common], ["user_history", "pair_statistics"])
            for method in pipe.METHODS:
                specific = pipe.method_paths(paths["output_dir"], method)
                commands = pipe.method_stage_commands(method, "classes:deps", paths, specific, params)
                self.assertEqual([stage for stage, *_rest in commands], [f"{method}_similarity", f"{method}_scoring", f"{method}_top_k"])
                self.assertFalse(any(pipe.command_uses_test_input(command, paths["test_csv"]) for _stage, command, _inputs, _outputs in commands))
                self.assertIn(str(paths["pair_statistics_dir"]), commands[0][1])

    def test_multiple_part_files_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root / "part-r-00001", "2\t2:4\n")
            self.write(root / "part-r-00000", "1\t1:5\n")
            self.write(root / "_SUCCESS", "")
            self.write(root / ".part-r-00002.crc", "ignored")
            self.assertEqual([path.name for path in pipe.iter_part_files(root)], ["part-r-00000", "part-r-00001"])
            self.assertEqual(pipe.count_output_rows(root), 2)

    def test_resume_requires_matching_parameters_and_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            paths = pipe.build_paths(repo / "results" / "movielens-1m")
            paths["stage_manifest_dir"].mkdir(parents=True)
            input_file = self.write(repo / "input.csv", "x\n")
            output_dir = repo / "results" / "movielens-1m" / "out"
            self.write(output_dir / "part-r-00000", "1\t1:5\n")
            pipe.write_stage_manifest(paths, "stage", "completed", [input_file], [output_dir], {"p": 1}, 1.0, 2.0, 0, repo)
            self.assertTrue(pipe.manifest_matches(pipe.stage_manifest_path(paths, "stage"), [input_file], [output_dir], {"p": 1}, repo))
            self.assertFalse(pipe.manifest_matches(pipe.stage_manifest_path(paths, "stage"), [input_file], [output_dir], {"p": 2}, repo))

    def test_incomplete_manifests_are_not_resumed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            paths = pipe.build_paths(repo / "results" / "movielens-1m")
            paths["stage_manifest_dir"].mkdir(parents=True)
            input_file = self.write(repo / "input.csv", "x\n")
            output_dir = repo / "results" / "movielens-1m" / "out"
            self.write(output_dir / "part-r-00000", "1\n")
            pipe.write_stage_manifest(paths, "stage", "failed", [input_file], [output_dir], {}, 1.0, 2.0, 1, repo)
            self.assertFalse(pipe.manifest_matches(pipe.stage_manifest_path(paths, "stage"), [input_file], [output_dir], {}, repo))

    def test_force_stage_reruns_dependent_downstream_stages(self) -> None:
        forced = pipe.dependent_forced_stages("pair_statistics")
        self.assertIn("pair_statistics", forced)
        self.assertIn("cosine_similarity", forced)
        self.assertIn("cooccurrence_evaluation", forced)
        self.assertNotIn("user_history", forced)

    def test_raw_dataset_is_never_deleted_by_output_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            raw = self.write(repo / "data" / "raw" / "movielens-1m" / "ml-1m" / "ratings.dat", "raw\n")
            pipe.clean_outputs([raw], repo)
            self.assertTrue(raw.is_file())

    def test_unsafe_output_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            with self.assertRaisesRegex(pipe.MovieLensPipelineError, "under results"):
                pipe.ensure_results_output_path(repo / "data" / "bad", repo)

    def test_preflight_pair_estimate_is_correct(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            train = self.write(
                root / "train.csv",
                "userId,movieId,rating,date\n1,1,5,2000-01-01\n1,2,4,2000-01-01\n1,3,3,2000-01-01\n2,1,5,2000-01-01\n2,2,4,2000-01-01\n",
            )
            self.assertEqual(pipe.estimate_pair_contributions(train), 4)

    def test_generated_json_contains_no_nan_and_no_absolute_paths(self) -> None:
        rows = pipe.build_method_comparison_rows(
            {
                "common": {"user_history_seconds": 1.0, "pair_statistics_seconds": 2.0},
                "cosine": {"status": "completed", "stage_seconds": {"similarity": 1.0}, "metrics": {"mae": math.nan}},
                "cooccurrence": {"status": "completed", "stage_seconds": {}, "metrics": {}},
            },
            {"rating_rows": 10, "distinct_users": 2, "distinct_rated_movies": 3, "metadata_movies": 3},
            {"train_rows": 8, "test_rows": 2},
            {"top_l": 50, "top_k": 10, "min_common_users": 5, "relevance_threshold": 4, "reducers": 4},
        )
        text = json.dumps(rows, allow_nan=False)
        self.assertNotIn("NaN", text)
        self.assertEqual(rows[0]["mae"], "")


if __name__ == "__main__":
    unittest.main()
