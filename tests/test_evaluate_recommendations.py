import json
import math
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_recommendations import (
    METRICS_CSV_HEADER,
    PER_USER_HEADER,
    EvaluationError,
    compute_metrics,
    load_raw_predictions,
    load_recommendations,
    run_evaluation,
)


FIXTURE_DIR = Path("tests/fixtures/evaluation")
TRAIN = FIXTURE_DIR / "train-ratings.csv"
TEST = FIXTURE_DIR / "test-ratings.csv"
RAW_PREDICTIONS = FIXTURE_DIR / "raw-predictions.txt"
TOP_K_RECOMMENDATIONS = FIXTURE_DIR / "top-k-recommendations.txt"


class EvaluateRecommendationsTests(unittest.TestCase):
    def write_file(self, root: Path, relative_path: str, content: str) -> Path:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def run_fixture_evaluation(self, root: Path, raw_path: Path = RAW_PREDICTIONS):
        metrics_json = root / "metrics.json"
        metrics_csv = root / "metrics.csv"
        per_user = root / "per_user.csv"
        metrics = run_evaluation(
            train_path=TRAIN,
            test_path=TEST,
            raw_predictions_path=raw_path,
            recommendations_path=TOP_K_RECOMMENDATIONS,
            k=2,
            relevance_threshold=4,
            metrics_json_path=metrics_json,
            metrics_csv_path=metrics_csv,
            per_user_output_path=per_user,
        )
        return metrics, metrics_json, metrics_csv, per_user

    def test_parse_valid_raw_predictions(self) -> None:
        predictions = load_raw_predictions(RAW_PREDICTIONS)
        self.assertEqual(predictions[(101, 3)], 4.5)
        self.assertEqual(len(predictions), 3)

    def test_parse_valid_top_k_recommendations(self) -> None:
        recommendations = load_recommendations(TOP_K_RECOMMENDATIONS, 2)
        self.assertEqual([entry.movie_id for entry in recommendations[102]], [2, 1])

    def test_reject_malformed_prediction_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_file(Path(tmp), "raw.txt", "101,3,4.5\n")
            with self.assertRaisesRegex(EvaluationError, "raw prediction"):
                load_raw_predictions(path)

    def test_reject_non_finite_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_file(Path(tmp), "raw.txt", "101,3\tNaN\n")
            with self.assertRaisesRegex(EvaluationError, "finite"):
                load_raw_predictions(path)

    def test_reject_duplicate_recommendation_movie_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_file(Path(tmp), "recs.txt", "101\t3:4.5,3:4.0\n")
            with self.assertRaisesRegex(EvaluationError, "duplicate recommendation movieId"):
                load_recommendations(path, 2)

    def test_reject_recommendations_exceeding_k(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_file(Path(tmp), "recs.txt", "101\t3:4.5,4:4.0,5:3.0\n")
            with self.assertRaisesRegex(EvaluationError, "more than K"):
                load_recommendations(path, 2)

    def test_reject_incorrect_recommendation_ordering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_file(Path(tmp), "recs.txt", "101\t4:4.0,3:4.5\n")
            with self.assertRaisesRegex(EvaluationError, "ordered"):
                load_recommendations(path, 2)

    def test_detect_train_test_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            train = self.write_file(
                root,
                "train.csv",
                "userId,movieId,rating,date\n101,3,5,2005-01-01\n",
            )
            with self.assertRaisesRegex(EvaluationError, "overlap"):
                run_evaluation(
                    train,
                    TEST,
                    RAW_PREDICTIONS,
                    TOP_K_RECOMMENDATIONS,
                    root / "m.json",
                    root / "m.csv",
                    root / "u.csv",
                    k=2,
                    relevance_threshold=4,
                )

    def test_detect_watched_movies_in_final_recommendations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recs = self.write_file(root, "recs.txt", "101\t1:4.5000000000,3:4.0000000000\n")
            with self.assertRaisesRegex(EvaluationError, "Watched recommendations"):
                run_evaluation(
                    TRAIN,
                    TEST,
                    RAW_PREDICTIONS,
                    recs,
                    root / "m.json",
                    root / "m.csv",
                    root / "u.csv",
                    k=2,
                    relevance_threshold=4,
                )

    def test_compute_matched_and_missing_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metrics, _json, _csv, _per_user = self.run_fixture_evaluation(Path(tmp))
            self.assertEqual(metrics["matched_test_predictions"], 3)
            self.assertEqual(metrics["missing_test_predictions"], 1)

    def test_compute_prediction_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metrics, _json, _csv, _per_user = self.run_fixture_evaluation(Path(tmp))
            self.assertTrue(math.isclose(metrics["prediction_coverage"], 0.75))

    def test_compute_mae(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metrics, _json, _csv, _per_user = self.run_fixture_evaluation(Path(tmp))
            self.assertTrue(math.isclose(metrics["mae"], 2 / 3))

    def test_compute_rmse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metrics, _json, _csv, _per_user = self.run_fixture_evaluation(Path(tmp))
            self.assertTrue(math.isclose(metrics["rmse"], math.sqrt(0.5)))

    def test_exclude_below_threshold_from_ranking_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metrics, _json, _csv, _per_user = self.run_fixture_evaluation(Path(tmp))
            self.assertEqual(metrics["ranking_eligible_users"], 3)

    def test_compute_precision_at_k(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metrics, _json, _csv, _per_user = self.run_fixture_evaluation(Path(tmp))
            self.assertTrue(math.isclose(metrics["precision_at_k"], 1 / 3))

    def test_compute_recall_at_k(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metrics, _json, _csv, _per_user = self.run_fixture_evaluation(Path(tmp))
            self.assertTrue(math.isclose(metrics["recall_at_k"], 2 / 3))

    def test_compute_hit_rate_at_k(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metrics, _json, _csv, _per_user = self.run_fixture_evaluation(Path(tmp))
            self.assertTrue(math.isclose(metrics["hit_rate_at_k"], 2 / 3))

    def test_compute_ndcg_at_k(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metrics, _json, _csv, _per_user = self.run_fixture_evaluation(Path(tmp))
            expected = (1 + 1 / math.log2(3)) / 3
            self.assertTrue(math.isclose(metrics["ndcg_at_k"], expected))

    def test_compute_mrr_at_k(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metrics, _json, _csv, _per_user = self.run_fixture_evaluation(Path(tmp))
            self.assertTrue(math.isclose(metrics["mrr_at_k"], 0.5))

    def test_count_users_without_recommendation_rows_as_misses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metrics, _json, _csv, _per_user = self.run_fixture_evaluation(Path(tmp))
            self.assertEqual(metrics["users_with_recommendations"], 3)
            self.assertTrue(math.isclose(metrics["recommendation_user_coverage"], 0.75))

    def test_write_valid_json_without_nan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metrics, metrics_json, _csv, _per_user = self.run_fixture_evaluation(root)
            loaded = json.loads(metrics_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded["watched_recommendations_found"], 0)
            self.assertNotIn("NaN", metrics_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded["mae"], metrics["mae"])

    def test_write_exact_metrics_csv_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _metrics, _json, metrics_csv, _per_user = self.run_fixture_evaluation(Path(tmp))
            header = metrics_csv.read_text(encoding="utf-8").splitlines()[0].split(",")
            self.assertEqual(header, METRICS_CSV_HEADER)

    def test_write_deterministic_per_user_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _metrics, _json, _csv, per_user = self.run_fixture_evaluation(Path(tmp))
            lines = per_user.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0].split(","), PER_USER_HEADER)
            self.assertEqual([line.split(",")[0] for line in lines[1:]], ["101", "102", "103", "104"])

    def test_handle_no_matched_predictions_with_null_mae_rmse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = self.write_file(root, "raw.txt", "999,9\t4.0000000000\n")
            metrics, metrics_json, _csv, _per_user = self.run_fixture_evaluation(root, raw)
            self.assertIsNone(metrics["mae"])
            self.assertIsNone(metrics["rmse"])
            loaded = json.loads(metrics_json.read_text(encoding="utf-8"))
            self.assertIsNone(loaded["mae"])
            self.assertIsNone(loaded["rmse"])

    def test_reject_k_below_one(self) -> None:
        with self.assertRaisesRegex(EvaluationError, "k"):
            load_recommendations(TOP_K_RECOMMENDATIONS, 0)

    def test_reject_relevance_threshold_outside_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(EvaluationError, "relevance"):
                run_evaluation(
                    TRAIN,
                    TEST,
                    RAW_PREDICTIONS,
                    TOP_K_RECOMMENDATIONS,
                    root / "m.json",
                    root / "m.csv",
                    root / "u.csv",
                    k=2,
                    relevance_threshold=6,
                )

    def test_duplicate_raw_prediction_identical_score_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw = self.write_file(Path(tmp), "raw.txt", "101,3\t4.5000000000\n101,3\t4.5000000000\n")
            predictions = load_raw_predictions(raw)
            self.assertEqual(predictions[(101, 3)], 4.5)

    def test_conflicting_duplicate_raw_prediction_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw = self.write_file(Path(tmp), "raw.txt", "101,3\t4.5000000000\n101,3\t4.0000000000\n")
            with self.assertRaisesRegex(EvaluationError, "conflicting duplicate prediction"):
                load_raw_predictions(raw)

    def test_compute_metrics_directly_from_loaded_inputs(self) -> None:
        raw_predictions = load_raw_predictions(RAW_PREDICTIONS)
        recommendations = load_recommendations(TOP_K_RECOMMENDATIONS, 2)
        metrics, diagnostics = compute_metrics(
            train_records=[],
            test_records=[],
            raw_predictions=raw_predictions,
            recommendations=recommendations,
            k=2,
            relevance_threshold=4,
        )
        self.assertEqual(metrics["test_rows"], 0)
        self.assertEqual(diagnostics, [])


if __name__ == "__main__":
    unittest.main()
