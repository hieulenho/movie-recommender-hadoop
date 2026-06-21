"""Build a deterministic source/documentation submission package."""

from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from typing import Any, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.final_artifact_utils import sha256_file, write_json


VERSION = "1.0.0"
FIXED_ZIP_DATE = (2024, 1, 1, 0, 0, 0)
EXCLUDE_PREFIXES = (
    "data/raw/",
    "data/processed/",
    "results/",
    "target/",
    "dist/",
    "full-run-logs/",
    "logs/",
    ".git/",
    ".venv/",
    ".venv-demo/",
    "__pycache__/",
)
EXCLUDE_PATTERNS = (
    "*.class",
    "*.jar",
    "*.war",
    "*.ear",
    "*.pyc",
    "*.log",
    "*.tmp",
    "*.bak",
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
)


class SubmissionPackageError(Exception):
    """Raised when a submission package cannot be built safely."""


def _git_lines(root: Path, args: Sequence[str]) -> list[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise SubmissionPackageError(completed.stderr.strip() or "git command failed")
    return [line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()]


def is_excluded(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if any(normalized.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return True
    parts = normalized.split("/")
    if any(part in {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"} for part in parts):
        return True
    return any(fnmatch.fnmatch(parts[-1], pattern) or fnmatch.fnmatch(normalized, pattern) for pattern in EXCLUDE_PATTERNS)


def collect_package_files(root: Path, include_untracked: bool = False) -> list[str]:
    files = set(_git_lines(root, ["ls-files"]))
    if include_untracked:
        files.update(_git_lines(root, ["ls-files", "--others", "--exclude-standard"]))
    kept = []
    for item in files:
        if is_excluded(item):
            continue
        path = root / item
        if path.is_file():
            kept.append(item)
    return sorted(kept)


def build_submission_package(
    repo_root: Path | str,
    output: Path | str,
    include_untracked: bool = False,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    output_path = Path(output).resolve()
    package_files = collect_package_files(root, include_untracked=include_untracked)
    if not package_files:
        raise SubmissionPackageError("No package files selected.")
    forbidden = [path for path in package_files if is_excluded(path)]
    if forbidden:
        raise SubmissionPackageError(f"Forbidden paths selected: {forbidden[:5]}")

    manifest = {
        "package_name": output_path.name,
        "version": VERSION,
        "include_untracked": include_untracked,
        "file_count": len(package_files),
        "files": [
            {
                "path": path,
                "sha256": sha256_file(root / path),
                "bytes": (root / path).stat().st_size,
            }
            for path in package_files
        ],
        "excluded_policy": {
            "prefixes": EXCLUDE_PREFIXES,
            "patterns": EXCLUDE_PATTERNS,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in package_files:
            info = zipfile.ZipInfo(path, FIXED_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (root / path).read_bytes())
        info = zipfile.ZipInfo("SUBMISSION_MANIFEST.json", FIXED_ZIP_DATE)
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n")

    manifest["zip_sha256"] = sha256_file(output_path)
    write_json(output_path.with_suffix(".manifest.json"), manifest)
    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build deterministic final submission ZIP.")
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--output", default=f"dist/movie-recommender-hadoop-v{VERSION}.zip", help="Output ZIP path.")
    parser.add_argument(
        "--include-untracked",
        action="store_true",
        help="Include untracked non-ignored source/docs files for local pre-commit packaging.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        manifest = build_submission_package(args.repo_root, args.output, include_untracked=args.include_untracked)
    except (SubmissionPackageError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Built {args.output} with {manifest['file_count']} files.")
    print(f"ZIP sha256: {manifest['zip_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
