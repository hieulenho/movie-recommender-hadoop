"""Path defaults and validation helpers for the Streamlit demo."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
METHODS = ("cosine", "cooccurrence")

MOVIELENS_DEFAULTS_BY_METHOD = {
    method: {
        "user_history": "results/movielens-1m/common/user-history",
        "recommendations": f"results/movielens-1m/{method}/recommendations",
        "evaluation": f"results/movielens-1m/{method}/metrics.json",
        "metadata": "results/movielens-1m/normalized/movie_metadata.csv",
        "manifest": "results/movielens-1m/movielens_1m_manifest.json",
        "method_comparison": "results/movielens-1m/method_comparison.csv",
        "benchmark": "target/scalability-benchmark/benchmark_results.csv",
    }
    for method in METHODS
}

FULL_REFERENCE_DEFAULTS = {
    "user_history": "results/full-reference-dataset/cosine/user-history",
    "recommendations": "results/full-reference-dataset/cosine/recommendations",
    "evaluation": "results/full-reference-dataset/cosine/metrics.json",
    "metadata": "results/full-reference-dataset/metadata/movie_metadata.csv",
    "manifest": "results/full-reference-dataset/full_dataset_manifest.json",
    "method_comparison": "results/full-reference-dataset/method_comparison.csv",
    "benchmark": "target/scalability-benchmark/benchmark_results.csv",
}

FULL_REFERENCE_DEFAULTS_BY_METHOD = {
    method: {
        **FULL_REFERENCE_DEFAULTS,
        "user_history": f"results/full-reference-dataset/{method}/user-history",
        "recommendations": f"results/full-reference-dataset/{method}/recommendations",
        "evaluation": f"results/full-reference-dataset/{method}/metrics.json",
    }
    for method in METHODS
}

REQUIRED_ARTIFACTS = {
    "user_history": ("User history", MOVIELENS_DEFAULTS_BY_METHOD["cosine"]["user_history"]),
    "recommendations": ("Final Top-K recommendations", MOVIELENS_DEFAULTS_BY_METHOD["cosine"]["recommendations"]),
}


def _existing_or_blank(repo_root: Path | str, defaults: Mapping[str, str]) -> dict[str, str]:
    root = Path(repo_root)
    result: dict[str, str] = {}
    for key, relative in defaults.items():
        path = root / relative
        if path.exists() or key not in {"metadata", "benchmark", "manifest", "method_comparison"}:
            result[key] = relative
        else:
            result[key] = ""
    return result


def build_dataset_method_defaults(dataset_mode: str, method: str = "cosine", repo_root: Path | str = REPO_ROOT) -> dict[str, str]:
    """Return repository-relative defaults for a dataset/method pair."""

    if method not in METHODS:
        raise ValueError(f"Unsupported method: {method}")
    if dataset_mode == "movielens":
        return _existing_or_blank(repo_root, MOVIELENS_DEFAULTS_BY_METHOD[method])
    if dataset_mode == "github-reference":
        return _existing_or_blank(repo_root, FULL_REFERENCE_DEFAULTS_BY_METHOD[method])
    return _existing_or_blank(repo_root, FULL_REFERENCE_DEFAULTS_BY_METHOD[method])


def movielens_artifacts_available(repo_root: Path | str = REPO_ROOT, method: str = "cosine") -> bool:
    root = Path(repo_root)
    defaults = MOVIELENS_DEFAULTS_BY_METHOD[method]
    return (root / defaults["user_history"]).exists() and (root / defaults["recommendations"]).exists()


def build_local_artifact_defaults(repo_root: Path | str = REPO_ROOT) -> dict[str, str]:
    """Return readable repository-relative defaults for local artifact mode."""

    if movielens_artifacts_available(repo_root):
        return build_dataset_method_defaults("movielens", "cosine", repo_root)
    return build_dataset_method_defaults("github-reference", "cosine", repo_root)


def resolve_artifact_path(repo_root: Path | str, text: str | None) -> Path | None:
    """Resolve a user-entered path relative to the repository root."""

    if text is None or str(text).strip() == "":
        return None
    candidate = Path(str(text).strip())
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def resolved_path_text(repo_root: Path | str, text: str | None) -> str:
    resolved = resolve_artifact_path(repo_root, text)
    return "" if resolved is None else str(resolved)


def required_artifact_errors(paths: Mapping[str, str], repo_root: Path | str = REPO_ROOT) -> list[str]:
    """Return concise user-facing errors for missing required artifacts."""

    errors: list[str] = []
    for key, (label, example) in REQUIRED_ARTIFACTS.items():
        entered = paths.get(key, "")
        resolved = resolve_artifact_path(repo_root, entered)
        if resolved is not None and resolved.exists():
            continue
        display_entered = entered.strip() if entered and entered.strip() else "(blank)"
        errors.append(f"Missing required artifact: {label}. Entered path: {display_entered}. Example: {example}")
    return errors


def resolve_paths_for_loading(paths: Mapping[str, str], repo_root: Path | str = REPO_ROOT) -> dict[str, str]:
    """Resolve all nonblank paths for loaders while preserving blanks for optional fields."""

    resolved: dict[str, str] = {}
    for key, text in paths.items():
        resolved[key] = resolved_path_text(repo_root, text)
    return resolved
