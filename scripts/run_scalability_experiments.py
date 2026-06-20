"""Run reproducible scalability experiments for the Hadoop recommendation pipeline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from typing import Callable, Mapping, Sequence


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import evaluate_recommendations
from scripts import split_ratings_for_evaluation
from scripts.generate_synthetic_ratings import (
    DATASET_TYPE as SYNTHETIC_DATASET_TYPE,
    DEFAULT_SEED,
    SyntheticRatingsError,
    run_generation,
)
from scripts.summarize_scalability_results import summarize_results


BENCHMARK_OWNER = "movie-recommender-hadoop-scalability-benchmark"
SCHEMA_VERSION = 1
SUPPORTED_METHODS = {"cosine", "cooccurrence"}
BENCHMARK_RESULTS_HEADER = [
    "experimentId",
    "profile",
    "datasetType",
    "method",
    "seed",
    "users",
    "items",
    "ratingsPerUser",
    "ratingsRows",
    "trainRows",
    "testRows",
    "minCommonUsers",
    "topL",
    "topK",
    "relevanceThreshold",
    "reducers",
    "repetition",
    "datasetGenerationSeconds",
    "splitSeconds",
    "userHistorySeconds",
    "pairStatisticsSeconds",
    "similaritySeconds",
    "scoringSeconds",
    "topKSeconds",
    "evaluationSeconds",
    "totalPipelineSeconds",
    "totalRunSeconds",
    "userHistoryRows",
    "itemPairRows",
    "similarityRows",
    "rawPredictionRows",
    "recommendationUsers",
    "recommendationItems",
    "ratingsInputBytes",
    "trainBytes",
    "userHistoryBytes",
    "itemPairBytes",
    "similarityBytes",
    "rawPredictionBytes",
    "recommendationBytes",
    "predictionCoverage",
    "mae",
    "rmse",
    "precisionAtK",
    "recallAtK",
    "hitRateAtK",
    "ndcgAtK",
    "mrrAtK",
    "status",
    "errorStage",
    "errorMessage",
]

STAGE_SECONDS_TO_RESULT_COLUMNS = {
    "dataset_generation": "datasetGenerationSeconds",
    "split": "splitSeconds",
    "user_history": "userHistorySeconds",
    "pair_statistics": "pairStatisticsSeconds",
    "similarity": "similaritySeconds",
    "scoring": "scoringSeconds",
    "top_k": "topKSeconds",
    "evaluation": "evaluationSeconds",
}


class BenchmarkError(Exception):
    """Fatal benchmark setup or orchestration error."""


class StageFailure(BenchmarkError):
    """A single experiment stage failed."""

    def __init__(self, stage: str, message: str, exit_code: int | None = None):
        super().__init__(message)
        self.stage = stage
        self.exit_code = exit_code


class CommandResult:
    """Captured subprocess result."""

    def __init__(self, exit_code: int, elapsed_seconds: float, stdout_path: Path, stderr_path: Path):
        self.exit_code = exit_code
        self.elapsed_seconds = elapsed_seconds
        self.stdout_path = stdout_path
        self.stderr_path = stderr_path


def stage_order() -> list[str]:
    return [
        "dataset_generation",
        "split",
        "user_history",
        "pair_statistics",
        "similarity",
        "scoring",
        "top_k",
        "evaluation",
    ]


def deterministic_experiment_id(experiment: Mapping[str, object], profile_name: str = "") -> str:
    explicit = str(experiment.get("id", "")).strip()
    if explicit:
        return explicit
    prefix = profile_name or "profile"
    users = int(experiment["users"])
    ratings_per_user = int(experiment["ratings_per_user"])
    method = str(experiment["method"])
    return (
        f"{prefix}-{method}-{users * ratings_per_user}-ratings-"
        f"mcu{experiment['min_common_users']}-tl{experiment['top_l']}-tk{experiment['top_k']}"
    )


def load_profiles(path: Path | str) -> dict[str, object]:
    profile_path = Path(path)
    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BenchmarkError(f"Cannot read profiles file {profile_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BenchmarkError(f"Profiles file is not valid JSON: {exc}") from exc
    validate_profiles(data)
    return data


def validate_profiles(data: Mapping[str, object]) -> None:
    profiles = data.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise BenchmarkError("profiles must be a non-empty list.")

    profile_names: set[str] = set()
    experiment_ids: set[str] = set()
    for profile in profiles:
        if not isinstance(profile, dict):
            raise BenchmarkError("Each profile must be an object.")
        name = str(profile.get("name", "")).strip()
        if not name:
            raise BenchmarkError("Each profile must have a name.")
        if name in profile_names:
            raise BenchmarkError(f"Duplicate profile name: {name}")
        profile_names.add(name)

        experiments = profile.get("experiments")
        if not isinstance(experiments, list) or not experiments:
            raise BenchmarkError(f"Profile {name} must contain a non-empty experiments list.")
        for experiment in experiments:
            if not isinstance(experiment, dict):
                raise BenchmarkError(f"Profile {name} contains a non-object experiment.")
            experiment_id = deterministic_experiment_id(experiment, name)
            if experiment_id in experiment_ids:
                raise BenchmarkError(f"Duplicate experiment ID: {experiment_id}")
            experiment_ids.add(experiment_id)
            _validate_experiment(experiment, name)


def _validate_experiment(experiment: Mapping[str, object], profile_name: str) -> None:
    required = [
        "users",
        "items",
        "ratings_per_user",
        "method",
        "min_common_users",
        "top_l",
        "top_k",
        "relevance_threshold",
        "reducers",
        "repetitions",
    ]
    for key in required:
        if key not in experiment:
            raise BenchmarkError(f"Experiment in profile {profile_name} is missing {key}.")

    users = _require_int(experiment["users"], "users")
    items = _require_int(experiment["items"], "items")
    ratings_per_user = _require_int(experiment["ratings_per_user"], "ratings_per_user")
    method = str(experiment["method"])
    min_common_users = _require_int(experiment["min_common_users"], "min_common_users")
    top_l = _require_int(experiment["top_l"], "top_l")
    top_k = _require_int(experiment["top_k"], "top_k")
    relevance_threshold = _require_int(experiment["relevance_threshold"], "relevance_threshold")
    reducers = _require_int(experiment["reducers"], "reducers")
    repetitions = _require_int(experiment["repetitions"], "repetitions")

    if users < 2:
        raise BenchmarkError("users must be at least 2.")
    if items < 3:
        raise BenchmarkError("items must be at least 3.")
    if ratings_per_user < 2 or ratings_per_user > items:
        raise BenchmarkError("ratings_per_user must be between 2 and items.")
    if method not in SUPPORTED_METHODS:
        raise BenchmarkError(f"Unsupported similarity method: {method}")
    if min_common_users < 1:
        raise BenchmarkError("min_common_users must be at least 1.")
    if top_l < 1:
        raise BenchmarkError("top_l must be at least 1.")
    if top_k < 1:
        raise BenchmarkError("top_k must be at least 1.")
    if relevance_threshold < 1 or relevance_threshold > 5:
        raise BenchmarkError("relevance_threshold must be from 1 through 5.")
    if reducers < 1:
        raise BenchmarkError("reducers must be at least 1.")
    if repetitions < 1:
        raise BenchmarkError("repetitions must be at least 1.")


def _require_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise BenchmarkError(f"{name} must be an integer.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise BenchmarkError(f"{name} must be an integer.") from exc


def select_profile(data: Mapping[str, object], name: str) -> dict[str, object]:
    profiles = data.get("profiles", [])
    for profile in profiles:
        if isinstance(profile, dict) and profile.get("name") == name:
            return dict(profile)
    raise BenchmarkError(f"Unknown benchmark profile: {name}")


def experiments_for_profile(profile: Mapping[str, object], experiment_filter: str | None = None) -> list[dict[str, object]]:
    profile_name = str(profile["name"])
    selected: list[dict[str, object]] = []
    for raw_experiment in profile.get("experiments", []):
        experiment = dict(raw_experiment)
        experiment["id"] = deterministic_experiment_id(experiment, profile_name)
        experiment["profile"] = profile_name
        if experiment_filter and experiment_filter not in str(experiment["id"]):
            continue
        selected.append(experiment)
    if not selected:
        raise BenchmarkError("No experiments matched the selected profile/filter.")
    return selected


def validate_safe_output_dir(output_dir: Path | str, repo_root: Path | str) -> Path:
    resolved = Path(output_dir).resolve()
    repo = Path(repo_root).resolve()
    if resolved == Path(resolved.anchor):
        raise BenchmarkError(f"Refusing to use filesystem root as output directory: {resolved}")
    if resolved.exists() and not resolved.is_dir():
        raise BenchmarkError(f"Output path exists and is not a directory: {resolved}")
    protected_subtrees = [
        repo / ".git",
        repo / "src",
        repo / "scripts",
        repo / "docs",
        repo / "data",
        repo / "tests",
        repo / "report",
        repo / "config",
        repo / "docker",
    ]
    if resolved == repo:
        raise BenchmarkError("Refusing to use repository root as benchmark output directory.")
    for protected in protected_subtrees:
        try:
            resolved.relative_to(protected)
        except ValueError:
            continue
        raise BenchmarkError(f"Refusing to use protected repository subtree as output directory: {resolved}")
    if resolved == repo / "results":
        raise BenchmarkError("Use a benchmark-owned subdirectory under results, not results itself.")
    return resolved


def prepare_output_dir(output_dir: Path | str, repo_root: Path | str, resume: bool) -> Path:
    resolved = validate_safe_output_dir(output_dir, repo_root)
    if resume:
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved
    if not resolved.exists():
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved
    if not any(resolved.iterdir()):
        return resolved

    manifest_path = resolved / "benchmark_manifest.json"
    if not manifest_path.exists():
        raise BenchmarkError(
            f"Output directory is not empty and has no benchmark manifest: {resolved}"
        )
    manifest = _read_json(manifest_path)
    if manifest.get("tool") != BENCHMARK_OWNER:
        raise BenchmarkError(f"Output directory is not owned by this benchmark tool: {resolved}")
    if manifest.get("status") == "running":
        raise BenchmarkError(f"Refusing to overwrite incomplete benchmark output: {resolved}")
    shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def is_completed_manifest(path: Path | str) -> bool:
    manifest_path = Path(path)
    if not manifest_path.exists() or not manifest_path.is_file():
        return False
    try:
        manifest = _read_json(manifest_path)
    except (OSError, json.JSONDecodeError):
        return False
    return manifest.get("status") == "completed"


def count_text_part_rows(path: Path | str) -> int:
    total = 0
    for part_file in iter_part_files(path):
        with part_file.open("r", encoding="utf-8", errors="replace") as input_file:
            for _line in input_file:
                total += 1
    return total


def count_part_files(path: Path | str) -> int:
    return len(iter_part_files(path))


def iter_part_files(path: Path | str) -> list[Path]:
    candidate = Path(path)
    if candidate.is_file():
        if _is_hadoop_part_file(candidate):
            return [candidate]
        return []
    if not candidate.exists():
        return []
    return sorted(
        (
            child
            for child in candidate.iterdir()
            if child.is_file() and _is_hadoop_part_file(child)
        ),
        key=lambda item: item.name,
    )


def _is_hadoop_part_file(path: Path) -> bool:
    name = path.name
    if name.startswith(".") or name == "_SUCCESS" or name.endswith(".crc"):
        return False
    return name.startswith("part-")


def measure_part_bytes(path: Path | str) -> int:
    return sum(part_file.stat().st_size for part_file in iter_part_files(path))


def measure_file_bytes(path: Path | str) -> int:
    file_path = Path(path)
    if not file_path.exists():
        return 0
    return file_path.stat().st_size


def count_recommendation_items(path: Path | str) -> int:
    total = 0
    for part_file in iter_part_files(path):
        with part_file.open("r", encoding="utf-8", errors="replace") as input_file:
            for raw_line in input_file:
                line = raw_line.strip()
                if not line:
                    continue
                fields = line.split("\t")
                if len(fields) != 2 or not fields[1]:
                    continue
                total += len([entry for entry in fields[1].split(",") if entry])
    return total


def combine_part_files(source_dir: Path | str, destination: Path | str) -> None:
    parts = iter_part_files(source_dir)
    if not parts:
        raise BenchmarkError(f"No Hadoop part files found under {source_dir}")
    output_path = Path(destination)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        for part_file in parts:
            with part_file.open("r", encoding="utf-8", errors="replace") as input_file:
                shutil.copyfileobj(input_file, output_file)


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_external_normalized_input(path: Path | str) -> dict[str, object]:
    input_path = Path(path)
    load_result = split_ratings_for_evaluation.load_normalized_ratings(input_path)
    return _dataset_stats_from_records(load_result.records, "external-normalized", input_path)


def create_user_preserving_subset(input_path: Path | str, output_path: Path | str, target_rows: int) -> dict[str, object]:
    if target_rows < 1:
        raise BenchmarkError("target_rows must be positive.")
    load_result = split_ratings_for_evaluation.load_normalized_ratings(input_path)
    by_user: dict[int, list[split_ratings_for_evaluation.RatingRecord]] = {}
    for record in load_result.records:
        by_user.setdefault(record.user_id, []).append(record)

    selected: list[split_ratings_for_evaluation.RatingRecord] = []
    for user_id in sorted(by_user):
        selected.extend(sorted(by_user[user_id], key=lambda item: (item.date, item.movie_id)))
        if len(selected) >= target_rows:
            break
    if not selected:
        raise BenchmarkError("External input subset would be empty.")
    split_ratings_for_evaluation.write_ratings_csv(selected, output_path)
    return _dataset_stats_from_records(selected, "external-normalized", Path(output_path))


def _dataset_stats_from_records(
    records: Sequence[split_ratings_for_evaluation.RatingRecord],
    dataset_type: str,
    path: Path,
) -> dict[str, object]:
    users: dict[int, int] = {}
    items: dict[int, set[int]] = {}
    dates: list[str] = []
    for record in records:
        users[record.user_id] = users.get(record.user_id, 0) + 1
        items.setdefault(record.movie_id, set()).add(record.user_id)
        dates.append(record.date)
    user_counts = list(users.values())
    item_counts = [len(user_ids) for user_ids in items.values()]
    return {
        "dataset_type": dataset_type,
        "output_rows": len(records),
        "distinct_users": len(users),
        "distinct_items": len(items),
        "minimum_ratings_per_user": min(user_counts),
        "maximum_ratings_per_user": max(user_counts),
        "average_ratings_per_user": sum(user_counts) / len(user_counts),
        "minimum_users_per_item": min(item_counts),
        "maximum_users_per_item": max(item_counts),
        "average_users_per_item": sum(item_counts) / len(item_counts),
        "start_date": min(dates),
        "end_date": max(dates),
        "file_size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def build_stage_command(stage: str, java_classpath: str, config: Mapping[str, object], paths: Mapping[str, Path]) -> list[str]:
    reducers = str(config["reducers"])
    if stage == "user_history":
        return [
            "java",
            "-cp",
            java_classpath,
            "com.movierecommender.history.UserHistoryJob",
            "--local",
            "--reducers",
            reducers,
            str(paths["train_csv"]),
            str(paths["user_history_dir"]),
        ]
    if stage == "pair_statistics":
        return [
            "java",
            "-cp",
            java_classpath,
            "com.movierecommender.pairs.ItemPairStatisticsJob",
            "--local",
            "--reducers",
            reducers,
            str(paths["user_history_dir"]),
            str(paths["pair_stats_dir"]),
        ]
    if stage == "similarity":
        return [
            "java",
            "-cp",
            java_classpath,
            "com.movierecommender.similarity.ItemSimilarityPipeline",
            "--local",
            "--method",
            str(config["method"]),
            "--min-common-users",
            str(config["min_common_users"]),
            "--top-l",
            str(config["top_l"]),
            "--reducers",
            reducers,
            str(paths["pair_stats_dir"]),
            str(paths["similarity_dir"]),
        ]
    if stage == "scoring":
        return [
            "java",
            "-cp",
            java_classpath,
            "com.movierecommender.scoring.RecommendationScoringPipeline",
            "--local",
            "--reducers",
            reducers,
            str(paths["user_history_dir"]),
            str(paths["similarity_dir"]),
            str(paths["raw_predictions_dir"]),
        ]
    if stage == "top_k":
        return [
            "java",
            "-cp",
            java_classpath,
            "com.movierecommender.recommendation.TopKRecommendationJob",
            "--local",
            "--reducers",
            reducers,
            "--top-k",
            str(config["top_k"]),
            str(paths["user_history_dir"]),
            str(paths["raw_predictions_dir"]),
            str(paths["top_k_dir"]),
        ]
    raise BenchmarkError(f"Unknown stage: {stage}")


def command_uses_test_data(command: Sequence[str], test_path: Path | str) -> bool:
    test_text = str(test_path)
    return any(arg == test_text for arg in command)


def run_command(stage: str, args: Sequence[str], logs_dir: Path, cwd: Path) -> CommandResult:
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / f"{stage}.stdout.log"
    stderr_path = logs_dir / f"{stage}.stderr.log"
    start = time.perf_counter()
    completed = subprocess.run(
        list(args),
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        check=False,
    )
    elapsed = time.perf_counter() - start
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    return CommandResult(completed.returncode, elapsed, stdout_path, stderr_path)


def collect_environment_metadata(repo_root: Path) -> dict[str, object]:
    return {
        "container_os": platform.platform(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "java_version": _tool_version(["java", "-version"]),
        "maven_version": _tool_version(["mvn", "-version"]),
        "hadoop_dependency_version": _hadoop_version_from_pom(repo_root / "pom.xml"),
        "docker_image_name": os.environ.get("BENCHMARK_DOCKER_IMAGE", ""),
        "git_commit_id": os.environ.get("BENCHMARK_GIT_COMMIT", ""),
        "git_branch": os.environ.get("BENCHMARK_GIT_BRANCH", ""),
        "repository_dirty": os.environ.get("BENCHMARK_GIT_DIRTY", ""),
    }


def _tool_version(args: Sequence[str]) -> str:
    try:
        completed = subprocess.run(
            list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            shell=False,
        )
    except OSError:
        return "unavailable"
    text = (completed.stdout + "\n" + completed.stderr).strip()
    return text.splitlines()[0] if text else "unavailable"


def _hadoop_version_from_pom(pom_path: Path) -> str:
    try:
        root = ET.fromstring(pom_path.read_text(encoding="utf-8"))
    except (OSError, ET.ParseError):
        return "unavailable"
    namespace = {"m": "http://maven.apache.org/POM/4.0.0"}
    value = root.findtext("m:properties/m:hadoop.version", namespaces=namespace)
    return value or "unavailable"


def build_java_classpath(repo_root: Path, output_dir: Path) -> str:
    logs_dir = output_dir / "logs"
    package_result = run_command(
        "maven_package",
        ["mvn", "-q", "-DskipTests", "package"],
        logs_dir,
        repo_root,
    )
    if package_result.exit_code != 0:
        raise StageFailure("maven_package", "Maven package command failed.", package_result.exit_code)
    classpath_file = output_dir / "maven-runtime-classpath.txt"
    classpath_result = run_command(
        "maven_classpath",
        [
            "mvn",
            "-q",
            "dependency:build-classpath",
            "-Dmdep.includeScope=runtime",
            f"-Dmdep.outputFile={classpath_file}",
        ],
        logs_dir,
        repo_root,
    )
    if classpath_result.exit_code != 0:
        raise StageFailure("maven_classpath", "Maven classpath command failed.", classpath_result.exit_code)
    runtime_classpath = classpath_file.read_text(encoding="utf-8").strip()
    if not runtime_classpath:
        raise StageFailure("maven_classpath", "Maven runtime classpath is empty.")
    return os.pathsep.join([str(repo_root / "target" / "classes"), runtime_classpath])


def collect_runs_with_failure_policy(
    experiments: Sequence[dict[str, object]],
    run_one: Callable[[dict[str, object], int], dict[str, object]],
    fail_fast: bool,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for experiment in experiments:
        repetitions = int(experiment["repetitions"])
        for repetition in range(1, repetitions + 1):
            record = run_one(experiment, repetition)
            records.append(record)
            if record.get("status") == "failed" and fail_fast:
                return records
    return records


def execute_experiment(
    experiment: dict[str, object],
    repetition: int,
    output_dir: Path,
    repo_root: Path,
    java_classpath: str,
    input_path: Path | None,
    seed_override: int | None,
    keep_stage_output: bool,
    ordinal: int,
    total: int,
) -> dict[str, object]:
    experiment_id = str(experiment["id"])
    run_id = experiment_id if int(experiment["repetitions"]) == 1 else f"{experiment_id}-rep{repetition}"
    run_dir = output_dir / "runs" / run_id
    logs_dir = run_dir / "logs"
    manifest_path = run_dir / "run_manifest.json"

    if is_completed_manifest(manifest_path):
        manifest = _read_json(manifest_path)
        result_record = manifest.get("result_record")
        if isinstance(result_record, dict):
            return dict(result_record)

    if run_dir.exists():
        if manifest_path.exists() and not is_completed_manifest(manifest_path):
            raise BenchmarkError(f"Refusing to overwrite incomplete run directory: {run_dir}")
        shutil.rmtree(run_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    stage_statuses: dict[str, dict[str, object]] = {
        stage: {"status": "pending", "exit_code": None} for stage in stage_order()
    }
    write_json(
        {
            "tool": BENCHMARK_OWNER,
            "schema_version": SCHEMA_VERSION,
            "experiment_id": experiment_id,
            "run_id": run_id,
            "configuration": experiment,
            "repetition": repetition,
            "status": "running",
            "stage_statuses": stage_statuses,
            "artifact_names": [],
            "error": None,
        },
        manifest_path,
    )

    paths = _run_paths(run_dir)
    stage_seconds = {stage: None for stage in stage_order()}
    stage_exit_codes = {stage: None for stage in stage_order()}
    dataset_stats: dict[str, object] = {}
    split_stats: dict[str, object] = {}
    evaluation_metrics: dict[str, object] = {}
    stage_metrics: dict[str, object] = {}
    error_stage = ""
    error_message = ""
    total_start = time.perf_counter()

    try:
        print(f"[{ordinal}/{total}] {run_id}: preparing dataset")
        dataset_start = time.perf_counter()
        dataset_path = output_dir / "datasets" / run_id / "ratings.csv"
        dataset_stats_path = output_dir / "datasets" / run_id / "dataset_stats.json"
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if input_path is None:
                seed = int(seed_override if seed_override is not None else experiment.get("seed", DEFAULT_SEED))
                dataset_stats = run_generation(
                    users=int(experiment["users"]),
                    items=int(experiment["items"]),
                    ratings_per_user=int(experiment["ratings_per_user"]),
                    seed=seed,
                    output_path=dataset_path,
                    stats_output_path=dataset_stats_path,
                )
            else:
                seed = int(seed_override if seed_override is not None else experiment.get("seed", 0))
                dataset_stats = create_user_preserving_subset(
                    input_path,
                    dataset_path,
                    int(experiment["users"]) * int(experiment["ratings_per_user"]),
                )
                dataset_stats["seed"] = seed
                write_json(dataset_stats, dataset_stats_path)
        except (BenchmarkError, SyntheticRatingsError, OSError) as exc:
            raise StageFailure("dataset_generation", str(exc)) from exc
        stage_seconds["dataset_generation"] = time.perf_counter() - dataset_start
        stage_statuses["dataset_generation"] = {"status": "completed", "exit_code": 0}
        shutil.copyfile(dataset_stats_path, run_dir / "dataset_stats.json")

        print(f"[{ordinal}/{total}] {run_id}: running split")
        split_args = [
            sys.executable,
            "scripts/split_ratings_for_evaluation.py",
            "--input",
            str(dataset_path),
            "--train-output",
            str(paths["train_csv"]),
            "--test-output",
            str(paths["test_csv"]),
            "--stats-output",
            str(paths["split_stats"]),
        ]
        result = run_command("split", split_args, logs_dir, repo_root)
        stage_seconds["split"] = result.elapsed_seconds
        stage_exit_codes["split"] = result.exit_code
        if result.exit_code != 0:
            raise StageFailure("split", "Train/test split failed.", result.exit_code)
        stage_statuses["split"] = {"status": "completed", "exit_code": 0}
        split_stats = _read_json(paths["split_stats"])

        for stage in ["user_history", "pair_statistics", "similarity", "scoring", "top_k"]:
            print(f"[{ordinal}/{total}] {run_id}: running {stage.replace('_', ' ')}")
            command = build_stage_command(stage, java_classpath, experiment, paths)
            if command_uses_test_data(command, paths["test_csv"]):
                raise StageFailure(stage, "Model-building stage command includes the held-out test path.")
            result = run_command(stage, command, logs_dir, repo_root)
            stage_seconds[stage] = result.elapsed_seconds
            stage_exit_codes[stage] = result.exit_code
            if result.exit_code != 0:
                raise StageFailure(stage, f"{stage} command failed.", result.exit_code)
            stage_statuses[stage] = {"status": "completed", "exit_code": 0}

        try:
            combine_part_files(paths["raw_predictions_dir"], paths["raw_predictions_file"])
            combine_part_files(paths["top_k_dir"], paths["top_k_file"])
        except BenchmarkError as exc:
            raise StageFailure("top_k", str(exc)) from exc

        print(f"[{ordinal}/{total}] {run_id}: running evaluation")
        eval_args = [
            sys.executable,
            "scripts/evaluate_recommendations.py",
            "--train",
            str(paths["train_csv"]),
            "--test",
            str(paths["test_csv"]),
            "--raw-predictions",
            str(paths["raw_predictions_file"]),
            "--recommendations",
            str(paths["top_k_file"]),
            "--k",
            str(experiment["top_k"]),
            "--relevance-threshold",
            str(experiment["relevance_threshold"]),
            "--metrics-json",
            str(paths["evaluation_metrics"]),
            "--metrics-csv",
            str(paths["metrics_csv"]),
            "--per-user-output",
            str(paths["per_user_csv"]),
        ]
        result = run_command("evaluation", eval_args, logs_dir, repo_root)
        stage_seconds["evaluation"] = result.elapsed_seconds
        stage_exit_codes["evaluation"] = result.exit_code
        if result.exit_code != 0:
            raise StageFailure("evaluation", "Offline evaluation failed.", result.exit_code)
        stage_statuses["evaluation"] = {"status": "completed", "exit_code": 0}
        evaluation_metrics = _read_json(paths["evaluation_metrics"])

        stage_metrics = collect_stage_metrics(
            dataset_path,
            paths,
            dataset_stats,
            split_stats,
            stage_seconds,
            stage_exit_codes,
        )
        write_json(stage_metrics, run_dir / "stage_metrics.json")
        if not keep_stage_output:
            _remove_pipeline_owned_stage_output(paths["stages_dir"], run_dir)

        total_seconds = time.perf_counter() - total_start
        record = build_result_record(
            experiment,
            repetition,
            dataset_stats,
            split_stats,
            evaluation_metrics,
            stage_metrics,
            stage_seconds,
            total_seconds,
            status="completed",
            error_stage="",
            error_message="",
        )
        write_json(
            {
                "tool": BENCHMARK_OWNER,
                "schema_version": SCHEMA_VERSION,
                "experiment_id": experiment_id,
                "run_id": run_id,
                "configuration": experiment,
                "repetition": repetition,
                "dataset_hash": dataset_stats.get("sha256"),
                "status": "completed",
                "stage_statuses": stage_statuses,
                "output_artifact_names": _artifact_names(run_dir),
                "result_record": record,
                "error": None,
            },
            manifest_path,
        )
        return record
    except StageFailure as exc:
        error_stage = exc.stage
        error_message = str(exc)
        if error_stage in stage_statuses:
            stage_statuses[error_stage] = {"status": "failed", "exit_code": exc.exit_code}
        total_seconds = time.perf_counter() - total_start
        stage_metrics = collect_stage_metrics(
            dataset_path if "dataset_path" in locals() else run_dir,
            paths,
            dataset_stats,
            split_stats,
            stage_seconds,
            stage_exit_codes,
        )
        write_json(stage_metrics, run_dir / "stage_metrics.json")
        record = build_result_record(
            experiment,
            repetition,
            dataset_stats,
            split_stats,
            evaluation_metrics,
            stage_metrics,
            stage_seconds,
            total_seconds,
            status="failed",
            error_stage=error_stage,
            error_message=error_message,
        )
        write_json(
            {
                "tool": BENCHMARK_OWNER,
                "schema_version": SCHEMA_VERSION,
                "experiment_id": experiment_id,
                "run_id": run_id,
                "configuration": experiment,
                "repetition": repetition,
                "dataset_hash": dataset_stats.get("sha256"),
                "status": "failed",
                "stage_statuses": stage_statuses,
                "output_artifact_names": _artifact_names(run_dir),
                "result_record": record,
                "error": {
                    "stage": error_stage,
                    "message": error_message,
                    "exit_code": exc.exit_code,
                },
            },
            manifest_path,
        )
        return record


def _run_paths(run_dir: Path) -> dict[str, Path]:
    split_dir = run_dir / "split"
    stages_dir = run_dir / "stages"
    evaluator_dir = run_dir / "evaluator"
    return {
        "split_dir": split_dir,
        "train_csv": split_dir / "train_ratings.csv",
        "test_csv": split_dir / "test_ratings.csv",
        "split_stats": run_dir / "split_stats.json",
        "stages_dir": stages_dir,
        "user_history_dir": stages_dir / "user-history",
        "pair_stats_dir": stages_dir / "item-pair-statistics",
        "similarity_dir": stages_dir / "item-similarity",
        "raw_predictions_dir": stages_dir / "raw-predictions",
        "top_k_dir": stages_dir / "top-k-recommendations",
        "evaluator_dir": evaluator_dir,
        "raw_predictions_file": evaluator_dir / "raw_predictions.txt",
        "top_k_file": evaluator_dir / "top_k_recommendations.txt",
        "evaluation_metrics": run_dir / "evaluation_metrics.json",
        "metrics_csv": evaluator_dir / "metrics.csv",
        "per_user_csv": evaluator_dir / "per_user_metrics.csv",
    }


def collect_stage_metrics(
    dataset_path: Path,
    paths: Mapping[str, Path],
    dataset_stats: Mapping[str, object],
    split_stats: Mapping[str, object],
    stage_seconds: Mapping[str, float | None],
    stage_exit_codes: Mapping[str, int | None],
) -> dict[str, object]:
    return {
        "hadoop_counters": None,
        "hadoop_counters_status": "unavailable",
        "stages": {
            "ratings_input": {
                "output_rows": dataset_stats.get("output_rows"),
                "output_bytes": measure_file_bytes(dataset_path),
                "part_files": None,
                "success": bool(dataset_stats),
                "exit_code": 0 if dataset_stats else None,
            },
            "split": {
                "input_rows": dataset_stats.get("output_rows"),
                "train_rows": split_stats.get("train_rows"),
                "test_rows": split_stats.get("test_rows"),
                "train_bytes": measure_file_bytes(paths["train_csv"]),
                "test_bytes": measure_file_bytes(paths["test_csv"]),
                "success": bool(split_stats),
                "exit_code": stage_exit_codes.get("split"),
                "elapsed_seconds": stage_seconds.get("split"),
            },
            "user_history": _stage_dir_metrics(paths["train_csv"], paths["user_history_dir"], stage_seconds, stage_exit_codes, "user_history"),
            "pair_statistics": _stage_dir_metrics(paths["user_history_dir"], paths["pair_stats_dir"], stage_seconds, stage_exit_codes, "pair_statistics"),
            "similarity": _stage_dir_metrics(paths["pair_stats_dir"], paths["similarity_dir"], stage_seconds, stage_exit_codes, "similarity"),
            "scoring": _stage_dir_metrics(paths["similarity_dir"], paths["raw_predictions_dir"], stage_seconds, stage_exit_codes, "scoring"),
            "top_k": _stage_dir_metrics(paths["raw_predictions_dir"], paths["top_k_dir"], stage_seconds, stage_exit_codes, "top_k"),
        },
        "row_counts": {
            "ratings_rows": dataset_stats.get("output_rows", 0),
            "train_rows": split_stats.get("train_rows", 0),
            "test_rows": split_stats.get("test_rows", 0),
            "user_history_rows": count_text_part_rows(paths["user_history_dir"]),
            "item_pair_rows": count_text_part_rows(paths["pair_stats_dir"]),
            "similarity_rows": count_text_part_rows(paths["similarity_dir"]),
            "raw_prediction_rows": count_text_part_rows(paths["raw_predictions_dir"]),
            "recommendation_users": count_text_part_rows(paths["top_k_dir"]),
            "recommendation_items": count_recommendation_items(paths["top_k_dir"]),
        },
        "byte_counts": {
            "ratings_input_bytes": measure_file_bytes(dataset_path),
            "train_bytes": measure_file_bytes(paths["train_csv"]),
            "user_history_bytes": measure_part_bytes(paths["user_history_dir"]),
            "item_pair_bytes": measure_part_bytes(paths["pair_stats_dir"]),
            "similarity_bytes": measure_part_bytes(paths["similarity_dir"]),
            "raw_prediction_bytes": measure_part_bytes(paths["raw_predictions_dir"]),
            "recommendation_bytes": measure_part_bytes(paths["top_k_dir"]),
        },
        "part_file_counts": {
            "user_history_part_files": count_part_files(paths["user_history_dir"]),
            "item_pair_part_files": count_part_files(paths["pair_stats_dir"]),
            "similarity_part_files": count_part_files(paths["similarity_dir"]),
            "raw_prediction_part_files": count_part_files(paths["raw_predictions_dir"]),
            "top_k_part_files": count_part_files(paths["top_k_dir"]),
        },
    }


def _stage_dir_metrics(
    input_path: Path,
    output_path: Path,
    stage_seconds: Mapping[str, float | None],
    stage_exit_codes: Mapping[str, int | None],
    stage: str,
) -> dict[str, object]:
    return {
        "input_bytes": measure_file_bytes(input_path) if input_path.is_file() else measure_part_bytes(input_path),
        "output_rows": count_text_part_rows(output_path),
        "output_bytes": measure_part_bytes(output_path),
        "part_files": count_part_files(output_path),
        "success": stage_exit_codes.get(stage) == 0,
        "exit_code": stage_exit_codes.get(stage),
        "elapsed_seconds": stage_seconds.get(stage),
    }


def build_result_record(
    experiment: Mapping[str, object],
    repetition: int,
    dataset_stats: Mapping[str, object],
    split_stats: Mapping[str, object],
    evaluation_metrics: Mapping[str, object],
    stage_metrics: Mapping[str, object],
    stage_seconds: Mapping[str, float | None],
    total_run_seconds: float,
    status: str,
    error_stage: str,
    error_message: str,
) -> dict[str, object]:
    row_counts = stage_metrics.get("row_counts", {}) if isinstance(stage_metrics.get("row_counts"), dict) else {}
    byte_counts = stage_metrics.get("byte_counts", {}) if isinstance(stage_metrics.get("byte_counts"), dict) else {}
    total_pipeline_seconds = sum(
        value or 0.0
        for stage, value in stage_seconds.items()
        if stage != "dataset_generation"
    )
    seed = dataset_stats.get("seed", experiment.get("seed", ""))
    record: dict[str, object] = {
        "experimentId": experiment.get("id", ""),
        "profile": experiment.get("profile", ""),
        "datasetType": dataset_stats.get("dataset_type", SYNTHETIC_DATASET_TYPE),
        "method": experiment.get("method", ""),
        "seed": seed,
        "users": dataset_stats.get("distinct_users", experiment.get("users", "")),
        "items": dataset_stats.get("distinct_items", experiment.get("items", "")),
        "ratingsPerUser": experiment.get("ratings_per_user", ""),
        "ratingsRows": row_counts.get("ratings_rows", dataset_stats.get("output_rows", "")),
        "trainRows": row_counts.get("train_rows", split_stats.get("train_rows", "")),
        "testRows": row_counts.get("test_rows", split_stats.get("test_rows", "")),
        "minCommonUsers": experiment.get("min_common_users", ""),
        "topL": experiment.get("top_l", ""),
        "topK": experiment.get("top_k", ""),
        "relevanceThreshold": experiment.get("relevance_threshold", ""),
        "reducers": experiment.get("reducers", ""),
        "repetition": repetition,
        "datasetGenerationSeconds": _duration(stage_seconds.get("dataset_generation")),
        "splitSeconds": _duration(stage_seconds.get("split")),
        "userHistorySeconds": _duration(stage_seconds.get("user_history")),
        "pairStatisticsSeconds": _duration(stage_seconds.get("pair_statistics")),
        "similaritySeconds": _duration(stage_seconds.get("similarity")),
        "scoringSeconds": _duration(stage_seconds.get("scoring")),
        "topKSeconds": _duration(stage_seconds.get("top_k")),
        "evaluationSeconds": _duration(stage_seconds.get("evaluation")),
        "totalPipelineSeconds": _duration(total_pipeline_seconds),
        "totalRunSeconds": _duration(total_run_seconds),
        "userHistoryRows": row_counts.get("user_history_rows", ""),
        "itemPairRows": row_counts.get("item_pair_rows", ""),
        "similarityRows": row_counts.get("similarity_rows", ""),
        "rawPredictionRows": row_counts.get("raw_prediction_rows", ""),
        "recommendationUsers": row_counts.get("recommendation_users", ""),
        "recommendationItems": row_counts.get("recommendation_items", ""),
        "ratingsInputBytes": byte_counts.get("ratings_input_bytes", ""),
        "trainBytes": byte_counts.get("train_bytes", ""),
        "userHistoryBytes": byte_counts.get("user_history_bytes", ""),
        "itemPairBytes": byte_counts.get("item_pair_bytes", ""),
        "similarityBytes": byte_counts.get("similarity_bytes", ""),
        "rawPredictionBytes": byte_counts.get("raw_prediction_bytes", ""),
        "recommendationBytes": byte_counts.get("recommendation_bytes", ""),
        "predictionCoverage": _metric(evaluation_metrics.get("prediction_coverage")),
        "mae": _metric(evaluation_metrics.get("mae")),
        "rmse": _metric(evaluation_metrics.get("rmse")),
        "precisionAtK": _metric(evaluation_metrics.get("precision_at_k")),
        "recallAtK": _metric(evaluation_metrics.get("recall_at_k")),
        "hitRateAtK": _metric(evaluation_metrics.get("hit_rate_at_k")),
        "ndcgAtK": _metric(evaluation_metrics.get("ndcg_at_k")),
        "mrrAtK": _metric(evaluation_metrics.get("mrr_at_k")),
        "status": status,
        "errorStage": error_stage,
        "errorMessage": error_message,
    }
    return {column: record.get(column, "") for column in BENCHMARK_RESULTS_HEADER}


def _duration(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6f}"


def _metric(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return f"{float(value):.10f}"
    return str(value)


def write_results_csv(records: Sequence[Mapping[str, object]], path: Path | str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=BENCHMARK_RESULTS_HEADER, lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow({column: record.get(column, "") for column in BENCHMARK_RESULTS_HEADER})


def write_benchmark_json(
    records: Sequence[Mapping[str, object]],
    profile: Mapping[str, object],
    environment: Mapping[str, object],
    output_dir: Path,
) -> None:
    successful = sum(1 for record in records if record.get("status") == "completed")
    failed = sum(1 for record in records if record.get("status") == "failed")
    write_json(
        {
            "tool": BENCHMARK_OWNER,
            "schema_version": SCHEMA_VERSION,
            "benchmark_metadata": {
                "execution_mode": "docker",
                "timing_method": "time.perf_counter",
                "counter_policy": "Hadoop counters are unavailable unless a reliable structured source is added.",
            },
            "environment_metadata": environment,
            "profile_metadata": profile,
            "runs": list(records),
            "successful_run_count": successful,
            "failed_run_count": failed,
        },
        output_dir / "benchmark_results.json",
    )


def write_failures(records: Sequence[Mapping[str, object]], output_dir: Path) -> None:
    failures = [
        {
            "experimentId": record.get("experimentId", ""),
            "repetition": record.get("repetition", ""),
            "errorStage": record.get("errorStage", ""),
            "errorMessage": record.get("errorMessage", ""),
        }
        for record in records
        if record.get("status") == "failed"
    ]
    write_json(failures, output_dir / "failures.json")


def write_root_manifest(
    records: Sequence[Mapping[str, object]],
    profile_name: str,
    output_dir: Path,
    status: str,
) -> None:
    write_json(
        {
            "tool": BENCHMARK_OWNER,
            "schema_version": SCHEMA_VERSION,
            "profile": profile_name,
            "status": status,
            "successful_run_count": sum(1 for record in records if record.get("status") == "completed"),
            "failed_run_count": sum(1 for record in records if record.get("status") == "failed"),
            "artifact_names": [
                "benchmark_results.csv",
                "benchmark_results.json",
                "benchmark_summary.md",
                "method_comparison.csv",
                "size_scaling.csv",
                "failures.json",
            ],
        },
        output_dir / "benchmark_manifest.json",
    )


def write_json(data: object, path: Path | str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path | str) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _remove_pipeline_owned_stage_output(stages_dir: Path, run_dir: Path) -> None:
    if not stages_dir.exists():
        return
    resolved_stage = stages_dir.resolve()
    resolved_run = run_dir.resolve()
    try:
        resolved_stage.relative_to(resolved_run)
    except ValueError as exc:
        raise BenchmarkError(f"Refusing to remove non-run stage path: {stages_dir}") from exc
    shutil.rmtree(stages_dir)


def _artifact_names(run_dir: Path) -> list[str]:
    names: list[str] = []
    for child in sorted(run_dir.iterdir(), key=lambda item: item.name):
        names.append(child.name)
    return names


def run_benchmark(args: argparse.Namespace) -> int:
    if args.execution_mode != "docker":
        raise BenchmarkError("Only --execution-mode docker is supported in this milestone.")

    repo_root = Path(__file__).resolve().parents[1]
    output_dir = prepare_output_dir(args.output_dir, repo_root, args.resume)
    write_json(
        {
            "tool": BENCHMARK_OWNER,
            "schema_version": SCHEMA_VERSION,
            "profile": args.profile,
            "status": "running",
        },
        output_dir / "benchmark_manifest.json",
    )

    profiles_data = load_profiles(args.profiles_file)
    profile = select_profile(profiles_data, args.profile)
    experiments = experiments_for_profile(profile, args.experiment_filter)
    total_runs = sum(int(experiment["repetitions"]) for experiment in experiments)
    input_path = Path(args.input).resolve() if args.input else None
    if input_path is not None:
        validate_external_normalized_input(input_path)

    environment = collect_environment_metadata(repo_root)
    java_classpath = build_java_classpath(repo_root, output_dir)
    ordinal = 0

    def run_one(experiment: dict[str, object], repetition: int) -> dict[str, object]:
        nonlocal ordinal
        ordinal += 1
        return execute_experiment(
            experiment=experiment,
            repetition=repetition,
            output_dir=output_dir,
            repo_root=repo_root,
            java_classpath=java_classpath,
            input_path=input_path,
            seed_override=args.seed_override,
            keep_stage_output=args.keep_stage_output,
            ordinal=ordinal,
            total=total_runs,
        )

    records = collect_runs_with_failure_policy(experiments, run_one, args.fail_fast)
    write_results_csv(records, output_dir / "benchmark_results.csv")
    write_benchmark_json(records, profile, environment, output_dir)
    write_failures(records, output_dir)
    summarize_results(output_dir / "benchmark_results.csv", output_dir)
    write_root_manifest(records, str(profile["name"]), output_dir, "completed")
    return 1 if any(record.get("status") == "failed" for record in records) else 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Hadoop recommendation scalability experiments.")
    parser.add_argument("--profile", default="smoke")
    parser.add_argument("--profiles-file", default="config/scalability_profiles.json")
    parser.add_argument("--output-dir", default="target/scalability-benchmark")
    parser.add_argument("--execution-mode", default="docker")
    parser.add_argument("--input", help="Existing normalized CSV input.")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--keep-stage-output", action="store_true")
    parser.add_argument("--seed-override", type=int)
    parser.add_argument("--experiment-filter")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        return run_benchmark(args)
    except (BenchmarkError, OSError, split_ratings_for_evaluation.SplitRatingsError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
