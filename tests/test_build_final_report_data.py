import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_final_report_data import PLACEHOLDER, build_final_report_data


class BuildFinalReportDataTests(unittest.TestCase):
    def write(self, path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_json(self, path: Path, payload: dict[str, object]) -> Path:
        return self.write(path, json.dumps(payload, allow_nan=False))

    def prepare_run(self, root: Path) -> Path:
        run = root / "results" / "movielens-1m"
        self.write_json(
            run / "movielens_1m_manifest.json",
            {
                "dataset_name": "MovieLens 1M",
                "dataset_role": "primary-experimental",
                "parameters": {"top_l": 50, "top_k": 10, "min_common_users": 5, "relevance_threshold": 4},
            },
        )
        self.write_json(
            run / "normalized" / "dataset_stats.json",
            {
                "rating_rows": 1000209,
                "distinct_users": 6040,
                "distinct_rated_movies": 3706,
                "metadata_movies": 3883,
                "minimum_datetime_utc": "2000-04-25T23:05:32Z",
                "maximum_datetime_utc": "2003-02-28T17:49:50Z",
            },
        )
        self.write_json(
            run / "split" / "split_stats.json",
            {"split_method": "leave-one-out-by-exact-timestamp", "train_rows": 994169, "test_rows": 6040, "train_test_overlap_rows": 0},
        )
        self.write(
            run / "method_comparison.csv",
            "method,dataset,ratingsRows,users,ratedMovies,metadataMovies,trainRows,testRows,topL,topK,minCommonUsers,relevanceThreshold,matchedPredictions,missingPredictions,predictionCoverage,mae,rmse,rankingEligibleUsers,rankingHits,recommendationUsers,recommendationUserCoverage,precisionAtK,recallAtK,hitRateAtK,ndcgAtK,mrrAtK,userHistorySeconds,pairStatisticsSeconds,similaritySeconds,scoringSeconds,topKSeconds,evaluationSeconds,totalPipelineSeconds,status\n"
            "cosine,MovieLens 1M,1000209,6040,3706,3883,994169,6040,50,10,5,4,5000,1040,0.8278145695,0.7,0.9,5000,1000,6000,0.9933774834,0.1,0.2,0.2,0.3,0.4,1,2,3,4,5,6,21,completed\n"
            "cooccurrence,MovieLens 1M,1000209,6040,3706,3883,994169,6040,50,10,5,4,4800,1240,0.7947019868,0.8,1.0,4800,900,5900,0.9768211921,0.09,0.18,0.18,0.28,0.35,1,2,3,4,5,6,21,completed\n",
        )
        self.write_json(run / "stage_metrics.json", {"dataset_name": "MovieLens 1M", "stages": [{"stage": "user_history", "status": "completed", "elapsedSeconds": 1.0, "outputRows": 6040, "outputBytes": 123}]})
        self.write_json(run / "cosine" / "metrics.json", {"rmse": 0.9, "watched_recommendations_found": 0})
        self.write_json(run / "cooccurrence" / "metrics.json", {"rmse": 1.0, "watched_recommendations_found": 0})
        self.write_json(root / "target" / "final-validation" / "streamlit_movielens_1m_validation.json", {"status": "passed", "real_movielens_artifacts_valid": True})
        return run

    def test_builds_report_files_from_movielens_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            self.write(root / "README.md", "demo\n")
            self.write(root / "docs" / "final_report_content.md", "ready\n")
            self.write(root / "docs" / "final_presentation_content.md", "ready\n")
            run = self.prepare_run(root)
            out = root / "target" / "final-report-data"

            facts = build_final_report_data(root, run, out)

            self.assertEqual(facts["dataset"]["name"]["value"], "MovieLens 1M")
            self.assertEqual(facts["split"]["method"]["value"], "leave-one-out-by-exact-timestamp")
            self.assertTrue((out / "final_report_facts.json").is_file())
            self.assertIn("MovieLens 1M", (out / "method_metrics.csv").read_text(encoding="utf-8"))
            self.assertIn("user_history", (out / "stage_output_counts.csv").read_text(encoding="utf-8"))

    def test_missing_movielens_values_do_not_fallback_to_github(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            self.write(root / "README.md", "demo\n")
            self.write(root / "docs" / "final_report_content.md", "ready\n")
            self.write(root / "docs" / "final_presentation_content.md", "ready\n")
            self.write_json(root / "results" / "full-reference-dataset" / "full_dataset_manifest.json", {"total_ratings": 999})
            out = root / "target" / "final-report-data"

            facts = build_final_report_data(root, "results/movielens-1m", out)

            self.assertIn("normalized/dataset_stats.json", "\n".join(facts["missing_required_movielens_sources"]))
            self.assertEqual(facts["dataset"]["ratingsRows"]["value"], PLACEHOLDER)
            self.assertIn(PLACEHOLDER, (out / "dataset_summary.csv").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
