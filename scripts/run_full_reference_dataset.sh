#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

dataset_dir="$repo_root/data/raw/github-reference"
output_dir="$repo_root/results/full-reference-dataset"
top_l="10"
top_k="5"
min_common_users="1"
relevance_threshold="4"
source_format="github-reference-3col"

usage() {
  cat <<'USAGE'
Usage: run_full_reference_dataset.sh [options]

Options:
  --dataset-dir PATH
  --output-dir PATH
  --top-l N
  --top-k K
  --min-common-users N
  --relevance-threshold R
  --source-format github-reference-3col|netflix-raw|auto
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dataset-dir)
      dataset_dir="${2:-}"
      shift 2
      ;;
    --output-dir)
      output_dir="${2:-}"
      shift 2
      ;;
    --top-l)
      top_l="${2:-}"
      shift 2
      ;;
    --top-k)
      top_k="${2:-}"
      shift 2
      ;;
    --min-common-users)
      min_common_users="${2:-}"
      shift 2
      ;;
    --relevance-threshold)
      relevance_threshold="${2:-}"
      shift 2
      ;;
    --source-format)
      source_format="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$repo_root"

python3 scripts/full_reference_dataset.py \
  --dataset-dir "$dataset_dir" \
  --output-dir "$output_dir" \
  --top-l "$top_l" \
  --top-k "$top_k" \
  --min-common-users "$min_common_users" \
  --relevance-threshold "$relevance_threshold" \
  --source-format "$source_format"
