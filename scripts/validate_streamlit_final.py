"""Validate MovieLens Streamlit demo inputs without mutating Hadoop artifacts."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo import artifact_paths
from demo.data_loader import build_demo_bundle, build_sample_bundle, load_benchmark_results
from demo.models import DemoValidationError
from demo.service import validate_bundle_integrity
from scripts.final_artifact_utils import load_json, repo_root_from, relative_path, write_json


def _count_validation_categories(errors: Sequence[str]) -> dict[str, int]:
    return {
        "watched_recommendation_violations": sum(1 for item in errors if "watched movie" in item),
        "duplicate_recommendation_violations": sum(1 for item in errors if "duplicates movie" in item),
        "ordering_violations": sum(1 for item in errors if "order" in item),
        "invalid_score_violations": sum(1 for item in errors if "score" in item and "order" not in item),
    }


def _bundle_fields(bundle: Any) -> dict[str, Any]:
    referenced_movie_ids = {
        item.movie_id
        for profile in bundle.users.values()
        for item in [*profile.watched, *profile.recommendations]
    }
    metadata_ids = set(bundle.metadata)
    unknown_metadata = sorted(referenced_movie_ids - metadata_ids)
    coverage = None
    if referenced_movie_ids:
        coverage = (len(referenced_movie_ids) - len(unknown_metadata)) / len(referenced_movie_ids)
    validation_errors = validate_bundle_integrity(bundle)
    categories = _count_validation_categories(validation_errors)
    return {
        "users_loaded": len(bundle.users),
        "watched_ratings_loaded": sum(len(profile.watched) for profile in bundle.users.values()),
        "recommendation_users_loaded": sum(1 for profile in bundle.users.values() if profile.recommendations),
        "recommendations_loaded": sum(len(profile.recommendations) for profile in bundle.users.values()),
        "metadata_records_loaded": len(bundle.metadata),
        "metadata_coverage": coverage,
        "unknown_metadata_movies": unknown_metadata,
        **categories,
        "integrity_errors": validation_errors,
    }


def _comparison_loaded(path: Path) -> bool:
    if not path.is_file():
        return False
    with path.open("r", encoding="utf-8", newline="") as input_file:
        rows = [dict(row) for row in csv.DictReader(input_file)]
    return {row.get("method") for row in rows} >= {"cosine", "cooccurrence"}


def validate_streamlit_artifacts(
    repo_root: Path | str,
    method: str = "cosine",
    benchmark: Path | str | None = None,
    app_test_passed: bool | None = None,
    health_check_passed: bool | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    defaults = artifact_paths.MOVIELENS_DEFAULTS_BY_METHOD[method]
    paths = {key: root / value for key, value in defaults.items()}
    errors: list[str] = []
    warnings: list[str] = []
    result: dict[str, Any] = {
        "dataset_name": "MovieLens 1M",
        "method": method,
        "source_mode": "movielens-1m-primary-artifacts",
        "inputs": {key: relative_path(path, root) for key, path in paths.items()},
        "metrics_loaded": False,
        "comparison_loaded": False,
        "benchmark_loaded": False,
        "app_test_passed": app_test_passed,
        "health_check_passed": health_check_passed,
        "real_movielens_artifacts_valid": False,
        "errors": errors,
        "warnings": warnings,
    }

    try:
        build_sample_bundle()
    except (DemoValidationError, OSError) as exc:
        warnings.append(f"Bundled sample validation failed: {exc}")

    try:
        bundle = build_demo_bundle(
            user_history_path=paths["user_history"],
            recommendations_path=paths["recommendations"],
            evaluation_metrics_path=paths["evaluation"],
            benchmark_results_path=None,
            movie_metadata_path=paths["metadata"],
            manifest_path=paths["manifest"],
            dataset_type="movielens",
        )
        result.update(_bundle_fields(bundle))
    except (DemoValidationError, OSError) as exc:
        errors.append(f"MovieLens artifact validation failed: {exc}")
        result.update(
            {
                "users_loaded": 0,
                "watched_ratings_loaded": 0,
                "recommendation_users_loaded": 0,
                "recommendations_loaded": 0,
                "metadata_records_loaded": 0,
                "metadata_coverage": None,
                "unknown_metadata_movies": [],
                "watched_recommendation_violations": 0,
                "duplicate_recommendation_violations": 0,
                "ordering_violations": 0,
                "invalid_score_violations": 0,
            }
        )

    if paths["evaluation"].is_file():
        try:
            metrics = load_json(paths["evaluation"])
            result["metrics_loaded"] = True
            result["train_test_overlap_rows"] = metrics.get("train_test_overlap_rows")
        except (OSError, ValueError) as exc:
            errors.append(f"MovieLens metrics validation failed: {exc}")
            result["train_test_overlap_rows"] = None
    else:
        errors.append(f"MovieLens metrics file is missing: {relative_path(paths['evaluation'], root)}")
        result["train_test_overlap_rows"] = None

    try:
        result["comparison_loaded"] = _comparison_loaded(paths["method_comparison"])
        if not result["comparison_loaded"]:
            warnings.append("MovieLens method comparison is unavailable or incomplete.")
    except (OSError, csv.Error) as exc:
        errors.append(f"MovieLens method comparison validation failed: {exc}")

    benchmark_path = Path(benchmark) if benchmark is not None else paths["benchmark"]
    if benchmark_path.is_file():
        try:
            load_benchmark_results(benchmark_path)
            result["benchmark_loaded"] = True
        except (DemoValidationError, OSError) as exc:
            warnings.append(f"Synthetic benchmark CSV validation failed: {exc}")
    else:
        warnings.append("Synthetic benchmark CSV is unavailable; this is non-fatal for MovieLens demo validation.")

    result["real_movielens_artifacts_valid"] = (
        not errors
        and result.get("metrics_loaded") is True
        and result.get("watched_recommendation_violations") == 0
        and result.get("duplicate_recommendation_violations") == 0
        and result.get("ordering_violations") == 0
        and result.get("invalid_score_violations") == 0
        and result.get("train_test_overlap_rows") == 0
    )
    result["status"] = "passed" if result["real_movielens_artifacts_valid"] else "failed"
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    root = repo_root_from()
    parser = argparse.ArgumentParser(description="Validate final Streamlit MovieLens artifacts.")
    parser.add_argument("--repo-root", default=str(root), help="Repository root.")
    parser.add_argument("--method", choices=["cosine", "cooccurrence"], default="cosine")
    parser.add_argument("--benchmark", default="target/scalability-benchmark/benchmark_results.csv")
    parser.add_argument("--output", default="target/final-validation/streamlit_movielens_1m_validation.json")
    parser.add_argument("--app-test-passed", action="store_true")
    parser.add_argument("--health-check-passed", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    benchmark = root / args.benchmark if args.benchmark else None
    result = validate_streamlit_artifacts(
        root,
        method=args.method,
        benchmark=benchmark,
        app_test_passed=True if args.app_test_passed else None,
        health_check_passed=True if args.health_check_passed else None,
    )
    write_json(root / args.output, result)
    print(f"Streamlit MovieLens validation: {result['status']}")
    for warning in result["warnings"]:
        print(f"Warning: {warning}")
    for error in result["errors"]:
        print(f"Error: {error}", file=sys.stderr)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
