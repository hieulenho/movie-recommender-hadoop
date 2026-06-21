import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_final_report_data import build_final_report_data


class BuildFinalReportDataTests(unittest.TestCase):
    def write(self, path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_json(self, path: Path, payload: dict[str, object]) -> Path:
        return self.write(path, json.dumps(payload, allow_nan=False))

    def prepare_run(self, root: Path) -> Path:
        run = root / "results" / "full-reference-dataset"
        manifest = {
            "dataset_label": "GitHub reference repository 15-movie subset",
            "source_repository": "thviet79/Bigdata_Project_Recommender_System",
            "source_subset_description": "all 15 mv_*.txt files committed in Movie_DataSet",
            "source_format": "github-reference-3col",
            "source_has_dates": False,
            "schema_placeholder_date": "1970-01-01",
            "total_ratings": 4,
            "distinct_users": 2,
            "distinct_movies": 3,
            "movie_ids": [1, 2, 3],
            "normalized_hash": "abc",
            "split_method": "deterministic-leave-one-out-by-item",
            "split_tie_breaking_rule": "Sort by movieId ascending; hold out the highest movieId.",
            "train_rows": 2,
            "test_rows": 2,
            "train_test_overlap_count": 0,
            "parameters": {"top_k": 1},
        }
        self.write_json(run / "full_dataset_manifest.json", manifest)
        self.write_json(run / "normalized" / "dataset_stats.json", {"source_date_status": "unavailable"})
        self.write_json(run / "split" / "split_stats.json", {"split_method": "deterministic-leave-one-out-by-item"})
        self.write(
            run / "method_comparison.csv",
            "method,predictionCoverage,mae,rmse,precisionAtK,recallAtK,hitRateAtK,ndcgAtK,mrrAtK,totalPipelineSeconds,userHistorySeconds,pairStatisticsSeconds,similaritySeconds,scoringSeconds,topKSeconds,evaluationSeconds\n"
            "cosine,1.0,0.5,0.5,1.0,1.0,1.0,1.0,1.0,1.2,0.1,0.2,0.3,0.4,0.1,0.1\n"
            "cooccurrence,1.0,0.6,0.6,1.0,1.0,1.0,1.0,1.0,1.5,0.1,0.2,0.3,0.6,0.2,0.1\n",
        )
        for method in ("cosine", "cooccurrence"):
            self.write_json(run / method / "metrics.json", {"rmse": 0.5, "watched_recommendations_found": 0})
            self.write(run / method / "user-history" / "part-r-00000", "1\t1:5\n2\t2:4\n")
            self.write(run / method / "pair-statistics" / "part-r-00000", "1,2\t1,20,25,16\n")
            self.write(run / method / "similarity" / "part-r-00000", "1\t2:0.5\n")
            self.write(run / method / "raw-predictions" / "part-r-00000", "1,3\t4.5\n")
            self.write(run / method / "recommendations" / "part-r-00000", "1\t3:4.5000000000\n")
        return run

    def test_builds_report_files_from_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            self.write(root / "README.md", "demo\n")
            self.write(root / "docs" / "final_report_content.md", "ready\n")
            self.write(root / "docs" / "final_presentation_content.md", "ready\n")
            run = self.prepare_run(root)
            out = root / "target" / "final-report-data"

            facts = build_final_report_data(root, run, out)

            self.assertEqual(facts["split"]["method"], "deterministic-leave-one-out-by-item")
            self.assertTrue((out / "final_report_facts.json").is_file())
            self.assertIn("Chưa có dữ liệu thực nghiệm", (out / "scalability_summary.csv").read_text(encoding="utf-8"))
            self.assertIn("cosine", (out / "stage_output_counts.csv").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
