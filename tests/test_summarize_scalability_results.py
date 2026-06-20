import csv
import tempfile
import unittest
from pathlib import Path

from scripts.run_scalability_experiments import BENCHMARK_RESULTS_HEADER
from scripts.summarize_scalability_results import (
    calculate_runtime_growth_factors,
    calculate_stage_percentages,
    calculate_throughput,
    read_benchmark_csv,
    safe_divide,
    sort_rows,
    summarize_results,
    summarize_runtime,
    write_method_comparison_csv,
    write_summary_md,
)


class SummarizeScalabilityResultsTests(unittest.TestCase):
    def row(self, **overrides: object) -> dict[str, object]:
        row = {column: "" for column in BENCHMARK_RESULTS_HEADER}
        row.update(
            {
                "experimentId": "exp-a",
                "profile": "smoke",
                "datasetType": "synthetic",
                "method": "cosine",
                "ratingsRows": "100",
                "testRows": "10",
                "totalPipelineSeconds": "10",
                "userHistorySeconds": "1",
                "pairStatisticsSeconds": "2",
                "similaritySeconds": "3",
                "scoringSeconds": "2",
                "topKSeconds": "1",
                "evaluationSeconds": "1",
                "itemPairRows": "50",
                "similarityRows": "25",
                "recommendationUsers": "5",
                "predictionCoverage": "0.5",
                "precisionAtK": "0.1",
                "recallAtK": "0.2",
                "hitRateAtK": "0.2",
                "ndcgAtK": "0.3",
                "mrrAtK": "0.4",
                "repetition": "1",
                "status": "completed",
            }
        )
        row.update(overrides)
        return row

    def write_csv(self, path: Path, rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=BENCHMARK_RESULTS_HEADER, lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow({column: row.get(column, "") for column in BENCHMARK_RESULTS_HEADER})

    def test_reading_valid_benchmark_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "benchmark_results.csv"
            self.write_csv(path, [self.row()])
            rows = read_benchmark_csv(path)
            self.assertEqual(rows[0]["experimentId"], "exp-a")

    def test_calculating_throughput(self) -> None:
        self.assertEqual(calculate_throughput(self.row()), 10.0)

    def test_calculating_runtime_growth_factor(self) -> None:
        rows = [
            self.row(experimentId="small", ratingsRows="100", totalPipelineSeconds="5"),
            self.row(experimentId="large", ratingsRows="200", totalPipelineSeconds="15"),
        ]
        factors = calculate_runtime_growth_factors(rows)
        self.assertEqual(factors["small"], 1.0)
        self.assertEqual(factors["large"], 3.0)

    def test_calculating_stage_percentages(self) -> None:
        percentages = calculate_stage_percentages(self.row())
        self.assertEqual(percentages["userHistorySeconds"], 0.1)
        self.assertEqual(percentages["similaritySeconds"], 0.3)

    def test_handling_zero_denominators(self) -> None:
        self.assertIsNone(safe_divide(1, 0))
        self.assertIsNone(calculate_throughput(self.row(totalPipelineSeconds="0")))

    def test_handling_failed_experiments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "summary.md"
            rows = [self.row(status="failed", errorStage="similarity", errorMessage="boom")]
            write_summary_md(rows, output)
            text = output.read_text(encoding="utf-8")
            self.assertIn("similarity", text)
            self.assertIn("boom", text)

    def test_producing_deterministic_table_ordering(self) -> None:
        rows = [
            self.row(experimentId="b", method="cooccurrence", ratingsRows="200"),
            self.row(experimentId="a", method="cosine", ratingsRows="100"),
        ]
        ordered = sort_rows(rows)
        self.assertEqual([row["experimentId"] for row in ordered], ["b", "a"])

    def test_producing_method_comparison_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "method_comparison.csv"
            write_method_comparison_csv([self.row(), self.row(experimentId="exp-b", method="cooccurrence")], output)
            lines = output.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0].split(",")[0:3], ["profile", "ratingsRows", "method"])
            self.assertGreaterEqual(len(lines), 3)

    def test_computing_mean_min_max_and_population_stddev(self) -> None:
        stats = summarize_runtime([1.0, 3.0])
        self.assertEqual(stats["mean"], 2.0)
        self.assertEqual(stats["min"], 1.0)
        self.assertEqual(stats["max"], 3.0)
        self.assertEqual(stats["pstdev"], 1.0)

    def test_summarize_results_writes_all_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_csv = root / "benchmark_results.csv"
            self.write_csv(input_csv, [self.row()])
            summarize_results(input_csv, root / "summary")
            self.assertTrue((root / "summary" / "benchmark_summary.md").is_file())
            self.assertTrue((root / "summary" / "method_comparison.csv").is_file())
            self.assertTrue((root / "summary" / "size_scaling.csv").is_file())


if __name__ == "__main__":
    unittest.main()
