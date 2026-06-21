"""Path defaults and validation helpers for the Streamlit demo."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]

FULL_REFERENCE_DEFAULTS = {
    "user_history": "results/full-reference-dataset/cosine/user-history",
    "recommendations": "results/full-reference-dataset/cosine/recommendations",
    "evaluation": "results/full-reference-dataset/cosine/metrics.json",
    "metadata": "results/full-reference-dataset/metadata/movie_metadata.csv",
    "benchmark": "target/scalability-benchmark/benchmark_results.csv",
}

REQUIRED_ARTIFACTS = {
    "user_history": ("Lịch sử người dùng", FULL_REFERENCE_DEFAULTS["user_history"]),
    "recommendations": ("Gợi ý Top-K cuối cùng", FULL_REFERENCE_DEFAULTS["recommendations"]),
}


def build_local_artifact_defaults(repo_root: Path | str = REPO_ROOT) -> dict[str, str]:
    """Return readable repository-relative defaults for local artifact mode."""

    root = Path(repo_root)
    defaults: dict[str, str] = {}
    for key, primary in FULL_REFERENCE_DEFAULTS.items():
        primary_path = root / primary
        if primary_path.exists() or key not in {"metadata", "benchmark"}:
            defaults[key] = primary
            continue
        defaults[key] = ""
    return defaults


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
        display_entered = entered.strip() if entered and entered.strip() else "(trống)"
        errors.append(
            f"Thiếu artifact bắt buộc: {label}. "
            f"Đường dẫn đã nhập: {display_entered}. "
            f"Ví dụ full-reference: {example}"
        )
    return errors


def resolve_paths_for_loading(paths: Mapping[str, str], repo_root: Path | str = REPO_ROOT) -> dict[str, str]:
    """Resolve all nonblank paths for loaders while preserving blanks for optional fields."""

    resolved: dict[str, str] = {}
    for key, text in paths.items():
        resolved[key] = resolved_path_text(repo_root, text)
    return resolved
