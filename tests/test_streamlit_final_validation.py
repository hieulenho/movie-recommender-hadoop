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

    def test_validates_small_local_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root / "README.md", "demo\n")
            (root / ".git").mkdir()
            history = self.write(root / "out" / "history" / "part-r-00000", "101\t1:5,2:4\n")
            recommendations = self.write(root / "out" / "recommendations" / "part-r-00000", "101\t3:4.5000000000\n")
            metadata = self.write(root / "out" / "metadata.csv", "movieId,title,year\n1,A,2001\n2,B,2002\n3,C,2003\n")
            self.write(root / "results" / "full-reference-dataset" / "metadata" / "movie_metadata.csv", metadata.read_text(encoding="utf-8"))
            metrics = self.write(
                root / "out" / "metrics.json",
                json.dumps(
                    {
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
                        "precision_at_k": 1.0,
                        "recall_at_k": 1.0,
                        "hit_rate_at_k": 1.0,
                        "ndcg_at_k": 1.0,
                        "mrr_at_k": 1.0,
                        "watched_recommendations_found": 0,
                        "train_test_overlap_rows": 0,
                    },
                    allow_nan=False,
                ),
            )
            co_history = self.write(root / "results" / "full-reference-dataset" / "cooccurrence" / "user-history" / "part-r-00000", "101\t1:5,2:4\n")
            co_recs = self.write(root / "results" / "full-reference-dataset" / "cooccurrence" / "recommendations" / "part-r-00000", "101\t3:4.5000000000\n")
            self.write(root / "results" / "full-reference-dataset" / "cooccurrence" / "metrics.json", metrics.read_text(encoding="utf-8"))

            result = validate_streamlit_artifacts(root, history.parent, recommendations.parent, metadata, metrics)

            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["real_artifacts"]["valid"])
            self.assertTrue(result["cooccurrence_artifacts"]["valid"])
            self.assertEqual(result["real_artifacts"]["metadata_coverage"], 1.0)
            self.assertFalse(Path(result["inputs"]["user_history"]).is_absolute())


if __name__ == "__main__":
    unittest.main()
