"""Download or verify the official GroupLens MovieLens 1M archive."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import urllib.request
import zipfile
from typing import Mapping, Sequence


OFFICIAL_URL = "https://files.grouplens.org/datasets/movielens/ml-1m.zip"
OFFICIAL_SHA256: str | None = None
ARCHIVE_NAME = "ml-1m.zip"
EXTRACTED_DIR = "ml-1m"
REQUIRED_MEMBERS = (
    "ml-1m/ratings.dat",
    "ml-1m/movies.dat",
    "ml-1m/users.dat",
    "ml-1m/README",
)
TIMEOUT_SECONDS = 60
LICENSE_REMINDER = (
    "MovieLens 1M is provided by GroupLens for research use. Review the README/license "
    "and include the GroupLens acknowledgement in reports; do not commit or redistribute raw files."
)


class MovieLensDownloadError(Exception):
    """Fatal MovieLens acquisition error."""


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_output_path(path: Path, output_dir: Path) -> str:
    try:
        return path.resolve().relative_to(output_dir.resolve()).as_posix()
    except ValueError:
        return path.name


def archive_hash_ok(path: Path) -> bool:
    if OFFICIAL_SHA256 is None:
        return True
    return sha256_file(path).lower() == OFFICIAL_SHA256.lower()


def _safe_member_path(output_dir: Path, member_name: str) -> Path:
    destination = (output_dir / member_name).resolve()
    try:
        destination.relative_to(output_dir.resolve())
    except ValueError as exc:
        raise MovieLensDownloadError(f"Unsafe ZIP member path: {member_name}") from exc
    return destination


def validate_zip_structure(archive_path: Path | str, output_dir: Path | str | None = None) -> dict[str, object]:
    archive = Path(archive_path)
    root = Path(output_dir) if output_dir is not None else archive.parent
    if not archive.is_file():
        raise MovieLensDownloadError(f"Archive does not exist: {archive}")
    if not zipfile.is_zipfile(archive):
        raise MovieLensDownloadError(f"Archive is not a valid ZIP file: {archive}")
    with zipfile.ZipFile(archive, "r") as source_zip:
        names = set(source_zip.namelist())
        missing = sorted(set(REQUIRED_MEMBERS) - names)
        if missing:
            raise MovieLensDownloadError(f"MovieLens ZIP is missing required members: {', '.join(missing)}")
        for info in source_zip.infolist():
            _safe_member_path(root, info.filename)
    if not archive_hash_ok(archive):
        raise MovieLensDownloadError("Official archive SHA-256 validation failed.")
    return {
        "archive_name": archive.name,
        "archive_size_bytes": archive.stat().st_size,
        "archive_sha256": sha256_file(archive),
        "official_sha256": OFFICIAL_SHA256,
        "official_checksum_validated": OFFICIAL_SHA256 is not None,
        "required_members": list(REQUIRED_MEMBERS),
    }


def extract_archive(archive_path: Path | str, output_dir: Path | str, archive_only: bool = False) -> None:
    if archive_only:
        return
    archive = Path(archive_path)
    root = Path(output_dir)
    validate_zip_structure(archive, root)
    with zipfile.ZipFile(archive, "r") as source_zip:
        for info in source_zip.infolist():
            destination = _safe_member_path(root, info.filename)
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source_zip.open(info, "r") as input_file, destination.open("wb") as output_file:
                shutil.copyfileobj(input_file, output_file)


def validate_extracted_files(output_dir: Path | str) -> dict[str, dict[str, object]]:
    root = Path(output_dir)
    files: dict[str, dict[str, object]] = {}
    for member in REQUIRED_MEMBERS:
        path = root / member
        if not path.is_file():
            raise MovieLensDownloadError(f"Missing extracted MovieLens file: {member}")
        files[member] = {
            "path": member,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return files


def stream_download(url: str, destination: Path, timeout: int = TIMEOUT_SECONDS) -> None:
    partial = destination.with_suffix(destination.suffix + ".part")
    if partial.exists():
        partial.unlink()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response, partial.open("wb") as output_file:
            shutil.copyfileobj(response, output_file)
        if partial.stat().st_size == 0:
            raise MovieLensDownloadError("Downloaded archive is empty.")
        partial.replace(destination)
    except Exception:
        if partial.exists():
            partial.unlink()
        raise


def build_manifest(
    output_dir: Path,
    archive_summary: Mapping[str, object] | None,
    extracted_files: Mapping[str, object] | None,
    archive_only: bool,
) -> dict[str, object]:
    return {
        "dataset_name": "MovieLens 1M",
        "dataset_role": "primary-experimental",
        "source_url": OFFICIAL_URL,
        "license_reminder": LICENSE_REMINDER,
        "archive": archive_summary,
        "archive_only": archive_only,
        "extracted_files": extracted_files or {},
        "output_layout": {
            "archive": ARCHIVE_NAME,
            "extracted_dir": EXTRACTED_DIR,
            "manifest": "download_manifest.json",
        },
        "contains_absolute_paths": False,
    }


def write_manifest(output_dir: Path, manifest: Mapping[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "download_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def verify_existing(output_dir: Path, archive_only: bool = False) -> dict[str, object]:
    archive = output_dir / ARCHIVE_NAME
    archive_summary: dict[str, object] | None = None
    if archive.is_file():
        archive_summary = validate_zip_structure(archive, output_dir)
    elif (output_dir / (ARCHIVE_NAME + ".part")).exists():
        raise MovieLensDownloadError("Partial archive exists but completed archive is missing.")
    elif archive_only:
        raise MovieLensDownloadError(f"Archive is missing: {archive}")

    extracted = None
    if not archive_only:
        extracted = validate_extracted_files(output_dir)
    manifest = build_manifest(output_dir, archive_summary, extracted, archive_only)
    write_manifest(output_dir, manifest)
    return manifest


def download_movielens_1m(
    output_dir: Path | str,
    force: bool = False,
    verify_only: bool = False,
    archive_only: bool = False,
    source_url: str = OFFICIAL_URL,
) -> dict[str, object]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    archive = root / ARCHIVE_NAME

    if verify_only:
        return verify_existing(root, archive_only=archive_only)

    if archive.exists() and not force:
        try:
            manifest = verify_existing(root, archive_only=archive_only)
            manifest["reused_existing_archive"] = True
            write_manifest(root, manifest)
            return manifest
        except MovieLensDownloadError as exc:
            raise MovieLensDownloadError(f"Existing archive/data are not verified; pass --force to replace. {exc}") from exc

    if force and archive.exists():
        archive.unlink()
    stream_download(source_url, archive)
    archive_summary = validate_zip_structure(archive, root)
    extract_archive(archive, root, archive_only=archive_only)
    extracted = None if archive_only else validate_extracted_files(root)
    manifest = build_manifest(root, archive_summary, extracted, archive_only)
    write_manifest(root, manifest)
    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download or verify the official MovieLens 1M archive.")
    parser.add_argument("--output-dir", default="data/raw/movielens-1m", help="Directory for ml-1m.zip and extracted files.")
    parser.add_argument("--force", action="store_true", help="Replace an existing archive before downloading.")
    parser.add_argument("--verify-only", action="store_true", help="Verify existing archive/extracted files without downloading.")
    parser.add_argument("--archive-only", action="store_true", help="Download or verify only the ZIP archive without extraction.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        manifest = download_movielens_1m(
            args.output_dir,
            force=args.force,
            verify_only=args.verify_only,
            archive_only=args.archive_only,
        )
    except (MovieLensDownloadError, OSError, urllib.error.URLError, zipfile.BadZipFile) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print(LICENSE_REMINDER)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False))
    print(LICENSE_REMINDER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
