import json
import tempfile
import unittest
from pathlib import Path

from demo.data_loader import (
    discover_part_files,
    fallback_movie_metadata,
    load_benchmark_results,
    load_evaluation_metrics,
    load_movie_metadata,
    load_recommendations,
    load_user_histories,
)
from demo.models import DemoValidationError


class DemoDataLoaderTests(unittest.TestCase):
    def write(self, path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def benchmark_csv(self, rows: list[dict[str, str]]) -> str:
        header = [
            "experimentId",
            "profile",
            "datasetType",
            "method",
            "ratingsRows",
            "trainRows",
            "testRows",
            "topL",
            "topK",
            "totalPipelineSeconds",
            "userHistorySeconds",
            "pairStatisticsSeconds",
            "similaritySeconds",
            "scoringSeconds",
            "topKSeconds",
            "evaluationSeconds",
            "itemPairRows",
            "similarityRows",
            "rawPredictionRows",
            "recommendationUsers",
            "recommendationItems",
            "predictionCoverage",
            "mae",
            "rmse",
            "precisionAtK",
            "recallAtK",
            "ndcgAtK",
            "mrrAtK",
            "status",
        ]
        lines = [",".join(header)]
        for row in rows:
            lines.append(",".join(str(row.get(column, "")) for column in header))
        return "\n".join(lines) + "\n"

    def valid_metrics(self) -> dict[str, object]:
        return {
            "evaluation_method": "leave-one-out-offline-v1",
            "k": 2,
            "relevance_threshold": 4,
            "test_rows": 4,
            "matched_test_predictions": 3,
            "missing_test_predictions": 1,
            "prediction_coverage": 0.75,
            "mae": 0.5,
            "rmse": 0.75,
            "ranking_eligible_users": 3,
            "ranking_hits": 2,
            "recommendation_user_coverage": 0.75,
            "precision_at_k": 0.3333333333,
            "recall_at_k": 0.6666666667,
            "hit_rate_at_k": 0.6666666667,
            "ndcg_at_k": 0.5436432512,
            "mrr_at_k": 0.5,
            "watched_recommendations_found": 0,
            "train_test_overlap_rows": 0,
        }

    def test_discover_one_regular_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp) / "output.txt", "1\t2:5\n")
            self.assertEqual(discover_part_files(path), [path])

    def test_discover_multiple_hadoop_part_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.write(root / "part-r-00001", "2\t3:4\n")
            second = self.write(root / "part-r-00000", "1\t2:5\n")
            self.assertEqual(discover_part_files(root), [second, first])

    def test_ignore_success_and_hidden_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            part = self.write(root / "part-r-00000", "1\t2:5\n")
            self.write(root / "_SUCCESS", "")
            self.write(root / ".part-r-00001.crc", "ignored")
            self.assertEqual(discover_part_files(root), [part])

    def test_deterministic_part_file_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = [self.write(root / name, "1\t2:5\n") for name in ["part-r-00002", "part-r-00000", "part-r-00001"]]
            self.assertEqual([path.name for path in discover_part_files(root)], sorted(path.name for path in paths))

    def test_reject_empty_hadoop_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(DemoValidationError, "No readable part"):
                discover_part_files(Path(tmp))

    def test_parse_valid_user_histories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp) / "history.txt", "101\t2:3,1:5\n")
            histories = load_user_histories(path)
            self.assertEqual([item.movie_id for item in histories[101]], [1, 2])

    def test_reject_malformed_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp) / "history.txt", "101 1:5\n")
            with self.assertRaisesRegex(DemoValidationError, "tab"):
                load_user_histories(path)

    def test_reject_duplicate_movie_ids_in_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp) / "history.txt", "101\t1:5,1:4\n")
            with self.assertRaisesRegex(DemoValidationError, "duplicate"):
                load_user_histories(path)

    def test_reject_conflicting_duplicate_user_histories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp) / "history.txt", "101\t1:5\n101\t1:4\n")
            with self.assertRaisesRegex(DemoValidationError, "Conflicting"):
                load_user_histories(path)

    def test_parse_valid_recommendations_and_preserve_rank(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp) / "recommendations.txt", "101\t3:3.8000000000,4:3.0000000000\n")
            rows = load_recommendations(path)
            self.assertEqual([item.rank for item in rows[101]], [1, 2])

    def test_reject_malformed_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp) / "recommendations.txt", "101\t3\n")
            with self.assertRaisesRegex(DemoValidationError, "malformed"):
                load_recommendations(path)

    def test_reject_duplicate_recommended_movie_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp) / "recommendations.txt", "101\t3:4.0,3:3.0\n")
            with self.assertRaisesRegex(DemoValidationError, "duplicate"):
                load_recommendations(path)

    def test_reject_incorrect_score_ordering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp) / "recommendations.txt", "101\t3:3.0,4:4.0\n")
            with self.assertRaisesRegex(DemoValidationError, "score descending"):
                load_recommendations(path)

    def test_reject_incorrect_tie_ordering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp) / "recommendations.txt", "101\t4:4.0,3:4.0\n")
            with self.assertRaisesRegex(DemoValidationError, "movie ID ascending"):
                load_recommendations(path)

    def test_parse_optional_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp) / "metadata.csv", "movieId,title,year\n1,Demo Movie 1,2001\n")
            metadata = load_movie_metadata(path)
            self.assertEqual(metadata[1].title, "Demo Movie 1")

    def test_reject_duplicate_metadata_movie_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp) / "metadata.csv", "movieId,title,year\n1,A,\n1,B,\n")
            with self.assertRaisesRegex(DemoValidationError, "duplicate"):
                load_movie_metadata(path)

    def test_fallback_movie_titles(self) -> None:
        self.assertEqual(fallback_movie_metadata(17).title, "Movie 17")

    def test_parse_valid_evaluation_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp) / "metrics.json", json.dumps(self.valid_metrics()))
            self.assertEqual(load_evaluation_metrics(path).get("test_rows"), 4)

    def test_support_null_mae_and_rmse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metrics = self.valid_metrics()
            metrics["mae"] = None
            metrics["rmse"] = None
            path = self.write(Path(tmp) / "metrics.json", json.dumps(metrics))
            loaded = load_evaluation_metrics(path)
            self.assertIsNone(loaded.get("mae"))
            self.assertIsNone(loaded.get("rmse"))

    def test_reject_nan_and_infinity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp) / "metrics.json", '{"watched_recommendations_found":0,"train_test_overlap_rows":0,"mae": NaN}')
            with self.assertRaises(DemoValidationError):
                load_evaluation_metrics(path)

    def test_parse_valid_benchmark_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(
                Path(tmp) / "benchmark.csv",
                self.benchmark_csv([{"experimentId": "b", "profile": "smoke", "datasetType": "synthetic", "method": "cosine", "ratingsRows": "100", "status": "completed"}]),
            )
            self.assertEqual(load_benchmark_results(path)[0].experiment_id, "b")

    def test_separate_successful_and_failed_benchmark_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(
                Path(tmp) / "benchmark.csv",
                self.benchmark_csv(
                    [
                        {"experimentId": "ok", "profile": "smoke", "datasetType": "synthetic", "method": "cosine", "ratingsRows": "100", "status": "completed"},
                        {"experimentId": "bad", "profile": "smoke", "datasetType": "synthetic", "method": "cosine", "ratingsRows": "200", "status": "failed"},
                    ]
                ),
            )
            statuses = [run.status for run in load_benchmark_results(path)]
            self.assertEqual(statuses, ["completed", "failed"])

    def test_sort_benchmark_rows_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(
                Path(tmp) / "benchmark.csv",
                self.benchmark_csv(
                    [
                        {"experimentId": "z", "profile": "smoke", "datasetType": "synthetic", "method": "cosine", "ratingsRows": "200", "status": "completed"},
                        {"experimentId": "a", "profile": "smoke", "datasetType": "synthetic", "method": "cooccurrence", "ratingsRows": "100", "status": "completed"},
                    ]
                ),
            )
            self.assertEqual([run.experiment_id for run in load_benchmark_results(path)], ["a", "z"])


if __name__ == "__main__":
    unittest.main()

