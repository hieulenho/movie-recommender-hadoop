#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

dataset_dir="$repo_root/data/raw/movielens-1m/ml-1m"
output_dir="$repo_root/results/movielens-1m"
top_l="50"
top_k="10"
min_common_users="5"
relevance_threshold="4"
reducers="4"
resume=""
preflight_only=""
keep_intermediate=""
force_stage=""

usage() {
  cat <<'USAGE'
Usage: run_movielens_1m.sh [options]

Options:
  --dataset-dir PATH
  --output-dir PATH
  --top-l N
  --top-k K
  --min-common-users N
  --relevance-threshold R
  --reducers N
  --resume
  --preflight-only
  --keep-intermediate
  --force-stage STAGE
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
    --reducers)
      reducers="${2:-}"
      shift 2
      ;;
    --resume)
      resume="--resume"
      shift
      ;;
    --preflight-only)
      preflight_only="--preflight-only"
      shift
      ;;
    --keep-intermediate)
      keep_intermediate="--keep-intermediate"
      shift
      ;;
    --force-stage)
      force_stage="${2:-}"
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

for value in "$top_l" "$top_k" "$min_common_users" "$relevance_threshold" "$reducers"; do
  case "$value" in
    ''|*[!0-9]*)
      echo "Numeric options must be positive integers." >&2
      exit 2
      ;;
  esac
done
if (( top_l < 1 || top_k < 1 || min_common_users < 1 || reducers < 1 )); then
  echo "top-l, top-k, min-common-users, and reducers must be at least 1." >&2
  exit 2
fi
if (( relevance_threshold < 1 || relevance_threshold > 5 )); then
  echo "relevance-threshold must be from 1 through 5." >&2
  exit 2
fi

cd "$repo_root"

command=(
  python3 scripts/movielens_1m_pipeline.py
  --dataset-dir "$dataset_dir"
  --output-dir "$output_dir"
  --top-l "$top_l"
  --top-k "$top_k"
  --min-common-users "$min_common_users"
  --relevance-threshold "$relevance_threshold"
  --reducers "$reducers"
)
if [[ -n "$resume" ]]; then command+=("$resume"); fi
if [[ -n "$preflight_only" ]]; then command+=("$preflight_only"); fi
if [[ -n "$keep_intermediate" ]]; then command+=("$keep_intermediate"); fi
if [[ -n "$force_stage" ]]; then command+=(--force-stage "$force_stage"); fi

"${command[@]}"
