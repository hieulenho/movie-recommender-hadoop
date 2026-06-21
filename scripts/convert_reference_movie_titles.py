"""Convert GitHub reference movie_titles.txt into demo metadata CSV."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.full_reference_dataset import FullReferenceDatasetError, convert_movie_titles


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert reference movie_titles.txt to movie metadata CSV.")
    parser.add_argument("--input", required=True, help="Path to movie_titles.txt.")
    parser.add_argument("--output", required=True, help="Path to write movie_metadata.csv.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        result = convert_movie_titles(args.input, args.output)
    except (FullReferenceDatasetError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Metadata conversion complete: {result['metadata_rows']} rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
