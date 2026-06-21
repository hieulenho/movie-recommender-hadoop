"""Run the primary MovieLens 1M Hadoop experiment workflow."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Iterable, Mapping, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import evaluate_recommendations
from scripts import preprocess_movielens_1m
from scripts import split_movielens_1m


METHODS = ("cosine", "cooccurrence")
DATASET_NAME = "MovieLens 1M"
DATASET_ROLE = "primary-experimental"
DEFAULT_TOP_L = 50
DEFAULT_TOP_K = 10
DEFAULT_MIN_COMMON_USERS = 5
DEFAULT_RELEVANCE_THRESHOLD = 4
DEFAULT_REDUCERS = 4
OWNERSHIP_MARKER = ".movielens-1m-owned"
STAGE_ORDER = (
    "preprocess",
    "split",
    "user_history",
    "pair_statistics",
    "cosine_similarity",
    "cosine_scoring",
    "cosine_top_k",
    "cosine_evaluation",
    "cooccurrence_similarity",
    "cooccurrence_scoring",
    "cooccurrence_top_k",
    "cooccurrence_evaluation",
    "results",
)
METHOD_COMPARISON_HEADER = [
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


class MovieLensPipelineError(Exception):
    """Fatal MovieLens pipeline error."""


@dataclass(frozen=True)
class StageResult:
    stage: str
    status: str
    elapsed_seconds: float
    output_rows: int
    output_bytes: int
    manifest_path: Path


def repo_root_from() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_to_repo(path: Path | str, repo_root: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return f"external/{resolved.name}"


def write_json(path: Path | str, payload: object) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def read_json(path: Path | str) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_paths(output_dir: Path | str) -> dict[str, Path]:
    root = Path(output_dir)
    return {
        "output_dir": root,
        "marker": root / OWNERSHIP_MARKER,
        "normalized_dir": root / "normalized",
        "ratings_with_timestamp": root / "normalized" / "ratings_with_timestamp.csv",
        "movie_metadata": root / "normalized" / "movie_metadata.csv",
        "dataset_stats": root / "normalized" / "dataset_stats.json",
        "split_dir": root / "split",
        "train_csv": root / "split" / "train_ratings.csv",
        "test_csv": root / "split" / "test_ratings.csv",
        "test_with_timestamp": root / "split" / "test_ratings_with_timestamp.csv",
        "split_stats": root / "split" / "split_stats.json",
        "common_dir": root / "common",
        "user_history_dir": root / "common" / "user-history",
        "pair_statistics_dir": root / "common" / "pair-statistics",
        "logs_dir": root / "logs",
        "stage_manifest_dir": root / "logs" / "stage-manifests",
        "report_artifacts_dir": root / "report-artifacts",
        "method_comparison": root / "method_comparison.csv",
        "stage_metrics": root / "stage_metrics.json",
        "manifest": root / "movielens_1m_manifest.json",
    }


def method_paths(output_dir: Path | str, method: str) -> dict[str, Path]:
    root = Path(output_dir) / method
    return {
        "method_dir": root,
        "similarity_dir": root / "similarity",
        "raw_predictions_dir": root / "raw-predictions",
        "recommendations_dir": root / "recommendations",
        "raw_predictions_file": root / "raw_predictions.txt",
        "recommendations_file": root / "recommendations.txt",
        "metrics_json": root / "metrics.json",
        "metrics_csv": root / "metrics.csv",
        "per_user_metrics": root / "per_user_metrics.csv",
    }


def ensure_results_output_path(output_dir: Path, repo_root: Path) -> None:
    resolved = output_dir.resolve()
    results_root = (repo_root / "results").resolve()
    try:
        resolved.relative_to(results_root)
    except ValueError as exc:
        raise MovieLensPipelineError("Output directory must be under results/.") from exc
    if resolved == results_root:
        raise MovieLensPipelineError("Output directory must be a results/ subdirectory.")


def prepare_output_dir(output_dir: Path, repo_root: Path, resume: bool) -> dict[str, Path]:
    ensure_results_output_path(output_dir, repo_root)
    paths = build_paths(output_dir)
    if output_dir.exists():
        if not output_dir.is_dir():
            raise MovieLensPipelineError(f"Output path exists and is not a directory: {output_dir}")
        if any(output_dir.iterdir()) and not paths["marker"].exists():
            raise MovieLensPipelineError(f"Refusing to overwrite unowned output directory: {output_dir}")
        if not resume:
            shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths["marker"].write_text("owned by scripts/movielens_1m_pipeline.py\n", encoding="utf-8")
    for key in ("normalized_dir", "split_dir", "common_dir", "logs_dir", "stage_manifest_dir", "report_artifacts_dir"):
        paths[key].mkdir(parents=True, exist_ok=True)
    return paths


def iter_part_files(path: Path | str) -> list[Path]:
    source = Path(path)
    if source.is_file():
        return [source]
    if not source.exists():
        return []
    return sorted(
        [
            item
            for item in source.iterdir()
            if item.is_file()
            and item.name.startswith("part-")
            and item.name != "_SUCCESS"
            and not item.name.startswith(".")
            and not item.name.endswith(".crc")
        ],
        key=lambda item: item.name,
    )


def combine_part_files(source_dir: Path | str, destination: Path | str) -> None:
    parts = iter_part_files(source_dir)
    if not parts:
        raise MovieLensPipelineError(f"No Hadoop part files found under {source_dir}")
    output = Path(destination)
    with output.open("w", encoding="utf-8", newline="") as output_file:
        for part_file in parts:
            with part_file.open("r", encoding="utf-8", errors="replace") as input_file:
                shutil.copyfileobj(input_file, output_file)


def count_output_rows(path: Path | str) -> int:
    source = Path(path)
    if source.is_file():
        files = [source]
    else:
        files = iter_part_files(source)
    rows = 0
    for file_path in files:
        with file_path.open("r", encoding="utf-8", errors="replace") as input_file:
            rows += sum(1 for line in input_file if line.strip())
    return rows


def count_output_bytes(path: Path | str) -> int:
    source = Path(path)
    if source.is_file():
        return source.stat().st_size
    total = 0
    for file_path in iter_part_files(source):
        total += file_path.stat().st_size
    return total


def file_signature(path: Path | str, repo_root: Path) -> dict[str, object]:
    source = Path(path)
    if source.is_file():
        return {
            "path": relative_to_repo(source, repo_root),
            "sha256": sha256_file(source),
            "bytes": source.stat().st_size,
        }
    return {
        "path": relative_to_repo(source, repo_root),
        "parts": [
            {"name": part.name, "sha256": sha256_file(part), "bytes": part.stat().st_size}
            for part in iter_part_files(source)
        ],
    }


def output_exists(path: Path | str) -> bool:
    source = Path(path)
    return source.is_file() or bool(iter_part_files(source))


def manifest_matches(
    manifest_path: Path,
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    parameters: Mapping[str, object],
    repo_root: Path,
) -> bool:
    if not manifest_path.is_file():
        return False
    try:
        manifest = read_json(manifest_path)
    except (OSError, json.JSONDecodeError):
        return False
    if manifest.get("status") != "completed":
        return False
    if manifest.get("parameters") != dict(parameters):
        return False
    expected_inputs = [file_signature(path, repo_root) for path in inputs]
    if manifest.get("input_signatures") != expected_inputs:
        return False
    return all(output_exists(path) for path in outputs)


def clean_outputs(outputs: Sequence[Path], repo_root: Path) -> None:
    results_root = (repo_root / "results").resolve()
    for output in outputs:
        resolved = output.resolve()
        try:
            resolved.relative_to(results_root)
        except ValueError as exc:
            del exc
            continue
        if resolved == results_root:
            raise MovieLensPipelineError("Refusing to delete results root.")
        if output.is_dir():
            shutil.rmtree(output)
        elif output.exists():
            output.unlink()


def stage_manifest_path(paths: Mapping[str, Path], stage: str) -> Path:
    return paths["stage_manifest_dir"] / f"{stage}.json"


def write_stage_manifest(
    paths: Mapping[str, Path],
    stage: str,
    status: str,
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    parameters: Mapping[str, object],
    started_at: float,
    elapsed: float,
    exit_code: int,
    repo_root: Path,
    error_summary: str = "",
) -> StageResult:
    output_rows = sum(count_output_rows(path) for path in outputs if output_exists(path))
    output_bytes = sum(count_output_bytes(path) for path in outputs if output_exists(path))
    manifest = {
        "stage": stage,
        "status": status,
        "input_signatures": [file_signature(path, repo_root) for path in inputs],
        "parameters": dict(parameters),
        "output_paths": [relative_to_repo(path, repo_root) for path in outputs],
        "start_time_epoch_seconds": started_at,
        "completion_time_epoch_seconds": started_at + elapsed,
        "elapsed_seconds": elapsed,
        "output_row_count": output_rows,
        "output_bytes": output_bytes,
        "exit_code": exit_code,
        "error_summary": error_summary,
    }
    manifest_path = stage_manifest_path(paths, stage)
    write_json(manifest_path, manifest)
    return StageResult(stage, status, elapsed, output_rows, output_bytes, manifest_path)


def stage_should_run(
    paths: Mapping[str, Path],
    stage: str,
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    parameters: Mapping[str, object],
    repo_root: Path,
    resume: bool,
    forced_stages: set[str],
) -> bool:
    if stage in forced_stages:
        return True
    if not resume:
        return True
    return not manifest_matches(stage_manifest_path(paths, stage), inputs, outputs, parameters, repo_root)


def run_external_stage(
    paths: Mapping[str, Path],
    stage: str,
    command: Sequence[str],
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    parameters: Mapping[str, object],
    repo_root: Path,
    resume: bool,
    forced_stages: set[str],
) -> StageResult:
    if not stage_should_run(paths, stage, inputs, outputs, parameters, repo_root, resume, forced_stages):
        manifest = read_json(stage_manifest_path(paths, stage))
        return StageResult(stage, "skipped", float(manifest.get("elapsed_seconds", 0.0)), int(manifest.get("output_row_count", 0)), int(manifest.get("output_bytes", 0)), stage_manifest_path(paths, stage))
    clean_outputs(outputs, repo_root)
    stdout_path = paths["logs_dir"] / f"{stage}.stdout.log"
    stderr_path = paths["logs_dir"] / f"{stage}.stderr.log"
    started_at = time.time()
    start = time.perf_counter()
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        result = subprocess.run(command, cwd=repo_root, text=True, stdout=stdout, stderr=stderr, check=False)
    elapsed = time.perf_counter() - start
    if result.returncode != 0:
        write_stage_manifest(paths, stage, "failed", inputs, outputs, parameters, started_at, elapsed, result.returncode, repo_root, f"See {relative_to_repo(stderr_path, repo_root)}")
        raise MovieLensPipelineError(f"Stage {stage} failed with exit code {result.returncode}. See {relative_to_repo(stderr_path, repo_root)}")
    return write_stage_manifest(paths, stage, "completed", inputs, outputs, parameters, started_at, elapsed, 0, repo_root)


def run_python_stage(
    paths: Mapping[str, Path],
    stage: str,
    action: object,
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    parameters: Mapping[str, object],
    repo_root: Path,
    resume: bool,
    forced_stages: set[str],
) -> StageResult:
    if not stage_should_run(paths, stage, inputs, outputs, parameters, repo_root, resume, forced_stages):
        manifest = read_json(stage_manifest_path(paths, stage))
        return StageResult(stage, "skipped", float(manifest.get("elapsed_seconds", 0.0)), int(manifest.get("output_row_count", 0)), int(manifest.get("output_bytes", 0)), stage_manifest_path(paths, stage))
    clean_outputs(outputs, repo_root)
    started_at = time.time()
    start = time.perf_counter()
    try:
        action()  # type: ignore[operator]
    except Exception as exc:
        elapsed = time.perf_counter() - start
        write_stage_manifest(paths, stage, "failed", inputs, outputs, parameters, started_at, elapsed, 1, repo_root, str(exc))
        raise
    elapsed = time.perf_counter() - start
    return write_stage_manifest(paths, stage, "completed", inputs, outputs, parameters, started_at, elapsed, 0, repo_root)


def build_java_classpath(repo_root: Path, paths: Mapping[str, Path], resume: bool, forced_stages: set[str]) -> str:
    package_result = run_external_stage(
        paths,
        "maven_package",
        ["mvn", "-q", "-DskipTests", "package"],
        [repo_root / "pom.xml"],
        [repo_root / "target" / "classes"],
        {"skip_tests": True},
        repo_root,
        resume,
        forced_stages,
    )
    del package_result
    classpath_file = paths["logs_dir"] / "runtime-classpath.txt"
    run_external_stage(
        paths,
        "maven_classpath",
        ["mvn", "-q", "dependency:build-classpath", "-Dmdep.includeScope=runtime", f"-Dmdep.outputFile={classpath_file}"],
        [repo_root / "pom.xml"],
        [classpath_file],
        {"scope": "runtime"},
        repo_root,
        resume,
        forced_stages,
    )
    runtime_classpath = classpath_file.read_text(encoding="utf-8").strip()
    return f"{repo_root / 'target' / 'classes'}:{runtime_classpath}"


def common_stage_commands(java_classpath: str, paths: Mapping[str, Path], parameters: Mapping[str, int]) -> list[tuple[str, list[str], list[Path], list[Path]]]:
    reducers = str(parameters["reducers"])
    return [
        (
            "user_history",
            ["java", "-cp", java_classpath, "com.movierecommender.history.UserHistoryJob", "--local", "--reducers", reducers, str(paths["train_csv"]), str(paths["user_history_dir"])],
            [paths["train_csv"]],
            [paths["user_history_dir"]],
        ),
        (
            "pair_statistics",
            ["java", "-cp", java_classpath, "com.movierecommender.pairs.ItemPairStatisticsJob", "--local", "--reducers", reducers, str(paths["user_history_dir"]), str(paths["pair_statistics_dir"])],
            [paths["user_history_dir"]],
            [paths["pair_statistics_dir"]],
        ),
    ]


def method_stage_commands(
    method: str,
    java_classpath: str,
    paths: Mapping[str, Path],
    specific: Mapping[str, Path],
    parameters: Mapping[str, int],
) -> list[tuple[str, list[str], list[Path], list[Path]]]:
    reducers = str(parameters["reducers"])
    return [
        (
            f"{method}_similarity",
            ["java", "-cp", java_classpath, "com.movierecommender.similarity.ItemSimilarityPipeline", "--local", "--method", method, "--min-common-users", str(parameters["min_common_users"]), "--top-l", str(parameters["top_l"]), "--reducers", reducers, str(paths["pair_statistics_dir"]), str(specific["similarity_dir"])],
            [paths["pair_statistics_dir"]],
            [specific["similarity_dir"]],
        ),
        (
            f"{method}_scoring",
            ["java", "-cp", java_classpath, "com.movierecommender.scoring.RecommendationScoringPipeline", "--local", "--reducers", reducers, str(paths["user_history_dir"]), str(specific["similarity_dir"]), str(specific["raw_predictions_dir"])],
            [paths["user_history_dir"], specific["similarity_dir"]],
            [specific["raw_predictions_dir"]],
        ),
        (
            f"{method}_top_k",
            ["java", "-cp", java_classpath, "com.movierecommender.recommendation.TopKRecommendationJob", "--local", "--reducers", reducers, "--top-k", str(parameters["top_k"]), str(paths["user_history_dir"]), str(specific["raw_predictions_dir"]), str(specific["recommendations_dir"])],
            [paths["user_history_dir"], specific["raw_predictions_dir"]],
            [specific["recommendations_dir"]],
        ),
    ]


def command_uses_test_input(command: Sequence[str], test_path: Path | str) -> bool:
    test_text = str(test_path)
    return any(argument == test_text for argument in command)


def estimate_pair_contributions(train_csv: Path | str) -> int:
    by_user: dict[int, int] = {}
    with Path(train_csv).open("r", encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames != ["userId", "movieId", "rating", "date"]:
            raise MovieLensPipelineError("Train CSV header must be: userId,movieId,rating,date")
        for row in reader:
            user_id = int(row["userId"])
            by_user[user_id] = by_user.get(user_id, 0) + 1
    return sum((count * (count - 1)) // 2 for count in by_user.values())


def build_preflight_report(paths: Mapping[str, Path], parameters: Mapping[str, int], output_dir: Path) -> dict[str, object]:
    dataset_stats = read_json(paths["dataset_stats"])
    split_stats = read_json(paths["split_stats"])
    disk = shutil.disk_usage(output_dir.parent)
    return {
        "dataset_name": DATASET_NAME,
        "dataset_role": DATASET_ROLE,
        "accepted_ratings": dataset_stats.get("rating_rows"),
        "train_rows": split_stats.get("train_rows"),
        "test_rows": split_stats.get("test_rows"),
        "users": split_stats.get("users"),
        "rated_movies": dataset_stats.get("distinct_rated_movies"),
        "estimated_mapper_pair_contributions": estimate_pair_contributions(paths["train_csv"]),
        "available_disk_bytes": disk.free,
        "estimated_output_location": output_dir.as_posix(),
        "parameters": dict(parameters),
        "reducers": parameters["reducers"],
        "warning": "The pair-statistics stage may be the largest Hadoop stage.",
    }


def format_metric(value: object) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value_float = float(value)
        if not math.isfinite(value_float):
            return ""
        return f"{value_float:.10f}"
    return str(value)


def format_seconds(value: object) -> str:
    if value is None or value == "":
        return ""
    value_float = float(value)
    if not math.isfinite(value_float):
        return ""
    return f"{value_float:.6f}"


def build_method_comparison_rows(
    method_results: Mapping[str, Mapping[str, object]],
    dataset_stats: Mapping[str, object],
    split_stats: Mapping[str, object],
    parameters: Mapping[str, int],
) -> list[dict[str, object]]:
    rows = []
    common_user_history = method_results.get("common", {}).get("user_history_seconds")
    common_pair_statistics = method_results.get("common", {}).get("pair_statistics_seconds")
    for method in METHODS:
        result = method_results.get(method, {})
        metrics = result.get("metrics", {})
        if not isinstance(metrics, Mapping):
            metrics = {}
        stage_seconds = result.get("stage_seconds", {})
        if not isinstance(stage_seconds, Mapping):
            stage_seconds = {}
        total_seconds = sum(
            float(value)
            for value in [
                common_user_history,
                common_pair_statistics,
                stage_seconds.get("similarity"),
                stage_seconds.get("scoring"),
                stage_seconds.get("top_k"),
                stage_seconds.get("evaluation"),
            ]
            if isinstance(value, (int, float)) and math.isfinite(float(value))
        )
        rows.append(
            {
                "method": method,
                "dataset": DATASET_NAME,
                "ratingsRows": dataset_stats.get("rating_rows", ""),
                "users": dataset_stats.get("distinct_users", ""),
                "ratedMovies": dataset_stats.get("distinct_rated_movies", ""),
                "metadataMovies": dataset_stats.get("metadata_movies", ""),
                "trainRows": split_stats.get("train_rows", ""),
                "testRows": split_stats.get("test_rows", ""),
                "topL": parameters["top_l"],
                "topK": parameters["top_k"],
                "minCommonUsers": parameters["min_common_users"],
                "relevanceThreshold": parameters["relevance_threshold"],
                "matchedPredictions": metrics.get("matched_test_predictions", ""),
                "missingPredictions": metrics.get("missing_test_predictions", ""),
                "predictionCoverage": format_metric(metrics.get("prediction_coverage")),
                "mae": format_metric(metrics.get("mae")),
                "rmse": format_metric(metrics.get("rmse")),
                "rankingEligibleUsers": metrics.get("ranking_eligible_users", ""),
                "rankingHits": metrics.get("ranking_hits", ""),
                "recommendationUsers": metrics.get("users_with_recommendations", ""),
                "recommendationUserCoverage": format_metric(metrics.get("recommendation_user_coverage")),
                "precisionAtK": format_metric(metrics.get("precision_at_k")),
                "recallAtK": format_metric(metrics.get("recall_at_k")),
                "hitRateAtK": format_metric(metrics.get("hit_rate_at_k")),
                "ndcgAtK": format_metric(metrics.get("ndcg_at_k")),
                "mrrAtK": format_metric(metrics.get("mrr_at_k")),
                "userHistorySeconds": format_seconds(common_user_history),
                "pairStatisticsSeconds": format_seconds(common_pair_statistics),
                "similaritySeconds": format_seconds(stage_seconds.get("similarity")),
                "scoringSeconds": format_seconds(stage_seconds.get("scoring")),
                "topKSeconds": format_seconds(stage_seconds.get("top_k")),
                "evaluationSeconds": format_seconds(stage_seconds.get("evaluation")),
                "totalPipelineSeconds": format_seconds(total_seconds),
                "status": result.get("status", ""),
            }
        )
    return rows


def write_method_comparison(rows: Sequence[Mapping[str, object]], output_path: Path | str) -> None:
    with Path(output_path).open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=METHOD_COMPARISON_HEADER, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in METHOD_COMPARISON_HEADER})


def evaluation_stage(
    method: str,
    paths: Mapping[str, Path],
    specific: Mapping[str, Path],
    parameters: Mapping[str, int],
    repo_root: Path,
    resume: bool,
    forced_stages: set[str],
) -> StageResult:
    stage = f"{method}_evaluation"

    def action() -> None:
        combine_part_files(specific["raw_predictions_dir"], specific["raw_predictions_file"])
        combine_part_files(specific["recommendations_dir"], specific["recommendations_file"])
        evaluate_recommendations.run_evaluation(
            paths["train_csv"],
            paths["test_csv"],
            specific["raw_predictions_file"],
            specific["recommendations_file"],
            specific["metrics_json"],
            specific["metrics_csv"],
            specific["per_user_metrics"],
            parameters["top_k"],
            parameters["relevance_threshold"],
        )

    return run_python_stage(
        paths,
        stage,
        action,
        [paths["train_csv"], paths["test_csv"], specific["raw_predictions_dir"], specific["recommendations_dir"]],
        [specific["raw_predictions_file"], specific["recommendations_file"], specific["metrics_json"], specific["metrics_csv"], specific["per_user_metrics"]],
        {"top_k": parameters["top_k"], "relevance_threshold": parameters["relevance_threshold"]},
        repo_root,
        resume,
        forced_stages,
    )


def build_full_manifest(
    paths: Mapping[str, Path],
    dataset_stats: Mapping[str, object],
    split_stats: Mapping[str, object],
    comparison_rows: Sequence[Mapping[str, object]],
    stage_results: Sequence[StageResult],
    parameters: Mapping[str, int],
    repo_root: Path,
) -> dict[str, object]:
    stage_map = {result.stage: result.status for result in stage_results}
    completed = all(row.get("status") == "completed" for row in comparison_rows)
    metrics_by_method = {method: read_json(method_paths(paths["output_dir"], method)["metrics_json"]) for method in METHODS if method_paths(paths["output_dir"], method)["metrics_json"].is_file()}
    return {
        "dataset_name": DATASET_NAME,
        "dataset_role": DATASET_ROLE,
        "dataset_type": "real-stable-benchmark",
        "source_has_timestamps": True,
        "source_files": ["ratings.dat", "movies.dat", "users.dat", "README"],
        "split_method": split_stats.get("split_method"),
        "timezone": split_stats.get("timezone"),
        "parameters": dict(parameters),
        "methods": list(METHODS),
        "total_ratings": dataset_stats.get("rating_rows"),
        "distinct_users": dataset_stats.get("distinct_users"),
        "distinct_rated_movies": dataset_stats.get("distinct_rated_movies"),
        "metadata_movies": dataset_stats.get("metadata_movies"),
        "train_rows": split_stats.get("train_rows"),
        "test_rows": split_stats.get("test_rows"),
        "train_test_overlap_rows": split_stats.get("train_test_overlap_rows"),
        "cosine_status": next((row.get("status") for row in comparison_rows if row.get("method") == "cosine"), "not_run"),
        "cooccurrence_status": next((row.get("status") for row in comparison_rows if row.get("method") == "cooccurrence"), "not_run"),
        "watched_recommendation_violations": max(int(metrics.get("watched_recommendations_found", 0)) for metrics in metrics_by_method.values()) if metrics_by_method else None,
        "artifact_locations": {
            "normalized": relative_to_repo(paths["normalized_dir"], repo_root),
            "split": relative_to_repo(paths["split_dir"], repo_root),
            "user_history": relative_to_repo(paths["user_history_dir"], repo_root),
            "pair_statistics": relative_to_repo(paths["pair_statistics_dir"], repo_root),
            "cosine_recommendations": relative_to_repo(method_paths(paths["output_dir"], "cosine")["recommendations_dir"], repo_root),
            "cooccurrence_recommendations": relative_to_repo(method_paths(paths["output_dir"], "cooccurrence")["recommendations_dir"], repo_root),
            "movie_metadata": relative_to_repo(paths["movie_metadata"], repo_root),
        },
        "stage_status": stage_map,
        "completion_status": "completed" if completed else "failed",
    }


def build_stage_metrics(stage_results: Sequence[StageResult], repo_root: Path) -> dict[str, object]:
    return {
        "dataset_name": DATASET_NAME,
        "stages": [
            {
                "stage": result.stage,
                "status": result.status,
                "elapsedSeconds": result.elapsed_seconds,
                "outputRows": result.output_rows,
                "outputBytes": result.output_bytes,
                "manifest": relative_to_repo(result.manifest_path, repo_root),
            }
            for result in stage_results
        ],
    }


def dependent_forced_stages(force_stage: str | None) -> set[str]:
    if not force_stage:
        return set()
    if force_stage not in STAGE_ORDER and force_stage not in {"maven_package", "maven_classpath"}:
        raise MovieLensPipelineError(f"Unknown ForceStage: {force_stage}")
    if force_stage in {"maven_package", "maven_classpath"}:
        return {force_stage}
    start_index = STAGE_ORDER.index(force_stage)
    return set(STAGE_ORDER[start_index:])


def run_workflow(args: argparse.Namespace) -> int:
    repo_root = repo_root_from()
    dataset_dir = Path(args.dataset_dir)
    if not dataset_dir.is_absolute():
        dataset_dir = repo_root / dataset_dir
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    parameters = {
        "top_l": args.top_l,
        "top_k": args.top_k,
        "min_common_users": args.min_common_users,
        "relevance_threshold": args.relevance_threshold,
        "reducers": args.reducers,
    }
    forced_stages = dependent_forced_stages(args.force_stage)
    paths = prepare_output_dir(output_dir, repo_root, args.resume or args.preflight_only)
    stage_results: list[StageResult] = []

    preprocess_params = {"strict_official_counts": True}
    stage_results.append(
        run_python_stage(
            paths,
            "preprocess",
            lambda: preprocess_movielens_1m.preprocess_movielens_1m(dataset_dir, paths["normalized_dir"], strict_official_counts=True, overwrite=True),
            [dataset_dir / "ratings.dat", dataset_dir / "movies.dat", dataset_dir / "users.dat"],
            [paths["ratings_with_timestamp"], paths["movie_metadata"], paths["dataset_stats"]],
            preprocess_params,
            repo_root,
            args.resume,
            forced_stages,
        )
    )
    stage_results.append(
        run_python_stage(
            paths,
            "split",
            lambda: split_movielens_1m.split_movielens_1m(paths["ratings_with_timestamp"], paths["split_dir"]),
            [paths["ratings_with_timestamp"]],
            [paths["train_csv"], paths["test_csv"], paths["test_with_timestamp"], paths["split_stats"]],
            {"split_method": split_movielens_1m.SPLIT_METHOD},
            repo_root,
            args.resume,
            forced_stages,
        )
    )

    preflight = build_preflight_report(paths, parameters, output_dir)
    write_json(paths["output_dir"] / "preflight.json", preflight)
    print(json.dumps(preflight, indent=2, sort_keys=True, allow_nan=False))
    if args.preflight_only:
        return 0

    java_classpath = build_java_classpath(repo_root, paths, args.resume, forced_stages)
    for stage, command, inputs, outputs in common_stage_commands(java_classpath, paths, parameters):
        if command_uses_test_input(command, paths["test_csv"]):
            raise MovieLensPipelineError(f"Internal error: {stage} command uses held-out test data.")
        stage_results.append(
            run_external_stage(paths, stage, command, inputs, outputs, parameters, repo_root, args.resume, forced_stages)
        )

    method_results: dict[str, Mapping[str, object]] = {
        "common": {
            "user_history_seconds": next(result.elapsed_seconds for result in stage_results if result.stage == "user_history"),
            "pair_statistics_seconds": next(result.elapsed_seconds for result in stage_results if result.stage == "pair_statistics"),
        }
    }
    for method in METHODS:
        specific = method_paths(paths["output_dir"], method)
        specific["method_dir"].mkdir(parents=True, exist_ok=True)
        stage_seconds: dict[str, float] = {}
        for stage, command, inputs, outputs in method_stage_commands(method, java_classpath, paths, specific, parameters):
            if command_uses_test_input(command, paths["test_csv"]):
                raise MovieLensPipelineError(f"Internal error: {stage} command uses held-out test data.")
            result = run_external_stage(paths, stage, command, inputs, outputs, parameters, repo_root, args.resume, forced_stages)
            stage_results.append(result)
            stage_seconds[stage.removeprefix(f"{method}_")] = result.elapsed_seconds
        eval_result = evaluation_stage(method, paths, specific, parameters, repo_root, args.resume, forced_stages)
        stage_results.append(eval_result)
        stage_seconds["evaluation"] = eval_result.elapsed_seconds
        method_results[method] = {
            "method": method,
            "status": "completed",
            "stage_seconds": stage_seconds,
            "metrics": read_json(specific["metrics_json"]),
        }

    dataset_stats = read_json(paths["dataset_stats"])
    split_stats = read_json(paths["split_stats"])
    comparison_rows = build_method_comparison_rows(method_results, dataset_stats, split_stats, parameters)
    write_method_comparison(comparison_rows, paths["method_comparison"])
    write_json(paths["stage_metrics"], build_stage_metrics(stage_results, repo_root))
    manifest = build_full_manifest(paths, dataset_stats, split_stats, comparison_rows, stage_results, parameters, repo_root)
    write_json(paths["manifest"], manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False))
    return 0 if manifest["completion_status"] == "completed" else 1


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the primary MovieLens 1M Hadoop workflow.")
    parser.add_argument("--dataset-dir", default="data/raw/movielens-1m/ml-1m")
    parser.add_argument("--output-dir", default="results/movielens-1m")
    parser.add_argument("--top-l", type=int, default=DEFAULT_TOP_L)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--min-common-users", type=int, default=DEFAULT_MIN_COMMON_USERS)
    parser.add_argument("--relevance-threshold", type=int, default=DEFAULT_RELEVANCE_THRESHOLD)
    parser.add_argument("--reducers", type=int, default=DEFAULT_REDUCERS)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--keep-intermediate", action="store_true", help="Reserved for compatibility; outputs are preserved by default.")
    parser.add_argument("--force-stage", default=None, help="Stage to rerun with dependent downstream stages.")
    return parser


def validate_args(args: argparse.Namespace) -> None:
    for name in ("top_l", "top_k", "min_common_users", "reducers"):
        if getattr(args, name) < 1:
            raise MovieLensPipelineError(f"{name.replace('_', '-')} must be at least 1.")
    if args.relevance_threshold < 1 or args.relevance_threshold > 5:
        raise MovieLensPipelineError("relevance-threshold must be from 1 through 5.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        validate_args(args)
        return run_workflow(args)
    except (
        MovieLensPipelineError,
        preprocess_movielens_1m.MovieLensPreprocessError,
        split_movielens_1m.MovieLensSplitError,
        evaluate_recommendations.EvaluationError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
