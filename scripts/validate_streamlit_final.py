"""Validate final Streamlit demo inputs without mutating Hadoop artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo.data_loader import build_demo_bundle, build_sample_bundle, load_benchmark_results
from demo.models import DemoValidationError
from demo.service import summarize_benchmark_results, validate_bundle_integrity
from scripts.final_artifact_utils import repo_root_from, relative_path, write_json


def _bundle_summary(bundle: Any) -> dict[str, Any]:
    user_count = len(bundle.users)
    watched_movies = sum(len(profile.watched) for profile in bundle.users.values())
    recommendation_users = sum(1 for profile in bundle.users.values() if profile.recommendations)
    recommendation_items = sum(len(profile.recommendations) for profile in bundle.users.values())
    referenced_movie_ids = {
        item.movie_id
        for profile in bundle.users.values()
        for item in [*profile.watched, *profile.recommendations]
    }
    metadata_movie_ids = set(bundle.metadata)
    unknown_metadata = sorted(referenced_movie_ids - metadata_movie_ids)
    coverage = None
    if referenced_movie_ids:
        coverage = (len(referenced_movie_ids) - len(unknown_metadata)) / len(referenced_movie_ids)
    integrity_errors = validate_bundle_integrity(bundle)
    return {
        "valid": not integrity_errors,
        "user_count": user_count,
        "watched_movie_count": watched_movies,
        "recommendation_user_count": recommendation_users,
        "recommendation_item_count": recommendation_items,
        "metadata_row_count": len(bundle.metadata),
        "referenced_movie_count": len(referenced_movie_ids),
        "metadata_coverage": coverage,
        "unknown_metadata_movies": unknown_metadata,
        "integrity_error_count": len(integrity_errors),
        "integrity_errors": integrity_errors[:20],
    }


def validate_streamlit_artifacts(
    repo_root: Path | str,
    user_history: Path | str,
    recommendations: Path | str,
    metadata: Path | str,
    metrics: Path | str,
    benchmark: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    result: dict[str, Any] = {
        "status": "failed",
        "repo_root": ".",
        "source_mode": "bundled-sample-and-full-reference-artifacts",
        "errors": errors,
        "warnings": warnings,
        "inputs": {
            "user_history": relative_path(user_history, root),
            "recommendations": relative_path(recommendations, root),
            "metadata": relative_path(metadata, root),
            "metrics": relative_path(metrics, root),
            "benchmark": None if benchmark is None else relative_path(benchmark, root),
        },
    }

    try:
        sample_bundle = build_sample_bundle()
        result["bundled_sample"] = _bundle_summary(sample_bundle)
    except (DemoValidationError, OSError) as exc:
        errors.append(f"Bundled sample validation failed: {exc}")

    try:
        real_bundle = build_demo_bundle(
            user_history_path=Path(user_history),
            recommendations_path=Path(recommendations),
            evaluation_metrics_path=Path(metrics),
            benchmark_results_path=None,
            movie_metadata_path=Path(metadata),
            manifest_path=root / "results" / "full-reference-dataset" / "full_dataset_manifest.json",
        )
        result["real_artifacts"] = _bundle_summary(real_bundle)
    except (DemoValidationError, OSError) as exc:
        errors.append(f"Full-reference artifact validation failed: {exc}")

    cooccurrence_paths = {
        "user_history": root / "results" / "full-reference-dataset" / "cooccurrence" / "user-history",
        "recommendations": root / "results" / "full-reference-dataset" / "cooccurrence" / "recommendations",
        "metrics": root / "results" / "full-reference-dataset" / "cooccurrence" / "metrics.json",
        "metadata": root / "results" / "full-reference-dataset" / "metadata" / "movie_metadata.csv",
    }
    if all(path.exists() for path in cooccurrence_paths.values()):
        try:
            cooccurrence_bundle = build_demo_bundle(
                user_history_path=cooccurrence_paths["user_history"],
                recommendations_path=cooccurrence_paths["recommendations"],
                evaluation_metrics_path=cooccurrence_paths["metrics"],
                benchmark_results_path=None,
                movie_metadata_path=cooccurrence_paths["metadata"],
                manifest_path=root / "results" / "full-reference-dataset" / "full_dataset_manifest.json",
            )
            result["cooccurrence_artifacts"] = _bundle_summary(cooccurrence_bundle)
        except (DemoValidationError, OSError) as exc:
            errors.append(f"Full-reference cooccurrence artifact validation failed: {exc}")
    else:
        warnings.append("Cooccurrence full-reference artifacts are unavailable; cosine validation still ran.")

    if benchmark is None or not Path(benchmark).exists():
        warnings.append("Benchmark CSV is unavailable; Streamlit benchmark tab can still load without real benchmark runs.")
        result["benchmark"] = {
            "loaded": False,
            "successful_benchmark_runs": 0,
            "failed_benchmark_runs": 0,
            "reason": "unavailable",
        }
    else:
        try:
            runs = load_benchmark_results(Path(benchmark))
            summary = summarize_benchmark_results(runs)
            result["benchmark"] = {
                "loaded": True,
                "successful_benchmark_runs": summary["successful_count"],
                "failed_benchmark_runs": summary["failed_count"],
                "min_ratings_rows": summary["min_ratings_rows"],
                "max_ratings_rows": summary["max_ratings_rows"],
            }
        except (DemoValidationError, OSError) as exc:
            errors.append(f"Benchmark CSV validation failed: {exc}")

    if result.get("bundled_sample", {}).get("valid") is not True:
        errors.append("Bundled sample integrity check did not pass.")
    if result.get("real_artifacts", {}).get("valid") is not True:
        errors.append("Full-reference artifact integrity check did not pass.")
    if "cooccurrence_artifacts" in result and result.get("cooccurrence_artifacts", {}).get("valid") is not True:
        errors.append("Full-reference cooccurrence artifact integrity check did not pass.")

    result["status"] = "passed" if not errors else "failed"
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    root = repo_root_from()
    parser = argparse.ArgumentParser(description="Validate final Streamlit demo artifacts.")
    parser.add_argument("--repo-root", default=str(root), help="Repository root.")
    parser.add_argument(
        "--user-history",
        default="results/full-reference-dataset/cosine/user-history",
        help="Hadoop user-history output file or directory.",
    )
    parser.add_argument(
        "--recommendations",
        default="results/full-reference-dataset/cosine/recommendations",
        help="Hadoop recommendation output file or directory.",
    )
    parser.add_argument(
        "--metadata",
        default="results/full-reference-dataset/metadata/movie_metadata.csv",
        help="Movie metadata CSV.",
    )
    parser.add_argument(
        "--metrics",
        default="results/full-reference-dataset/cosine/metrics.json",
        help="Evaluation metrics JSON.",
    )
    parser.add_argument(
        "--benchmark",
        default="target/scalability-benchmark/benchmark_results.csv",
        help="Optional real benchmark CSV.",
    )
    parser.add_argument(
        "--output",
        default="target/final-validation/streamlit_validation.json",
        help="Validation JSON output path.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    benchmark = root / args.benchmark if args.benchmark else None
    result = validate_streamlit_artifacts(
        root,
        root / args.user_history,
        root / args.recommendations,
        root / args.metadata,
        root / args.metrics,
        benchmark,
    )
    write_json(root / args.output, result)
    print(f"Streamlit final validation: {result['status']}")
    for warning in result["warnings"]:
        print(f"Warning: {warning}")
    for error in result["errors"]:
        print(f"Error: {error}", file=sys.stderr)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
