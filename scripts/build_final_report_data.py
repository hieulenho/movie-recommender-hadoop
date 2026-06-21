"""Build report-ready Milestone 12 facts from real generated artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.final_artifact_utils import (
    FinalArtifactError,
    count_part_rows,
    count_recommendation_items,
    ensure_no_invalid_floats,
    load_json,
    read_csv_rows,
    relative_path,
    repo_root_from,
    source_record,
    write_csv_rows,
    write_json,
)


METHODS = ("cosine", "cooccurrence")
STAGE_DIRS = (
    ("userHistoryRows", "user-history"),
    ("itemPairRows", "pair-statistics"),
    ("similarityRows", "similarity"),
    ("rawPredictionRows", "raw-predictions"),
)
METRIC_COLUMNS = (
    "predictionCoverage",
    "mae",
    "rmse",
    "precisionAtK",
    "recallAtK",
    "hitRateAtK",
    "ndcgAtK",
    "mrrAtK",
)
RUNTIME_COLUMNS = (
    "userHistorySeconds",
    "pairStatisticsSeconds",
    "similaritySeconds",
    "scoringSeconds",
    "topKSeconds",
    "evaluationSeconds",
    "totalPipelineSeconds",
)


def _required_file(path: Path) -> Path:
    if not path.is_file():
        raise FinalArtifactError(f"Required file is missing: {path}")
    return path


def _scan_placeholders(paths: Sequence[Path], root: Path) -> list[dict[str, Any]]:
    pattern = re.compile(r"\b(TODO|TBD|FIXME)\b|\[[^\]]*(?:TODO|TBD|FILL|PLACEHOLDER)[^\]]*\]|CHEN|DIEN", re.IGNORECASE)
    matches: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if pattern.search(line):
                matches.append({"path": relative_path(path, root), "line": index, "text": line.strip()})
    return matches


def _method_output_counts(run_dir: Path, method: str) -> dict[str, Any]:
    method_dir = run_dir / method
    counts: dict[str, Any] = {"method": method}
    for column, subdir in STAGE_DIRS:
        counts[column] = count_part_rows(method_dir / subdir)
    rec_users, rec_items = count_recommendation_items(method_dir / "recommendations")
    counts["recommendationUsers"] = rec_users
    counts["recommendationItems"] = rec_items
    return counts


def build_final_report_data(repo_root: Path | str, run_dir: Path | str, output_dir: Path | str) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    run_root = Path(run_dir).resolve()
    out_root = Path(output_dir).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    manifest_path = _required_file(run_root / "full_dataset_manifest.json")
    dataset_stats_path = _required_file(run_root / "normalized" / "dataset_stats.json")
    split_stats_path = _required_file(run_root / "split" / "split_stats.json")
    comparison_path = _required_file(run_root / "method_comparison.csv")

    manifest = load_json(manifest_path)
    dataset_stats = load_json(dataset_stats_path)
    split_stats = load_json(split_stats_path)
    comparison_rows = read_csv_rows(comparison_path)
    method_metrics = {method: load_json(_required_file(run_root / method / "metrics.json")) for method in METHODS}

    facts: dict[str, Any] = {
        "project": {
            "name": "Scalable Movie Recommender System Using Item-Based Collaborative Filtering and Hadoop MapReduce",
            "version": "1.0.0",
            "release_status": "release-candidate",
        },
        "dataset": {
            "label": manifest.get("dataset_label"),
            "source_repository": manifest.get("source_repository"),
            "source_subset_description": manifest.get("source_subset_description"),
            "source_format": manifest.get("source_format"),
            "source_has_dates": manifest.get("source_has_dates"),
            "source_date_status": dataset_stats.get("source_date_status"),
            "schema_placeholder_date": manifest.get("schema_placeholder_date"),
            "total_ratings": manifest.get("total_ratings"),
            "distinct_users": manifest.get("distinct_users"),
            "distinct_movies": manifest.get("distinct_movies"),
            "movie_ids": manifest.get("movie_ids"),
            "normalized_sha256": manifest.get("normalized_hash"),
        },
        "split": {
            "method": manifest.get("split_method"),
            "tie_breaking_rule": manifest.get("split_tie_breaking_rule"),
            "train_rows": manifest.get("train_rows"),
            "test_rows": manifest.get("test_rows"),
            "train_test_overlap_count": manifest.get("train_test_overlap_count"),
            "warning": manifest.get("warning") or split_stats.get("warning"),
        },
        "parameters": manifest.get("parameters", {}),
        "metrics": method_metrics,
        "method_comparison": comparison_rows,
        "pipeline_outputs": [_method_output_counts(run_root, method) for method in METHODS],
        "scalability": {
            "status": "unavailable",
            "message": "Chưa có dữ liệu thực nghiệm",
            "expected_path": "target/scalability-benchmark/benchmark_results.csv",
        },
        "limitations": [
            "Full-reference run uses the 15 movie files available in the source GitHub repository, not the complete official Netflix Prize dataset.",
            "Source rows contain userId,movieId,rating and no dates; the full-reference split is deterministic non-temporal holdout by highest movieId.",
            "Docker Hadoop local mode is a reproducibility environment, not multi-node cluster scaling evidence.",
            "No real scalability benchmark artifact was present when this report data was generated.",
        ],
    }
    ensure_no_invalid_floats(facts)

    write_json(out_root / "final_report_facts.json", facts)
    write_json(
        out_root / "data_sources_manifest.json",
        {
            "sources": [
                source_record(manifest_path, root, "full reference manifest"),
                source_record(dataset_stats_path, root, "dataset statistics"),
                source_record(split_stats_path, root, "split statistics"),
                source_record(comparison_path, root, "method comparison"),
                *[
                    source_record(run_root / method / "metrics.json", root, f"{method} evaluation metrics")
                    for method in METHODS
                ],
                source_record(root / "target" / "scalability-benchmark" / "benchmark_results.csv", root, "optional scalability benchmark"),
            ]
        },
    )

    write_csv_rows(
        out_root / "dataset_summary.csv",
        ["field", "value"],
        [
            ("ratingsRows", facts["dataset"]["total_ratings"]),
            ("distinctUsers", facts["dataset"]["distinct_users"]),
            ("distinctMovies", facts["dataset"]["distinct_movies"]),
            ("sourceHasDates", facts["dataset"]["source_has_dates"]),
            ("sourceDateStatus", facts["dataset"]["source_date_status"]),
            ("sourceFormat", facts["dataset"]["source_format"]),
            ("normalizedSha256", facts["dataset"]["normalized_sha256"]),
        ],
    )
    write_csv_rows(
        out_root / "split_summary.csv",
        ["field", "value"],
        [
            ("splitMethod", facts["split"]["method"]),
            ("tieBreakingRule", facts["split"]["tie_breaking_rule"]),
            ("trainRows", facts["split"]["train_rows"]),
            ("testRows", facts["split"]["test_rows"]),
            ("trainTestOverlapCount", facts["split"]["train_test_overlap_count"]),
        ],
    )
    write_csv_rows(
        out_root / "method_metrics.csv",
        ["method", *METRIC_COLUMNS],
        ([method, *[row.get(column, "") for column in METRIC_COLUMNS]] for method, row in ((r["method"], r) for r in comparison_rows)),
    )
    write_csv_rows(
        out_root / "runtime_comparison.csv",
        ["method", *RUNTIME_COLUMNS],
        ([row.get("method", ""), *[row.get(column, "") for column in RUNTIME_COLUMNS]] for row in comparison_rows),
    )
    write_csv_rows(
        out_root / "stage_output_counts.csv",
        ["method", "userHistoryRows", "itemPairRows", "similarityRows", "rawPredictionRows", "recommendationUsers", "recommendationItems"],
        ([counts.get(column, "") for column in ["method", "userHistoryRows", "itemPairRows", "similarityRows", "rawPredictionRows", "recommendationUsers", "recommendationItems"]] for counts in facts["pipeline_outputs"]),
    )
    write_csv_rows(
        out_root / "ranking_metrics.csv",
        ["method", "precisionAtK", "recallAtK", "hitRateAtK", "ndcgAtK", "mrrAtK"],
        ([row.get("method", ""), row.get("precisionAtK", ""), row.get("recallAtK", ""), row.get("hitRateAtK", ""), row.get("ndcgAtK", ""), row.get("mrrAtK", "")] for row in comparison_rows),
    )
    write_csv_rows(
        out_root / "rating_metrics.csv",
        ["method", "predictionCoverage", "mae", "rmse"],
        ([row.get("method", ""), row.get("predictionCoverage", ""), row.get("mae", ""), row.get("rmse", "")] for row in comparison_rows),
    )
    write_csv_rows(
        out_root / "scalability_summary.csv",
        ["status", "message", "path"],
        [("unavailable", "Chưa có dữ liệu thực nghiệm", "target/scalability-benchmark/benchmark_results.csv")],
    )

    placeholder_matches = _scan_placeholders(
        [root / "docs" / "final_report_content.md", root / "docs" / "final_presentation_content.md"],
        root,
    )
    write_json(out_root / "remaining_placeholders.json", {"matches": placeholder_matches, "match_count": len(placeholder_matches)})
    (out_root / "remaining_placeholders.md").write_text(
        "# Remaining Placeholders\n\n"
        + ("\n".join(f"- {item['path']}:{item['line']} {item['text']}" for item in placeholder_matches) if placeholder_matches else "No placeholder markers found.\n"),
        encoding="utf-8",
    )

    report_md = f"""# Final Report Facts

## Dataset

- Source: {facts['dataset']['source_repository']} ({facts['dataset']['source_subset_description']}).
- Rows: {facts['dataset']['total_ratings']}; users: {facts['dataset']['distinct_users']}; movies: {facts['dataset']['distinct_movies']}.
- Source format: {facts['dataset']['source_format']}; source dates available: {facts['dataset']['source_has_dates']}.
- Split: {facts['split']['method']}; tie break: {facts['split']['tie_breaking_rule']}.

## Method Results

| Method | Coverage | MAE | RMSE | Precision@K | Recall@K | NDCG@K | MRR@K | Total seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
"""
    for row in comparison_rows:
        report_md += (
            f"| {row.get('method', '')} | {row.get('predictionCoverage', '')} | {row.get('mae', '')} | "
            f"{row.get('rmse', '')} | {row.get('precisionAtK', '')} | {row.get('recallAtK', '')} | "
            f"{row.get('ndcgAtK', '')} | {row.get('mrrAtK', '')} | {row.get('totalPipelineSeconds', '')} |\n"
        )
    report_md += "\n## Scalability\n\nChưa có dữ liệu thực nghiệm.\n"
    (out_root / "final_report_facts.md").write_text(report_md, encoding="utf-8")

    slide_md = f"""# Final Slide Facts

- Dataset: {facts['dataset']['total_ratings']} ratings, {facts['dataset']['distinct_users']} users, {facts['dataset']['distinct_movies']} movies.
- Split: deterministic non-temporal leave-one-out by highest movieId.
- Cosine RMSE: {comparison_rows[0].get('rmse', '')}; co-occurrence RMSE: {comparison_rows[1].get('rmse', '')}.
- Docker Hadoop local mode validates reproducibility, not cluster scaling.
- Scalability benchmark: Chưa có dữ liệu thực nghiệm.
"""
    (out_root / "final_slide_facts.md").write_text(slide_md, encoding="utf-8")
    (out_root / "report_table_catalog.md").write_text(
        "# Report Table Catalog\n\n"
        "- `dataset_summary.csv`: source and normalized dataset facts.\n"
        "- `split_summary.csv`: deterministic non-temporal split facts.\n"
        "- `method_metrics.csv`: quality metrics by method.\n"
        "- `runtime_comparison.csv`: local-mode pipeline timing by method.\n"
        "- `stage_output_counts.csv`: Hadoop output row counts by method.\n"
        "- `scalability_summary.csv`: real benchmark availability statement.\n",
        encoding="utf-8",
    )
    return facts


def build_arg_parser() -> argparse.ArgumentParser:
    root = repo_root_from()
    parser = argparse.ArgumentParser(description="Build final report data from generated artifacts.")
    parser.add_argument("--repo-root", default=str(root), help="Repository root.")
    parser.add_argument("--run-dir", default="results/full-reference-dataset", help="Full-reference run directory.")
    parser.add_argument("--output-dir", default="target/final-report-data", help="Output directory.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    try:
        build_final_report_data(root, root / args.run_dir, root / args.output_dir)
    except (FinalArtifactError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Final report data written to {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
