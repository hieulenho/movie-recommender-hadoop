"""Build report-ready facts from primary MovieLens 1M artifacts."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.final_artifact_utils import (
    FinalArtifactError,
    ensure_no_invalid_floats,
    load_json,
    read_csv_rows,
    relative_path,
    repo_root_from,
    sha256_file,
    source_record,
    write_csv_rows,
    write_json,
)


METHODS = ("cosine", "cooccurrence")
PLACEHOLDER = "Chưa có kết quả MovieLens 1M"
METHOD_COLUMNS = [
    "method",
    "dataset",
    "ratingsRows",
    "users",
    "ratedMovies",
    "metadataMovies",
    "trainRows",
    "testRows",
    "topL",
    "topK",
    "minCommonUsers",
    "relevanceThreshold",
    "matchedPredictions",
    "missingPredictions",
    "predictionCoverage",
    "mae",
    "rmse",
    "rankingEligibleUsers",
    "rankingHits",
    "recommendationUsers",
    "recommendationUserCoverage",
    "precisionAtK",
    "recallAtK",
    "hitRateAtK",
    "ndcgAtK",
    "mrrAtK",
    "userHistorySeconds",
    "pairStatisticsSeconds",
    "similaritySeconds",
    "scoringSeconds",
    "topKSeconds",
    "evaluationSeconds",
    "totalPipelineSeconds",
    "status",
]
RATING_COLUMNS = ("predictionCoverage", "mae", "rmse", "matchedPredictions", "missingPredictions")
RANKING_COLUMNS = ("precisionAtK", "recallAtK", "hitRateAtK", "ndcgAtK", "mrrAtK")
RUNTIME_COLUMNS = (
    "userHistorySeconds",
    "pairStatisticsSeconds",
    "similaritySeconds",
    "scoringSeconds",
    "topKSeconds",
    "evaluationSeconds",
    "totalPipelineSeconds",
)


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = load_json(path)
    if not isinstance(data, dict):
        raise FinalArtifactError(f"JSON root must be an object: {path}")
    return data


def _load_csv_if_exists(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    return read_csv_rows(path)


def _value_record(root: Path, path: Path, key: str, value: object, interpretation: str) -> dict[str, Any]:
    record = {
        "value": PLACEHOLDER if value is None or value == "" else value,
        "source": relative_path(path, root),
        "sha256": sha256_file(path) if path.is_file() else None,
        "interpretation": interpretation,
    }
    return record


def _required_sources(run_root: Path) -> dict[str, Path]:
    return {
        "manifest": run_root / "movielens_1m_manifest.json",
        "dataset_stats": run_root / "normalized" / "dataset_stats.json",
        "split_stats": run_root / "split" / "split_stats.json",
        "method_comparison": run_root / "method_comparison.csv",
        "stage_metrics": run_root / "stage_metrics.json",
        "cosine_metrics": run_root / "cosine" / "metrics.json",
        "cooccurrence_metrics": run_root / "cooccurrence" / "metrics.json",
    }


def _method_rows(comparison_rows: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    by_method = {row.get("method", ""): dict(row) for row in comparison_rows}
    rows = []
    for method in METHODS:
        if method in by_method:
            rows.append({column: by_method[method].get(column, "") for column in METHOD_COLUMNS})
        else:
            rows.append({column: PLACEHOLDER for column in METHOD_COLUMNS} | {"method": method, "dataset": "MovieLens 1M"})
    return rows


def _csv_dict_rows(path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


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


def _stage_output_rows(stage_metrics: Mapping[str, Any] | None) -> list[dict[str, object]]:
    if not stage_metrics:
        return [{"stage": PLACEHOLDER, "status": PLACEHOLDER, "elapsedSeconds": "", "outputRows": "", "outputBytes": ""}]
    stages = stage_metrics.get("stages")
    if not isinstance(stages, list):
        return [{"stage": PLACEHOLDER, "status": PLACEHOLDER, "elapsedSeconds": "", "outputRows": "", "outputBytes": ""}]
    return [
        {
            "stage": item.get("stage", "") if isinstance(item, Mapping) else "",
            "status": item.get("status", "") if isinstance(item, Mapping) else "",
            "elapsedSeconds": item.get("elapsedSeconds", "") if isinstance(item, Mapping) else "",
            "outputRows": item.get("outputRows", "") if isinstance(item, Mapping) else "",
            "outputBytes": item.get("outputBytes", "") if isinstance(item, Mapping) else "",
        }
        for item in stages
        if isinstance(item, Mapping)
    ]


def build_final_report_data(repo_root: Path | str, run_dir: Path | str, output_dir: Path | str) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    run_root = Path(run_dir)
    if not run_root.is_absolute():
        run_root = root / run_root
    out_root = Path(output_dir)
    if not out_root.is_absolute():
        out_root = root / out_root
    out_root.mkdir(parents=True, exist_ok=True)

    sources = _required_sources(run_root)
    manifest = _load_json_if_exists(sources["manifest"])
    dataset_stats = _load_json_if_exists(sources["dataset_stats"])
    split_stats = _load_json_if_exists(sources["split_stats"])
    stage_metrics = _load_json_if_exists(sources["stage_metrics"])
    comparison_rows = _load_csv_if_exists(sources["method_comparison"])
    method_rows = _method_rows(comparison_rows)
    streamlit_validation_path = root / "target" / "final-validation" / "streamlit_movielens_1m_validation.json"
    streamlit_validation = _load_json_if_exists(streamlit_validation_path)

    missing_required = [relative_path(path, root) for path in sources.values() if not path.is_file()]
    dataset_source = sources["dataset_stats"]
    split_source = sources["split_stats"]
    manifest_source = sources["manifest"]
    comparison_source = sources["method_comparison"]
    streamlit_source = streamlit_validation_path

    facts: dict[str, Any] = {
        "project": {
            "name": "Scalable Movie Recommender System Using Item-Based Collaborative Filtering and Hadoop MapReduce",
            "primary_dataset": "MovieLens 1M",
        },
        "dataset_roles": {
            "movielens_1m": "primary real experiment",
            "github_reference_15_movie": "compatibility and workflow validation",
            "synthetic": "controlled scalability only",
        },
        "dataset": {
            "name": _value_record(root, manifest_source, "dataset_name", (manifest or {}).get("dataset_name", "MovieLens 1M"), "Primary experiment dataset name."),
            "role": _value_record(root, manifest_source, "dataset_role", (manifest or {}).get("dataset_role", "primary-experimental"), "MovieLens role in final reporting."),
            "ratingsRows": _value_record(root, dataset_source, "rating_rows", (dataset_stats or {}).get("rating_rows"), "Accepted MovieLens rating rows."),
            "users": _value_record(root, dataset_source, "distinct_users", (dataset_stats or {}).get("distinct_users"), "Distinct MovieLens users."),
            "ratedMovies": _value_record(root, dataset_source, "distinct_rated_movies", (dataset_stats or {}).get("distinct_rated_movies"), "Movies with at least one rating."),
            "metadataMovies": _value_record(root, dataset_source, "metadata_movies", (dataset_stats or {}).get("metadata_movies"), "Movie metadata rows."),
            "timestampRangeUtc": _value_record(
                root,
                dataset_source,
                "timestamp_range",
                f"{(dataset_stats or {}).get('minimum_datetime_utc', PLACEHOLDER)} to {(dataset_stats or {}).get('maximum_datetime_utc', PLACEHOLDER)}" if dataset_stats else None,
                "UTC timestamp range preserved before splitting.",
            ),
        },
        "split": {
            "method": _value_record(root, split_source, "split_method", (split_stats or {}).get("split_method"), "Temporal holdout protocol."),
            "trainRows": _value_record(root, split_source, "train_rows", (split_stats or {}).get("train_rows"), "Train rows entering Hadoop model stages."),
            "testRows": _value_record(root, split_source, "test_rows", (split_stats or {}).get("test_rows"), "Held-out test rows used only by evaluator."),
            "trainTestOverlapRows": _value_record(root, split_source, "train_test_overlap_rows", (split_stats or {}).get("train_test_overlap_rows"), "Expected to be zero."),
        },
        "parameters": _value_record(root, manifest_source, "parameters", (manifest or {}).get("parameters"), "MovieLens full-run parameters."),
        "methods": {
            method: _value_record(root, comparison_source, method, next((row for row in method_rows if row.get("method") == method), None), f"{method} quality and runtime metrics.")
            for method in METHODS
        },
        "streamlit_validation": _value_record(root, streamlit_source, "streamlit_validation", streamlit_validation, "Read-only Streamlit MovieLens validation."),
        "missing_required_movielens_sources": missing_required,
    }
    ensure_no_invalid_floats(facts)

    write_json(out_root / "final_report_facts.json", facts)
    write_json(
        out_root / "data_sources_manifest.json",
        {
            "sources": [
                source_record(path, root, role)
                for role, path in [
                    ("MovieLens run manifest", sources["manifest"]),
                    ("MovieLens dataset statistics", sources["dataset_stats"]),
                    ("MovieLens split statistics", sources["split_stats"]),
                    ("MovieLens method comparison", sources["method_comparison"]),
                    ("MovieLens stage metrics", sources["stage_metrics"]),
                    ("Cosine metrics", sources["cosine_metrics"]),
                    ("Cooccurrence metrics", sources["cooccurrence_metrics"]),
                    ("Streamlit validation", streamlit_validation_path),
                ]
            ]
        },
    )

    write_csv_rows(
        out_root / "dataset_summary.csv",
        ["field", "value", "source", "interpretation"],
        (
            [field, record["value"], record["source"], record["interpretation"]]
            for field, record in facts["dataset"].items()
        ),
    )
    write_csv_rows(
        out_root / "split_summary.csv",
        ["field", "value", "source", "interpretation"],
        (
            [field, record["value"], record["source"], record["interpretation"]]
            for field, record in facts["split"].items()
        ),
    )
    _csv_dict_rows(out_root / "method_metrics.csv", METHOD_COLUMNS, method_rows)
    _csv_dict_rows(
        out_root / "rating_metrics.csv",
        ["method", *RATING_COLUMNS],
        ({column: row.get(column, "") for column in ["method", *RATING_COLUMNS]} for row in method_rows),
    )
    _csv_dict_rows(
        out_root / "ranking_metrics.csv",
        ["method", *RANKING_COLUMNS],
        ({column: row.get(column, "") for column in ["method", *RANKING_COLUMNS]} for row in method_rows),
    )
    _csv_dict_rows(
        out_root / "runtime_comparison.csv",
        ["method", *RUNTIME_COLUMNS],
        ({column: row.get(column, "") for column in ["method", *RUNTIME_COLUMNS]} for row in method_rows),
    )
    _csv_dict_rows(out_root / "stage_output_counts.csv", ["stage", "status", "elapsedSeconds", "outputRows", "outputBytes"], _stage_output_rows(stage_metrics))
    write_csv_rows(
        out_root / "scalability_summary.csv",
        ["dataset_role", "status", "message"],
        [("synthetic-scalability-only", "optional", "Synthetic benchmark remains separate from MovieLens quality metrics.")],
    )
    write_csv_rows(
        out_root / "streamlit_validation_summary.csv",
        ["field", "value", "source"],
        (
            [key, value, relative_path(streamlit_validation_path, root)]
            for key, value in (streamlit_validation or {"status": PLACEHOLDER}).items()
            if key not in {"errors", "warnings", "inputs"}
        ),
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

    dataset_rows = facts["dataset"]
    split_rows = facts["split"]
    report_md = f"""# Final Report Facts

Primary dataset: {dataset_rows['name']['value']} ({dataset_rows['role']['value']}).

- Ratings: {dataset_rows['ratingsRows']['value']}
- Users: {dataset_rows['users']['value']}
- Rated movies: {dataset_rows['ratedMovies']['value']}
- Metadata movies: {dataset_rows['metadataMovies']['value']}
- Timestamp range: {dataset_rows['timestampRangeUtc']['value']}
- Split: {split_rows['method']['value']}
- Train rows: {split_rows['trainRows']['value']}
- Test rows: {split_rows['testRows']['value']}

MovieLens 1M is the primary report source. GitHub 15-file results are compatibility evidence only.
"""
    (out_root / "final_report_facts.md").write_text(report_md, encoding="utf-8")
    slide_md = f"""# Final Slide Facts

- Primary dataset: MovieLens 1M.
- Ratings/users/movies: {dataset_rows['ratingsRows']['value']} / {dataset_rows['users']['value']} / {dataset_rows['ratedMovies']['value']}.
- Split: {split_rows['method']['value']}.
- Cosine and co-occurrence metrics come from `results/movielens-1m/method_comparison.csv`.
- Synthetic benchmark is shown only on the scalability slide.
"""
    (out_root / "final_slide_facts.md").write_text(slide_md, encoding="utf-8")
    (out_root / "report_table_catalog.md").write_text(
        "# Report Table Catalog\n\n"
        "- `dataset_summary.csv`: MovieLens dataset facts.\n"
        "- `split_summary.csv`: exact timestamp split facts.\n"
        "- `method_metrics.csv`: method quality and runtime metrics.\n"
        "- `rating_metrics.csv`: coverage, MAE, and RMSE.\n"
        "- `ranking_metrics.csv`: Precision/Recall/Hit/NDCG/MRR at K.\n"
        "- `runtime_comparison.csv`: local-mode runtime by method.\n"
        "- `stage_output_counts.csv`: stage output counts from MovieLens run.\n"
        "- `scalability_summary.csv`: synthetic scalability note.\n",
        encoding="utf-8",
    )
    return facts


def build_arg_parser() -> argparse.ArgumentParser:
    root = repo_root_from()
    parser = argparse.ArgumentParser(description="Build final report data from MovieLens artifacts.")
    parser.add_argument("--repo-root", default=str(root), help="Repository root.")
    parser.add_argument("--run-dir", default="results/movielens-1m", help="MovieLens run directory.")
    parser.add_argument("--output-dir", default="target/final-report-data", help="Output directory.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    try:
        facts = build_final_report_data(root, args.run_dir, args.output_dir)
    except (FinalArtifactError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    missing = facts.get("missing_required_movielens_sources", [])
    if missing:
        print("Final report data written with missing MovieLens placeholders:")
        for path in missing:
            print(f"- {path}")
    else:
        print(f"Final report data written to {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
