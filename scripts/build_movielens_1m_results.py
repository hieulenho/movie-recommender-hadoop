"""Build MovieLens 1M comparison and manifest artifacts from completed outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import movielens_1m_pipeline as pipeline


class MovieLensResultsError(Exception):
    """Raised when MovieLens result artifacts are incomplete."""


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise MovieLensResultsError(f"Required JSON is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _stage_seconds(run_dir: Path, stage: str) -> float | None:
    path = run_dir / "logs" / "stage-manifests" / f"{stage}.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    value = data.get("elapsed_seconds")
    return float(value) if isinstance(value, (int, float)) else None


def _method_result(run_dir: Path, method: str) -> dict[str, object]:
    specific = pipeline.method_paths(run_dir, method)
    metrics = _required_json(specific["metrics_json"])
    return {
        "method": method,
        "status": "completed",
        "stage_seconds": {
            "similarity": _stage_seconds(run_dir, f"{method}_similarity"),
            "scoring": _stage_seconds(run_dir, f"{method}_scoring"),
            "top_k": _stage_seconds(run_dir, f"{method}_top_k"),
            "evaluation": _stage_seconds(run_dir, f"{method}_evaluation"),
        },
        "metrics": metrics,
    }


def _load_parameters(run_dir: Path, config: Mapping[str, object] | None = None) -> dict[str, int]:
    manifest_path = run_dir / "movielens_1m_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        parameters = manifest.get("parameters")
        if isinstance(parameters, Mapping):
            return {
                "top_l": int(parameters.get("top_l", pipeline.DEFAULT_TOP_L)),
                "top_k": int(parameters.get("top_k", pipeline.DEFAULT_TOP_K)),
                "min_common_users": int(parameters.get("min_common_users", pipeline.DEFAULT_MIN_COMMON_USERS)),
                "relevance_threshold": int(parameters.get("relevance_threshold", pipeline.DEFAULT_RELEVANCE_THRESHOLD)),
                "reducers": int(parameters.get("reducers", pipeline.DEFAULT_REDUCERS)),
            }
    if config:
        return {
            "top_l": int(config.get("top_l", pipeline.DEFAULT_TOP_L)),
            "top_k": int(config.get("top_k", pipeline.DEFAULT_TOP_K)),
            "min_common_users": int(config.get("min_common_users", pipeline.DEFAULT_MIN_COMMON_USERS)),
            "relevance_threshold": int(config.get("relevance_threshold", pipeline.DEFAULT_RELEVANCE_THRESHOLD)),
            "reducers": int(config.get("reducers", pipeline.DEFAULT_REDUCERS)),
        }
    return {
        "top_l": pipeline.DEFAULT_TOP_L,
        "top_k": pipeline.DEFAULT_TOP_K,
        "min_common_users": pipeline.DEFAULT_MIN_COMMON_USERS,
        "relevance_threshold": pipeline.DEFAULT_RELEVANCE_THRESHOLD,
        "reducers": pipeline.DEFAULT_REDUCERS,
    }


def build_movielens_1m_results(run_dir: Path | str, config: Mapping[str, object] | None = None) -> dict[str, object]:
    root = Path(run_dir)
    repo_root = pipeline.repo_root_from()
    paths = pipeline.build_paths(root)
    dataset_stats = _required_json(paths["dataset_stats"])
    split_stats = _required_json(paths["split_stats"])
    parameters = _load_parameters(root, config)
    method_results = {
        "common": {
            "user_history_seconds": _stage_seconds(root, "user_history"),
            "pair_statistics_seconds": _stage_seconds(root, "pair_statistics"),
        },
        "cosine": _method_result(root, "cosine"),
        "cooccurrence": _method_result(root, "cooccurrence"),
    }
    rows = pipeline.build_method_comparison_rows(method_results, dataset_stats, split_stats, parameters)
    pipeline.write_method_comparison(rows, paths["method_comparison"])

    stage_results = []
    for manifest_file in sorted((root / "logs" / "stage-manifests").glob("*.json")) if (root / "logs" / "stage-manifests").is_dir() else []:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        stage_results.append(
            pipeline.StageResult(
                stage=str(data.get("stage", manifest_file.stem)),
                status=str(data.get("status", "unknown")),
                elapsed_seconds=float(data.get("elapsed_seconds", 0.0) or 0.0),
                output_rows=int(data.get("output_row_count", 0) or 0),
                output_bytes=int(data.get("output_bytes", 0) or 0),
                manifest_path=manifest_file,
            )
        )
    pipeline.write_json(paths["stage_metrics"], pipeline.build_stage_metrics(stage_results, repo_root))
    manifest = pipeline.build_full_manifest(paths, dataset_stats, split_stats, rows, stage_results, parameters, repo_root)
    pipeline.write_json(paths["manifest"], manifest)
    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build MovieLens 1M result summaries.")
    parser.add_argument("--run-dir", default="results/movielens-1m")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        manifest = build_movielens_1m_results(args.run_dir)
    except (MovieLensResultsError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False))
    return 0 if manifest.get("completion_status") == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
