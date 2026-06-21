import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_streamlit_final import validate_streamlit_artifacts


class StreamlitFinalValidationTests(unittest.TestCase):
    def write(self, path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def valid_metrics(self) -> dict[str, object]:
        return {
            "evaluation_method": "leave-one-out-offline-v1",
            "k": 1,
            "relevance_threshold": 4,
            "test_rows": 1,
            "matched_test_predictions": 1,
            "missing_test_predictions": 0,
            "prediction_coverage": 1.0,
            "mae": 0.5,
            "rmse": 0.5,
            "ranking_eligible_users": 1,
            "ranking_hits": 1,
            "users_with_recommendations": 1,
            "recommendation_user_coverage": 1.0,
            "precision_at_k": 1.0,
            "recall_at_k": 1.0,
            "hit_rate_at_k": 1.0,
            "ndcg_at_k": 1.0,
            "mrr_at_k": 1.0,
            "watched_recommendations_found": 0,
            "train_test_overlap_rows": 0,
        }

    def prepare_movielens_artifacts(self, root: Path) -> None:
        run = root / "results" / "movielens-1m"
        self.write(root / "README.md", "demo\n")
        (root / ".git").mkdir()
        self.write(run / "common" / "user-history" / "part-r-00000", "101\t1:5,2:4\n")
        self.write(run / "cosine" / "recommendations" / "part-r-00000", "101\t3:4.5000000000\n")
        self.write(run / "cooccurrence" / "recommendations" / "part-r-00000", "101\t3:4.5000000000\n")
        self.write(run / "normalized" / "movie_metadata.csv", "movieId,title,year,genres\n1,A,2001,Drama\n2,B,2002,Comedy\n3,C,2003,Action\n")
        self.write(run / "movielens_1m_manifest.json", json.dumps({"dataset_name": "MovieLens 1M", "dataset_role": "primary-experimental", "parameters": {"top_l": 50, "top_k": 10}}))
        metrics = json.dumps(self.valid_metrics(), allow_nan=False)
        self.write(run / "cosine" / "metrics.json", metrics)
        self.write(run / "cooccurrence" / "metrics.json", metrics)
        self.write(
            run / "method_comparison.csv",
            "method,dataset,status\ncosine,MovieLens 1M,completed\ncooccurrence,MovieLens 1M,completed\n",
        )

    def test_validates_small_movielens_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_movielens_artifacts(root)

            result = validate_streamlit_artifacts(root, method="cosine", app_test_passed=True, health_check_passed=True)

            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["real_movielens_artifacts_valid"])
            self.assertEqual(result["metadata_coverage"], 1.0)
            self.assertEqual(result["watched_recommendation_violations"], 0)
            self.assertTrue(result["metrics_loaded"])
            self.assertTrue(result["comparison_loaded"])
            self.assertFalse(Path(result["inputs"]["user_history"]).is_absolute())

    def test_missing_movielens_artifacts_do_not_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root / "README.md", "demo\n")
            (root / ".git").mkdir()
            result = validate_streamlit_artifacts(root, method="cosine")
            self.assertEqual(result["status"], "failed")
            self.assertFalse(result["real_movielens_artifacts_valid"])
            self.assertTrue(any("MovieLens" in item for item in result["errors"]))


if __name__ == "__main__":
    unittest.main()
