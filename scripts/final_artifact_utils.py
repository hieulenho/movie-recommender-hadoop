"""Shared helpers for Milestone 12 final validation artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


class FinalArtifactError(Exception):
    """Raised when a finalization artifact is missing or invalid."""


def repo_root_from(path: Path | None = None) -> Path:
    start = (path or Path.cwd()).resolve()
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists() and (candidate / "README.md").exists():
            return candidate
    return start


def relative_path(path: Path | str, root: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def reject_json_constant(value: str) -> None:
    raise FinalArtifactError(f"Invalid floating-point JSON constant: {value}")


def load_json(path: Path | str) -> Any:
    with Path(path).open("r", encoding="utf-8") as input_file:
        return json.load(input_file, parse_constant=reject_json_constant)


def write_json(path: Path | str, payload: Mapping[str, Any] | Sequence[Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def read_csv_rows(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as input_file:
        return [dict(row) for row in csv.DictReader(input_file)]


def write_csv_rows(path: Path | str, header: Sequence[str], rows: Iterable[Sequence[Any]]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow(list(row))


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_record(path: Path | str, root: Path, role: str) -> dict[str, Any]:
    source = Path(path)
    record: dict[str, Any] = {
        "path": relative_path(source, root),
        "role": role,
        "exists": source.exists(),
    }
    if source.is_file():
        record["sha256"] = sha256_file(source)
        record["bytes"] = source.stat().st_size
    return record


def discover_part_files(path: Path | str) -> list[Path]:
    source = Path(path)
    if source.is_file():
        return [source]
    if not source.is_dir():
        raise FinalArtifactError(f"Artifact path does not exist: {source}")
    files = [
        item
        for item in source.iterdir()
        if item.is_file()
        and item.name.startswith("part-")
        and not item.name.startswith(".")
        and not item.name.endswith(".crc")
    ]
    if not files:
        raise FinalArtifactError(f"No Hadoop part files found in: {source}")
    return sorted(files, key=lambda item: item.name)


def count_part_rows(path: Path | str) -> int:
    rows = 0
    for part_file in discover_part_files(path):
        with part_file.open("r", encoding="utf-8") as input_file:
            rows += sum(1 for line in input_file if line.strip())
    return rows


def count_recommendation_items(path: Path | str) -> tuple[int, int]:
    users = 0
    items = 0
    for part_file in discover_part_files(path):
        with part_file.open("r", encoding="utf-8") as input_file:
            for line in input_file:
                stripped = line.strip()
                if not stripped:
                    continue
                users += 1
                _user, payload = stripped.split("\t", 1)
                items += len([item for item in payload.split(",") if item.strip()])
    return users, items


def ensure_no_invalid_floats(value: Any, location: str = "$") -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise FinalArtifactError(f"Invalid floating-point value at {location}")
    elif isinstance(value, Mapping):
        for key, nested in value.items():
            ensure_no_invalid_floats(nested, f"{location}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, nested in enumerate(value):
            ensure_no_invalid_floats(nested, f"{location}[{index}]")
