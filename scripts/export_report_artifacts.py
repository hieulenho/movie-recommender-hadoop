"""Export selected full-reference artifacts into a report-ready folder."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Sequence


class ReportArtifactExportError(Exception):
    """Fatal report artifact export error."""


REPORT_ARTIFACTS = [
    ("normalized/dataset_stats.json", "dataset_stats.json"),
    ("split/split_stats.json", "split_stats.json"),
    ("method_comparison.csv", "method_comparison.csv"),
    ("cosine/metrics.json", "cosine_metrics.json"),
    ("cosine/metrics.csv", "cosine_metrics.csv"),
    ("cooccurrence/metrics.json", "cooccurrence_metrics.json"),
    ("cooccurrence/metrics.csv", "cooccurrence_metrics.csv"),
    ("metadata/movie_metadata.csv", "movie_metadata.csv"),
]


def export_report_artifacts(run_dir: Path | str, output_dir: Path | str) -> dict[str, object]:
    source_root = Path(run_dir)
    destination_root = Path(output_dir)
    if not source_root.exists():
        raise ReportArtifactExportError(f"Run directory does not exist: {source_root}")
    destination_root.mkdir(parents=True, exist_ok=True)

    exported: list[str] = []
    for relative_source, output_name in REPORT_ARTIFACTS:
        source = source_root / relative_source
        if not source.exists():
            continue
        destination = destination_root / output_name
        shutil.copyfile(source, destination)
        exported.append(output_name)

    manifest = {
        "artifact_count": len(exported),
        "artifacts": exported,
        "source_run_subpaths": [source for source, _name in REPORT_ARTIFACTS],
    }
    (destination_root / "report_artifacts_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Copy report-ready full-reference dataset artifacts.")
    parser.add_argument("--run-dir", required=True, help="Full-reference dataset run directory.")
    parser.add_argument("--output-dir", required=True, help="Directory to write report artifacts.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        manifest = export_report_artifacts(args.run_dir, args.output_dir)
    except (ReportArtifactExportError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Exported {manifest['artifact_count']} report artifacts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
