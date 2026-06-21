"""Assemble the Milestone 12 final validation manifest."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.final_artifact_utils import FinalArtifactError, load_json, repo_root_from, source_record, write_json


REQUIRED_ARTIFACTS = (
    "results/movielens-1m/movielens_1m_manifest.json",
    "results/movielens-1m/normalized/dataset_stats.json",
    "results/movielens-1m/split/split_stats.json",
    "results/movielens-1m/method_comparison.csv",
    "results/movielens-1m/stage_metrics.json",
    "results/movielens-1m/cosine/metrics.json",
    "results/movielens-1m/cooccurrence/metrics.json",
    "target/final-report-data/final_report_facts.json",
    "target/final-validation/streamlit_movielens_1m_validation.json",
)


def _run_git(root: Path, args: Sequence[str]) -> tuple[int, str, str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def build_final_validation_manifest(repo_root: Path | str, output: Path | str) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []

    artifact_records = []
    for relative in REQUIRED_ARTIFACTS:
        record = source_record(root / relative, root, "required final validation artifact")
        artifact_records.append(record)
        if not record["exists"]:
            errors.append(f"Missing required artifact: {relative}")

    manifest_path = root / "results/movielens-1m/movielens_1m_manifest.json"
    streamlit_path = root / "target/final-validation/streamlit_movielens_1m_validation.json"
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        expected = {
            "completion_status": "completed",
            "dataset_name": "MovieLens 1M",
            "dataset_role": "primary-experimental",
            "source_has_timestamps": True,
            "split_method": "leave-one-out-by-exact-timestamp",
            "train_test_overlap_rows": 0,
            "watched_recommendation_violations": 0,
        }
        for key, value in expected.items():
            if manifest.get(key) != value:
                errors.append(f"Manifest {key} expected {value!r}, found {manifest.get(key)!r}")
    if streamlit_path.exists():
        streamlit = load_json(streamlit_path)
        if streamlit.get("status") != "passed":
            errors.append("Streamlit final validation status is not passed.")

    diff_check_code, diff_check_out, diff_check_err = _run_git(
        root,
        [
            "-c",
            "core.autocrlf=true",
            "-c",
            "core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol",
            "diff",
            "--check",
        ],
    )
    if diff_check_code != 0:
        errors.append("git diff --check failed.")

    ignored_checks: dict[str, bool] = {}
    for path in ("data/raw/movielens-1m", "results/movielens-1m", "target/final-report-data", "target/final-validation"):
        code, _out, _err = _run_git(root, ["check-ignore", path])
        ignored_checks[path] = code == 0
        if code != 0:
            warnings.append(f"{path} is not ignored by git check-ignore.")

    command_results_path = root / "target/final-validation/command_results.json"
    command_results: Any = {"status": "not_available", "message": "No wrapper command results file found."}
    if command_results_path.exists():
        command_results = load_json(command_results_path)

    result = {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "warnings": warnings,
        "artifacts": artifact_records,
        "git_diff_check": {
            "exit_code": diff_check_code,
            "stdout": diff_check_out,
            "stderr": diff_check_err,
        },
        "ignored_paths": ignored_checks,
        "command_results": command_results,
    }
    write_json(output, result)
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    root = repo_root_from()
    parser = argparse.ArgumentParser(description="Build final validation manifest.")
    parser.add_argument("--repo-root", default=str(root), help="Repository root.")
    parser.add_argument("--output", default="target/final-validation/final_validation_manifest.json", help="Output JSON path.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    try:
        result = build_final_validation_manifest(root, root / args.output)
    except (FinalArtifactError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Final validation manifest: {result['status']}")
    for warning in result["warnings"]:
        print(f"Warning: {warning}")
    for error in result["errors"]:
        print(f"Error: {error}", file=sys.stderr)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
