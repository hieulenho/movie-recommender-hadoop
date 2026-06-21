#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output="dist/movie-recommender-hadoop-v1.0.0.zip"
include_untracked=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      output="$2"
      shift 2
      ;;
    --include-untracked)
      include_untracked=(--include-untracked)
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

cd "$repo_root"
python scripts/build_submission_package.py --output "$output" "${include_untracked[@]}"
